import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.models.account import Account
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan
from app.models.client_assignment import ClientAssignment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/clients", tags=["clients"])


class ClientCreateRequest(BaseModel):
    brand_name: str = Field(..., min_length=2, max_length=255)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: str | None = None
    # Email do dono da empresa — recebe o link de verificação (Resend).
    # O login do dono só funciona depois de verificar.
    email: str = Field(..., min_length=5, max_length=255)


class ClientOut(BaseModel):
    id: str
    brand_name: str
    username: str
    full_name: str | None
    is_active: bool
    plan: str = "free"
    plan_type: str = "dependente"
    email: str | None = None
    email_verified: bool = False
    blocked_modules: list[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


async def _get_current_subscription_plan(
    account_id: str, db: AsyncSession
) -> str | None:
    """Get the current active plan for an account."""
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.account_id == account_id,
                Subscription.is_active == True,
                Subscription.status == SubscriptionStatus.CONFIRMED,
            )
        ).order_by(Subscription.created_at.desc())
    )
    sub = result.scalars().first()
    return sub.plan if sub else None


async def _require_agency_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ensure the user's tenant is an agency account (plan_type == 'agencia').

    Gated purely by account type, decoupled from the billing plan. Limits per
    plan (nº de clientes etc.) will be enforced later, in the pricing phase.
    """
    account_result = await db.execute(
        select(Account).where(Account.id == current_user.tenant_id)
    )
    account = account_result.scalar_one_or_none()
    if account and account.plan_type == "agencia":
        return account.plan_type

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Apenas contas do tipo Agência podem gerenciar clientes.",
    )


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(
    body: ClientCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: str = Depends(_require_agency_plan),
):
    """Agency creates a sub-account (client) under their tenant."""

    # Check username uniqueness
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username já em uso.")

    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Email do dono inválido.")

    # Create sub-account linked to the agency.
    # Empresa gerenciada nasce como "dependente": marcada como filha da
    # agência, sem página de Clientes, e com os módulos controláveis pela mãe.
    client_account = Account(
        id=str(uuid.uuid4()),
        brand_name=body.brand_name,
        parent_account_id=current_user.tenant_id,
        plan_type="dependente",
        customer_email=email,
        customer_name=body.full_name,
        blocked_modules=[],
        is_active=True,
    )
    db.add(client_account)
    await db.flush()

    # Dono da empresa-filha: só loga depois de verificar o email (Resend)
    verification_token = str(uuid.uuid4()) + str(uuid.uuid4()).replace("-", "")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=client_account.id,
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="admin",
        is_verified=False,
        verification_token=verification_token,
    )
    db.add(user)
    await db.flush()

    # Envia o link de verificação para o email do dono (não bloqueante)
    try:
        from app.services.email_service import send_verification_email
        await send_verification_email(email, verification_token, body.full_name or body.brand_name)
    except Exception as exc:
        logger.warning("Falha ao enviar email de verificação do cliente %s: %s", client_account.id, exc)

    # Create free subscription for the client
    sub = Subscription(
        account_id=client_account.id,
        plan=SubscriptionPlan.FREE,
        value=0.0,
        status=SubscriptionStatus.CONFIRMED,
        is_active=True,
        auto_renew=True,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(sub)
    await db.commit()

    logger.info(
        "Agency %s created client account %s (user: %s)",
        current_user.tenant_id,
        client_account.id,
        body.username,
    )

    return ClientOut(
        id=client_account.id,
        brand_name=client_account.brand_name,
        username=body.username,
        full_name=body.full_name,
        is_active=True,
        plan="free",
        plan_type="dependente",
        email=email,
        email_verified=False,
        blocked_modules=[],
        created_at=client_account.created_at,
    )


@router.get("", response_model=list[ClientOut])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: str = Depends(_require_agency_plan),
):
    """List all sub-accounts (clients) managed by the agency.

    Admins veem todas; membros não-admin só veem as empresas atribuídas.
    """
    q = select(Account).where(
        Account.parent_account_id == current_user.tenant_id
    ).order_by(Account.created_at.desc())

    if current_user.role != "admin":
        assigned = select(ClientAssignment.client_account_id).where(
            ClientAssignment.user_id == current_user.id
        )
        q = q.where(Account.id.in_(assigned))

    result = await db.execute(q)
    accounts = result.scalars().all()

    clients_out = []
    for acc in accounts:
        user_result = await db.execute(
            select(User).where(
                User.tenant_id == acc.id, User.role == "admin"
            ).limit(1)
        )
        admin_user = user_result.scalar_one_or_none()
        plan = await _get_current_subscription_plan(acc.id, db)

        clients_out.append(
            ClientOut(
                id=acc.id,
                brand_name=acc.brand_name,
                username=admin_user.username if admin_user else "—",
                full_name=admin_user.full_name if admin_user else None,
                is_active=acc.is_active,
                plan=plan or "free",
                plan_type=acc.plan_type,
                email=acc.customer_email,
                email_verified=bool(admin_user and admin_user.is_verified),
                blocked_modules=list(acc.blocked_modules or []),
                created_at=acc.created_at,
            )
        )

    return clients_out


@router.post("/{client_id}/impersonate")
async def impersonate_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: str = Depends(_require_agency_plan),
):
    """Generate a token for the agency to access the client's account."""
    result = await db.execute(
        select(Account).where(
            and_(
                Account.id == client_id,
                Account.parent_account_id == current_user.tenant_id,
            )
        )
    )
    client_account = result.scalar_one_or_none()
    if not client_account:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    # Acesso restrito: membro não-admin só acessa empresas atribuídas a ele
    if current_user.role != "admin":
        assigned = await db.execute(
            select(ClientAssignment).where(
                ClientAssignment.user_id == current_user.id,
                ClientAssignment.client_account_id == client_id,
            )
        )
        if not assigned.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="Você não tem acesso a esta empresa. Peça ao admin para atribuí-la a você.",
            )

    result = await db.execute(
        select(User).where(
            User.tenant_id == client_account.id, User.role == "admin"
        ).limit(1)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário do cliente não encontrado.")

    from app.core.security import create_access_token, create_refresh_token

    return {
        "access_token": create_access_token(target_user.id, target_user.tenant_id, "agent"),
        "refresh_token": create_refresh_token(target_user.id, target_user.tenant_id),
        "token_type": "bearer",
        "user_id": target_user.id,
        "tenant_id": target_user.tenant_id,
        "role": "agent",
        "client_brand_name": client_account.brand_name,
    }


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: str = Depends(_require_agency_plan),
):
    """Deactivate a client account."""
    result = await db.execute(
        select(Account).where(
            and_(
                Account.id == client_id,
                Account.parent_account_id == current_user.tenant_id,
            )
        )
    )
    client_account = result.scalar_one_or_none()
    if not client_account:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    client_account.is_active = False
    await db.commit()
    logger.info("Agency %s deactivated client %s", current_user.tenant_id, client_id)


# ---------------------------------------------------------------------------
# Módulos — a agência-mãe bloqueia módulos das empresas dependentes;
# o super admin (SUPER_ADMIN_EMAILS) faz o mesmo com qualquer conta
# ---------------------------------------------------------------------------

from app.core.modules import AVAILABLE_MODULES, is_super_admin


class ModulesUpdateRequest(BaseModel):
    blocked_modules: list[str] = Field(default_factory=list)


async def _get_manageable_account(
    account_id: str, current_user: User, db: AsyncSession
) -> Account:
    """Conta que o usuário pode gerenciar: super admin → qualquer; agência
    (admin) → apenas as empresas-filhas dela."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    if is_super_admin(current_user):
        return target

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admins podem gerenciar módulos.")
    if target.parent_account_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Esta empresa não pertence à sua agência.")
    return target


@router.get("/{client_id}/modules")
async def get_client_modules(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_manageable_account(client_id, current_user, db)
    return {
        "account_id": target.id,
        "brand_name": target.brand_name,
        "blocked_modules": list(target.blocked_modules or []),
        "available_modules": AVAILABLE_MODULES,
    }


@router.put("/{client_id}/modules")
async def update_client_modules(
    client_id: str,
    body: ModulesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_manageable_account(client_id, current_user, db)

    invalid = set(body.blocked_modules) - set(AVAILABLE_MODULES)
    if invalid:
        raise HTTPException(status_code=422, detail=f"Módulos inválidos: {', '.join(sorted(invalid))}")

    target.blocked_modules = sorted(set(body.blocked_modules))
    await db.commit()
    logger.info("Usuário %s definiu módulos bloqueados de %s: %s",
                current_user.id, target.id, target.blocked_modules)
    return {"account_id": target.id, "blocked_modules": target.blocked_modules}


# ---------------------------------------------------------------------------
# Atribuições — quais empresas cada membro da agência pode acessar
# ---------------------------------------------------------------------------

class AssignmentsUpdateRequest(BaseModel):
    client_ids: list[str] = Field(default_factory=list)


async def _get_member_or_404(user_id: str, tenant_id: str, db: AsyncSession) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Membro não encontrado neste tenant.")
    return member


@router.get("/assignments/{user_id}")
async def list_assignments(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: str = Depends(_require_agency_plan),
):
    """Empresas atribuídas a um membro da agência (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admins podem ver atribuições.")
    await _get_member_or_404(user_id, current_user.tenant_id, db)

    result = await db.execute(
        select(ClientAssignment.client_account_id).where(ClientAssignment.user_id == user_id)
    )
    return {"user_id": user_id, "client_ids": [row[0] for row in result.all()]}


@router.put("/assignments/{user_id}")
async def update_assignments(
    user_id: str,
    body: AssignmentsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: str = Depends(_require_agency_plan),
):
    """Substitui as empresas atribuídas a um membro (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admins podem atribuir empresas.")
    await _get_member_or_404(user_id, current_user.tenant_id, db)

    # Valida que todos os ids são empresas desta agência
    if body.client_ids:
        result = await db.execute(
            select(Account.id).where(
                Account.parent_account_id == current_user.tenant_id,
                Account.id.in_(body.client_ids),
            )
        )
        valid_ids = {row[0] for row in result.all()}
        invalid = set(body.client_ids) - valid_ids
        if invalid:
            raise HTTPException(status_code=400, detail=f"Empresas inválidas: {', '.join(invalid)}")

    # Substitui tudo (delete + insert)
    existing = await db.execute(
        select(ClientAssignment).where(ClientAssignment.user_id == user_id)
    )
    for a in existing.scalars().all():
        await db.delete(a)
    await db.flush()

    for cid in set(body.client_ids):
        db.add(ClientAssignment(user_id=user_id, client_account_id=cid))
    await db.commit()

    logger.info("Admin %s set %d assignments for member %s",
                current_user.id, len(set(body.client_ids)), user_id)
    return {"user_id": user_id, "client_ids": list(set(body.client_ids))}
