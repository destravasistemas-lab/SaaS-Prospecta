"""
Painel Super Admin — aprovação de cadastros e módulos de QUALQUER conta do sistema.

Acesso restrito a `is_super_admin` (emails em SUPER_ADMIN_EMAILS). Enquanto a
env estiver vazia, ninguém entra (seguro por padrão) — basta adicionar os
emails de vocês para liberar.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.modules import is_super_admin, AVAILABLE_MODULES
from app.models.account import Account, APPROVAL_APPROVED, APPROVAL_PENDING, APPROVAL_REJECTED
from app.models.user import User
from app.services.email_service import send_account_approved_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["super-admin"])


def _require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito.")
    return current_user


class TenantOut(BaseModel):
    id: str
    brand_name: str | None
    plan_type: str | None
    parent_account_id: str | None
    blocked_modules: list[str] = Field(default_factory=list)
    user_count: int = 0
    approval_status: str = APPROVAL_APPROVED
    owner_email: str | None = None
    owner_name: str | None = None
    created_at: datetime | None = None


def _tenant_out(a: Account, user_count: int) -> TenantOut:
    return TenantOut(
        id=a.id, brand_name=a.brand_name, plan_type=a.plan_type,
        parent_account_id=a.parent_account_id,
        blocked_modules=list(a.blocked_modules or []), user_count=user_count,
        approval_status=a.approval_status or APPROVAL_APPROVED,
        owner_email=a.customer_email, owner_name=a.customer_name, created_at=a.created_at,
    )


class ApprovalRequest(BaseModel):
    approved: bool


class TenantModulesRequest(BaseModel):
    blocked_modules: list[str] = Field(default_factory=list)


@router.get("/modules-catalog")
async def modules_catalog(_: User = Depends(_require_super_admin)):
    """Catálogo de módulos disponíveis (chave → descrição)."""
    return AVAILABLE_MODULES


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(
    _: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lista TODAS as contas do sistema com seus módulos bloqueados."""
    counts = dict(
        (await db.execute(
            select(User.tenant_id, func.count(User.id)).group_by(User.tenant_id)
        )).all()
    )
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    accounts = result.scalars().all()
    # Pendentes primeiro: são o que o super admin precisa resolver.
    accounts = sorted(accounts, key=lambda a: a.approval_status != APPROVAL_PENDING)
    return [_tenant_out(a, int(counts.get(a.id, 0))) for a in accounts]


@router.post("/tenants/{account_id}/approval", response_model=TenantOut)
async def set_tenant_approval(
    account_id: str,
    body: ApprovalRequest,
    admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Libera ou recusa o acesso de um cadastro. As empresas-filhas seguem a conta-mãe."""
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    was_approved = account.approval_status == APPROVAL_APPROVED
    account.approval_status = APPROVAL_APPROVED if body.approved else APPROVAL_REJECTED
    account.approved_at = datetime.now(timezone.utc) if body.approved else None
    children = (await db.execute(select(Account).where(Account.parent_account_id == account_id))).scalars().all()
    for child in children:
        child.approval_status = account.approval_status
        child.approved_at = account.approved_at
    await db.flush()
    logger.info("Super admin %s %s a conta %s", admin.username,
                "aprovou" if body.approved else "recusou", account_id)

    if body.approved and not was_approved and account.customer_email:
        await send_account_approved_email(account.customer_email, account.customer_name or account.brand_name)

    count = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == account_id)
    )).scalar() or 0
    return _tenant_out(account, int(count))


@router.put("/tenants/{account_id}/modules", response_model=TenantOut)
async def set_tenant_modules(
    account_id: str,
    body: TenantModulesRequest,
    admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Define os módulos bloqueados de qualquer conta."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    account.blocked_modules = sorted({m for m in body.blocked_modules if m in AVAILABLE_MODULES})
    await db.flush()
    logger.info("Super admin %s alterou módulos da conta %s: bloqueados=%s",
                admin.username, account_id, account.blocked_modules)

    count = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == account_id)
    )).scalar() or 0
    return _tenant_out(account, int(count))
