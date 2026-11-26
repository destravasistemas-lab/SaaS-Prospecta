"""
Painel Super Admin — aprovação de cadastros e módulos de QUALQUER conta do sistema.

Acesso restrito a `is_super_admin` (emails em SUPER_ADMIN_EMAILS). Enquanto a
env estiver vazia, ninguém entra (seguro por padrão) — basta adicionar os
emails de vocês para liberar.
"""
import logging
from datetime import date, datetime, time, timezone
from typing import Literal

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
from app.services import billing
from app.models.billing import Plan
from app.routes.billing import PlanOut, plan_out

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
    billing: dict = Field(default_factory=dict)


def _tenant_out(a: Account, user_count: int) -> TenantOut:
    access = billing.compute_access(a)
    return TenantOut(
        billing={**billing.summary(access, a, None), "note": a.billing_note,
                 "trial_ends_at": a.trial_ends_at.isoformat() if a.trial_ends_at else None,
                 "paid_until": a.paid_until.isoformat() if a.paid_until else None},
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
    if body.approved and not was_approved and account.billing_status is None and account.plan_type != "dependente":
        billing.start_trial(account)
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



class BillingAction(BaseModel):
    action: Literal["courtesy", "end_courtesy", "trial", "plan"]
    until: date | None = None
    days: int | None = Field(default=None, ge=1, le=365)
    plan: str | None = None
    note: str | None = Field(default=None, max_length=500)


@router.post("/tenants/{account_id}/billing", response_model=TenantOut)
async def set_tenant_billing(
    account_id: str,
    body: BillingAction,
    admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    courtesy: libera sem cobrança até `until` (vazio = sem prazo).
    end_courtesy: encerra a cortesia (vale o que estiver pago ou em teste).
    trial: dá/estende o teste grátis por `days` dias a partir de hoje.
    plan: muda o plano (limites e módulos) sem mexer no pagamento.
    """
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    if body.plan is not None:
        if await db.get(Plan, body.plan) is None:
            raise HTTPException(status_code=404, detail="Plano não encontrado.")
        account.billing_plan = body.plan
    if body.action == "courtesy":
        account.billing_status = billing.STATUS_COURTESY
        account.courtesy_until = (
            datetime.combine(body.until, time(23, 59, 59), tzinfo=timezone.utc) if body.until else None
        )
    elif body.action == "end_courtesy":
        account.courtesy_until = None
        account.billing_status = billing.STATUS_ACTIVE if account.paid_until else billing.STATUS_TRIAL
    elif body.action == "trial":
        billing.start_trial(account, body.days)
        account.courtesy_until = None
    if body.note is not None:
        account.billing_note = body.note.strip() or None
    await db.flush()
    logger.info("Super admin %s mudou a cobrança da conta %s: %s", admin.username, account_id, body.action)
    count = (await db.execute(select(func.count(User.id)).where(User.tenant_id == account_id))).scalar() or 0
    return _tenant_out(account, int(count))


class PlanIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    price_cents: int = Field(..., ge=0, le=100_000_000)
    limits: dict[str, int | None] = Field(default_factory=dict)
    modules: list[str] = Field(default_factory=list)
    extras: list[str] = Field(default_factory=list, max_length=12)
    highlight: bool = False
    active: bool = True
    sort: int = 0


class AdminPlanOut(PlanOut):
    active: bool = True
    sort: int = 0


@router.get("/plans", response_model=list[AdminPlanOut])
async def admin_list_plans(_: User = Depends(_require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Plan).order_by(Plan.sort, Plan.price_cents))).scalars().all()
    return [AdminPlanOut(**plan_out(p).model_dump(), active=p.active, sort=p.sort) for p in rows]


@router.put("/plans/{code}", response_model=AdminPlanOut)
async def admin_save_plan(
    code: str,
    body: PlanIn,
    admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Cria ou edita um plano. O preço novo vale para as próximas assinaturas."""
    if not code.isidentifier() or len(code) > 30:
        raise HTTPException(status_code=422, detail="Código inválido: use letras, números e _.")
    plan = await db.get(Plan, code)
    if plan is None:
        plan = Plan(code=code)
        db.add(plan)
    plan.name = body.name.strip()
    plan.description = (body.description or "").strip() or None
    plan.price_cents = body.price_cents
    plan.limits = {k: v for k, v in body.limits.items() if k in ("users", "clients", "ai_tokens")}
    plan.modules = [m for m in body.modules if m in billing.ALL_MODULES]
    plan.extras = [e.strip() for e in body.extras if e.strip()]
    plan.highlight = body.highlight
    plan.active = body.active
    plan.sort = body.sort
    await db.flush()
    logger.info("Super admin %s salvou o plano %s", admin.username, code)
    return AdminPlanOut(**plan_out(plan).model_dump(), active=plan.active, sort=plan.sort)


@router.get("/ai-usage")
async def admin_ai_usage(
    days: int = 30,
    _: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Consumo da IA do Prospecta: custo estimado, 429, espera na fila e as contas que mais gastam."""
    from datetime import timedelta
    from app.core.config import settings
    from app.models.ai import AIUsageDay
    from app.services import ai_platform

    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    rows = (await db.execute(select(AIUsageDay).where(AIUsageDay.day >= since))).scalars().all()

    def platform_cost(r) -> float:
        share = (r.platform_tokens or 0) / r.tokens if r.tokens else 0
        return ai_platform.cost_brl(int((r.input_tokens or 0) * share), int((r.output_tokens or 0) * share))

    per_account: dict[str, dict] = {}
    for r in rows:
        a = per_account.setdefault(r.account_id, {"tokens": 0, "platform_tokens": 0, "replies": 0, "fallbacks": 0,
                                                  "rate_limited": 0, "cost": 0.0})
        a["tokens"] += r.tokens or 0
        a["platform_tokens"] += r.platform_tokens or 0
        a["replies"] += r.messages or 0
        a["fallbacks"] += r.fallbacks or 0
        a["rate_limited"] += r.rate_limited or 0
        a["cost"] += platform_cost(r)
    names = dict((await db.execute(
        select(Account.id, Account.brand_name).where(Account.id.in_(list(per_account) or [""]))
    )).all())
    replies = sum(a["replies"] for a in per_account.values())
    top = sorted(per_account.items(), key=lambda kv: kv[1]["platform_tokens"], reverse=True)[:20]
    return {
        "days": days,
        "keys": len(ai_platform.platform_keys()),
        "limits": {"key_rpm": settings.ai_key_rpm, "account_rpm": settings.ai_account_rpm,
                   "slot_wait_seconds": settings.ai_slot_wait_seconds,
                   "tokens_per_conversation": settings.ai_tokens_per_conversation},
        "totals": {
            "replies": replies,
            "fallbacks": sum(a["fallbacks"] for a in per_account.values()),
            "rate_limited": sum(a["rate_limited"] for a in per_account.values()),
            "platform_tokens": sum(a["platform_tokens"] for a in per_account.values()),
            "cost_brl": round(sum(a["cost"] for a in per_account.values()), 2),
            "avg_wait_ms": int(sum(r.queue_wait_ms or 0 for r in rows) / replies) if replies else 0,
        },
        "accounts": [
            {"account_id": aid, "name": names.get(aid) or aid, **{k: (round(v, 2) if k == "cost" else v) for k, v in a.items()},
             "conversations": ai_platform.tokens_to_conversations(a["platform_tokens"])}
            for aid, a in top
        ],
    }
