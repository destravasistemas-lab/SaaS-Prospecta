import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,
)
from app.models.account import Account
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.services.email_service import send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth-jwt"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    brand_name: str = Field(..., min_length=2, max_length=255)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str


class UserOut(BaseModel):
    id: str
    tenant_id: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    plan_type: str | None = None
    brand_name: str | None = None
    # Módulos bloqueados pela agência-mãe/super admin (o frontend esconde)
    blocked_modules: list[str] = Field(default_factory=list)
    # Módulos que ESTE usuário realmente acessa (conta - bloqueados ∩ permitidos)
    modules: list[str] = Field(default_factory=list)
    # Lista escolhida pelo admin p/ este usuário (None = herda todos da conta)
    allowed_modules: list[str] | None = None
    # Super admin do sistema (SUPER_ADMIN_EMAILS)
    is_super_admin: bool = False


# ---------------------------------------------------------------------------
# Register — cria tenant (Account) + primeiro usuário admin
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Verifica se username já existe
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username já em uso.")

    # Cria o tenant (Account)
    tenant = Account(
        id=str(uuid.uuid4()),
        brand_name=body.brand_name,
        meta_page_id=None,
        meta_access_token=None,
    )
    db.add(tenant)
    await db.flush()  # gera tenant.id sem commitar

    # Cria o usuário admin do tenant
    verification_token = str(uuid.uuid4()) + str(uuid.uuid4()).replace("-", "")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="admin",
        is_verified=False,
        verification_token=verification_token,
    )
    db.add(user)
    await db.flush()

    # Cria subscription gratuita confirmada para o tenant
    sub = Subscription(
        account_id=tenant.id,
        plan=SubscriptionPlan.FREE,
        value=0.0,
        status=SubscriptionStatus.CONFIRMED,
        is_active=True,
        auto_renew=True,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(sub)
    await db.flush()

    # Envia email de verificação (não bloqueante)
    await send_verification_email(body.username, verification_token, body.full_name or body.username)

    logger.info("Novo tenant registrado: %s | user: %s", tenant.id, user.username)

    return TokenResponse(
        access_token=create_access_token(user.id, tenant.id, user.role),
        refresh_token=create_refresh_token(user.id, tenant.id),
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada.")

    # Dono de empresa dependente (criada pela agência) só entra após verificar
    # o email — o link chega pelo Resend na criação da empresa.
    if not user.is_verified:
        acc_result = await db.execute(select(Account).where(Account.id == user.tenant_id))
        acc = acc_result.scalar_one_or_none()
        if acc and acc.plan_type == "dependente":
            raise HTTPException(
                status_code=403,
                detail="Verifique seu email para ativar o acesso — enviamos o link de confirmação.",
            )

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id, user.role),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Token de refresh inválido.")

    user_id = payload.get("sub", "")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id, user.role),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


# ---------------------------------------------------------------------------
# Me — retorna usuário autenticado
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.id == current_user.tenant_id))
    account = result.scalar_one_or_none()
    from app.core.modules import is_super_admin, effective_modules_for
    modules = await effective_modules_for(db, current_user)
    return UserOut(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        plan_type=account.plan_type if account else None,
        brand_name=account.brand_name if account else None,
        blocked_modules=list(account.blocked_modules or []) if account else [],
        modules=modules,
        allowed_modules=current_user.allowed_modules,
        is_super_admin=is_super_admin(current_user),
    )


# ---------------------------------------------------------------------------
# Criar agente adicional (apenas admin do tenant)
# ---------------------------------------------------------------------------

class CompleteSignupRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)


@router.post("/complete-signup", response_model=TokenResponse)
async def complete_signup(body: CompleteSignupRequest, db: AsyncSession = Depends(get_db)):
    """Complete signup after payment - set password for pre-created account"""
    result = await db.execute(select(User).where(User.username == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Conta não encontrada. Efetue o checkout primeiro.")

    if user.is_active and user.password_hash:
        raise HTTPException(status_code=400, detail="Conta já ativada. Faça login.")

    result = await db.execute(select(Account).where(Account.id == user.tenant_id))
    account = result.scalar_one_or_none()
    if not account or not account.is_active:
        raise HTTPException(status_code=400, detail="Pagamento ainda não confirmado.")

    user.password_hash = hash_password(body.password)
    user.is_active = True
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id, user.role),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


class CreateAgentRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: str | None = None
    role: str = "agent"
    # Módulos permitidos p/ este usuário (None = todos os da conta). Só p/ agent.
    allowed_modules: list[str] | None = None
    # Empresas-filhas que este membro da agência pode ver (ClientAssignment).
    client_ids: list[str] = Field(default_factory=list)


class UpdateUserModulesRequest(BaseModel):
    allowed_modules: list[str] | None = None  # None = herda todos da conta


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: CreateAgentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admins podem criar usuários.")

    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username já em uso.")

    if body.role not in ("admin", "agent"):
        raise HTTPException(status_code=400, detail="Role inválida. Use 'admin' ou 'agent'.")

    # Módulos por usuário só valem para agentes; admin sempre vê tudo da conta.
    allowed_modules = None
    if body.role == "agent" and body.allowed_modules is not None:
        from app.core.modules import AVAILABLE_MODULES
        allowed_modules = [m for m in body.allowed_modules if m in AVAILABLE_MODULES]

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        allowed_modules=allowed_modules,
    )
    db.add(user)
    await db.flush()

    # Vínculo com empresas-filhas (só faz sentido para agência).
    if body.client_ids:
        from app.models.client_assignment import ClientAssignment
        # Garante que os client_ids são empresas-filhas desta agência.
        valid = await db.execute(
            select(Account.id).where(
                Account.id.in_(body.client_ids),
                Account.parent_account_id == current_user.tenant_id,
            )
        )
        for cid in [r[0] for r in valid.all()]:
            db.add(ClientAssignment(user_id=user.id, client_account_id=cid))
        await db.flush()

    return UserOut(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        allowed_modules=user.allowed_modules,
    )


@router.put("/users/{user_id}/modules", response_model=UserOut)
async def update_user_modules(
    user_id: str,
    body: UpdateUserModulesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin da conta define quais módulos um agente pode acessar."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admins podem alterar módulos.")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Admin já tem acesso a todos os módulos.")

    if body.allowed_modules is None:
        target.allowed_modules = None
    else:
        from app.core.modules import AVAILABLE_MODULES
        target.allowed_modules = [m for m in body.allowed_modules if m in AVAILABLE_MODULES]
    await db.flush()

    return UserOut(
        id=target.id, tenant_id=target.tenant_id, username=target.username,
        full_name=target.full_name, role=target.role, is_active=target.is_active,
        allowed_modules=target.allowed_modules,
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos os usuários do tenant autenticado."""
    result = await db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id)
    )
    users = result.scalars().all()
    return [
        UserOut(
            id=u.id, tenant_id=u.tenant_id, username=u.username,
            full_name=u.full_name, role=u.role, is_active=u.is_active,
            allowed_modules=u.allowed_modules,
        )
        for u in users
    ]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin desativa um membro da equipe do próprio tenant."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admins podem remover usuários.")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode remover a si mesmo.")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    user.is_active = False
    await db.flush()
