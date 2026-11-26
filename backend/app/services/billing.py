"""
Cobrança do Prospecta: planos, teste grátis, cortesia e assinatura no Asaas.

Quem tem acesso (em ordem):
  1. billing_status None → conta fora da cobrança (antigas/testes): liberada.
  2. Cortesia do super admin (courtesy_until vazio ou no futuro): liberada, sem cobrança.
  3. Pago até paid_until (+ dias de tolerância): liberada; depois do vencimento
     aparece como "em atraso" até a tolerância acabar.
  4. Teste grátis até trial_ends_at: liberada.
  5. Senão: bloqueada (só vê a tela de Planos), se BILLING_ENFORCED estiver ligado.

Empresas-filhas de uma agência seguem a conta da agência.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.account import Account
from app.models.billing import Plan

ALL_MODULES = ["whatsapp", "instagram", "ads", "ia"]

DEFAULT_PLANS = [
    {"code": "essencial", "name": "Essencial", "price_cents": 14700, "sort": 1, "highlight": False,
     "description": "Atendimento no WhatsApp e no Instagram para um negócio.",
     "limits": {"users": 2, "clients": 0, "ai_tokens": 6_000_000},
     "modules": ["whatsapp", "instagram", "ia"], "extras": []},
    {"code": "profissional", "name": "Profissional", "price_cents": 29700, "sort": 2, "highlight": True,
     "description": "Atendimento, automações e anúncios com retorno por venda.",
     "limits": {"users": 5, "clients": 0, "ai_tokens": 20_000_000},
     "modules": ALL_MODULES, "extras": []},
    {"code": "agencia", "name": "Agência", "price_cents": 59700, "sort": 3, "highlight": False,
     "description": "Para agências que atendem várias empresas.",
     "limits": {"users": 15, "clients": 10, "ai_tokens": 60_000_000},
     "modules": ALL_MODULES, "extras": []},
]

STATUS_COURTESY = "courtesy"
STATUS_TRIAL = "trial"
STATUS_ACTIVE = "active"
STATUS_PAST_DUE = "past_due"
STATUS_CANCELED = "canceled"
STATUS_BLOCKED = "blocked"
STATUS_UNMANAGED = "unmanaged"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


# Franquia de IA da primeira versão dos planos padrão (antes da IA do Prospecta)
_OLD_AI_TOKENS = {"essencial": 1_000_000, "profissional": 3_000_000, "agencia": 10_000_000}


async def seed_plans(db: AsyncSession) -> None:
    """Cria os planos padrão na primeira subida (depois o super admin edita)."""
    existing = {p.code: p for p in (await db.execute(select(Plan))).scalars().all()}
    if not existing:
        for p in DEFAULT_PLANS:
            db.add(Plan(**p))
        await db.flush()
        return
    # Atualiza a franquia de IA só onde ainda está o valor antigo de fábrica
    for d in DEFAULT_PLANS:
        plan = existing.get(d["code"])
        if plan and (plan.limits or {}).get("ai_tokens") == _OLD_AI_TOKENS.get(d["code"]):
            plan.limits = {**(plan.limits or {}), "ai_tokens": d["limits"]["ai_tokens"]}
    await db.flush()


@dataclass
class Access:
    status: str
    allowed: bool
    until: datetime | None
    plan_code: str | None


def compute_access(acc: Account, now: datetime | None = None) -> Access:
    now = now or _now()
    plan = acc.billing_plan
    if acc.billing_status is None:
        return Access(STATUS_UNMANAGED, True, None, plan)
    courtesy_until = _aware(acc.courtesy_until)
    if acc.billing_status == STATUS_COURTESY and (courtesy_until is None or courtesy_until >= now):
        return Access(STATUS_COURTESY, True, courtesy_until, plan)
    paid_until = _aware(acc.paid_until)
    if paid_until and paid_until >= now:
        return Access(STATUS_ACTIVE, True, paid_until, plan)
    if paid_until and paid_until + timedelta(days=settings.billing_grace_days) >= now:
        return Access(STATUS_PAST_DUE, True, paid_until + timedelta(days=settings.billing_grace_days), plan)
    trial = _aware(acc.trial_ends_at)
    if trial and trial >= now:
        return Access(STATUS_TRIAL, True, trial, plan)
    return Access(STATUS_BLOCKED, False, None, plan)


async def billing_account(db: AsyncSession, account_id: str) -> Account | None:
    """A conta que paga: a própria ou a agência-mãe (empresas-filhas)."""
    acc = await db.get(Account, account_id)
    if acc and acc.plan_type == "dependente" and acc.parent_account_id:
        parent = await db.get(Account, acc.parent_account_id)
        return parent or acc
    return acc


async def access_for(db: AsyncSession, account_id: str) -> tuple[Access, Account | None]:
    acc = await billing_account(db, account_id)
    if acc is None:
        return Access(STATUS_UNMANAGED, True, None, None), None
    return compute_access(acc), acc


async def plan_for(db: AsyncSession, account_id: str) -> Plan | None:
    """Plano que vale para os limites. Só conta com a cobrança ligada e conta gerenciada."""
    if not settings.billing_enforced:
        return None
    access, acc = await access_for(db, account_id)
    if acc is None or access.status == STATUS_UNMANAGED or not acc.billing_plan:
        return None
    return await db.get(Plan, acc.billing_plan)


async def plan_limit(db: AsyncSession, account_id: str, key: str) -> int | None:
    plan = await plan_for(db, account_id)
    if plan is None:
        return None
    value = (plan.limits or {}).get(key)
    return int(value) if value is not None else None


async def plan_blocked_modules(db: AsyncSession, account_id: str) -> set[str]:
    plan = await plan_for(db, account_id)
    if plan is None:
        return set()
    return {m for m in ALL_MODULES if m not in (plan.modules or [])}


def start_trial(acc: Account, days: int | None = None) -> None:
    acc.billing_status = STATUS_TRIAL
    acc.trial_ends_at = _now() + timedelta(days=days or settings.billing_trial_days)
    acc.billing_plan = acc.billing_plan or settings.billing_trial_plan


def add_month(ts: datetime) -> datetime:
    month = ts.month + 1
    year = ts.year + (month > 12)
    month = (month - 1) % 12 + 1
    for day in (ts.day, 30, 29, 28):
        try:
            return ts.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return ts + timedelta(days=30)


def apply_paid(acc: Account, due_date: str | None, payment_id: str | None = None) -> None:
    """Pagamento confirmado: libera até um mês depois do vencimento (idempotente)."""
    try:
        due = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc) if due_date else _now()
    except ValueError:
        due = _now()
    until = add_month(due).replace(hour=23, minute=59, second=59)
    current = _aware(acc.paid_until)
    if current is None or until > current:
        acc.paid_until = until
    if acc.billing_status != STATUS_COURTESY:
        acc.billing_status = STATUS_ACTIVE
    if payment_id and acc.pending_payment_id == payment_id:
        acc.pending_payment_id = None


def summary(access: Access, acc: Account | None, plan: Plan | None) -> dict:
    days_left = None
    if access.until is not None:
        days_left = max(0, (access.until - _now()).days)
    return {
        "status": access.status,
        "allowed": access.allowed,
        "enforced": settings.billing_enforced,
        "until": access.until.isoformat() if access.until else None,
        "days_left": days_left,
        "plan": plan.code if plan else access.plan_code,
        "plan_name": plan.name if plan else None,
        "subscribed": bool(acc and acc.asaas_subscription_id),
        "has_pending_payment": bool(acc and acc.pending_payment_id),
    }
