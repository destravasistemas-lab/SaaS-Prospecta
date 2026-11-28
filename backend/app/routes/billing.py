"""
Planos e assinatura do Prospecta (Asaas, cobrança mensal recorrente).

Estas rotas continuam abertas para quem está bloqueado por falta de
pagamento: é por aqui que a pessoa vê o plano e paga.
"""
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_store
from app.core.i18n import t
from app.core.security import get_current_user
from app.models.billing import AIPackPurchase, Plan
from app.services import ai_platform
from app.models.user import User
from app.services import billing
from app.services.asaas_service import asaas_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


class PlanOut(BaseModel):
    code: str
    name: str
    description: str | None = None
    price_cents: int
    limits: dict = {}
    modules: list[str] = []
    extras: list[str] = []
    highlight: bool = False
    # Franquia de IA convertida em atendimentos (média configurada em AI_TOKENS_PER_CONVERSATION)
    ai_conversations: int | None = None
    tokens_per_conversation: int = 0


def plan_out(p: Plan) -> PlanOut:
    limits = p.limits or {}
    return PlanOut(code=p.code, name=p.name, description=p.description, price_cents=p.price_cents,
                   limits=limits, modules=p.modules or [], extras=p.extras or [], highlight=p.highlight,
                   ai_conversations=ai_platform.tokens_to_conversations(limits.get("ai_tokens")),
                   tokens_per_conversation=settings.ai_tokens_per_conversation)


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Planos à venda (público: aparece também na página de preços)."""
    rows = (await db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort, Plan.price_cents))).scalars().all()
    return [plan_out(p) for p in rows]


async def _pending_payment(acc) -> dict | None:
    """Cobrança em aberto (Pix + link da fatura). Confere no Asaas se já foi paga."""
    if not acc or not acc.pending_payment_id or not settings.asaas_api_key:
        return None
    try:
        payment = await asaas_service.get_payment(acc.pending_payment_id)
    except Exception as exc:
        logger.warning("Cobrança %s indisponível no Asaas: %s", acc.pending_payment_id, exc)
        return None
    if payment.get("status") in ("RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"):
        billing.apply_paid(acc, payment.get("dueDate"), payment.get("id"))
        return None
    if payment.get("status") in ("REFUNDED", "DELETED"):
        acc.pending_payment_id = None
        return None
    out = {"payment_id": payment.get("id"), "value": payment.get("value"), "due_date": payment.get("dueDate"),
           "invoice_url": payment.get("invoiceUrl"), "pix_payload": None, "pix_image": None,
           "auto_debit": False}
    # Com o Pix Automático ativo o banco debita no vencimento: a tela não pede para pagar de novo,
    # a não ser que o débito tenha sido recusado ou a cobrança já esteja vencida.
    if acc.pix_auto_status == billing.PIX_AUTO_ACTIVE and payment.get("status") == "PENDING":
        store = await get_store()
        out["auto_debit"] = not await store.get(_refused_key(acc.pending_payment_id))
    try:
        qr = await asaas_service.get_pix_qr(acc.pending_payment_id)
        out["pix_payload"], out["pix_image"] = qr.get("payload"), qr.get("encodedImage")
    except Exception:
        pass
    return out


def _refused_key(payment_id: str) -> str:
    return f"pixauto:refused:{payment_id}"


async def _sync_pix_automatic(acc) -> None:
    """O webhook é o caminho principal. Aqui só consulta o Asaas enquanto não sabemos se foi
    oferecido ou se o cliente ainda não autorizou, no máximo a cada 10 minutos."""
    if not acc or not acc.asaas_subscription_id or not settings.asaas_api_key:
        return
    if acc.pix_auto_status not in (None, billing.PIX_AUTO_OFFERED):
        return
    store = await get_store()
    if not await store.set_nx_ttl(f"pixauto:sync:{acc.id}", "1", 600):
        return
    try:
        auth = await asaas_service.subscription_pix_authorization(acc.asaas_subscription_id)
    except Exception as exc:
        logger.warning("Pix Automático da assinatura %s indisponível: %s", acc.asaas_subscription_id, exc)
        return
    if auth:
        billing.apply_pix_authorization(acc, auth)
    elif acc.pix_auto_status is None:
        acc.pix_auto_status = billing.PIX_AUTO_DISABLED


async def _drop_pix_authorization(acc) -> None:
    """Assinatura trocada ou cancelada: a autorização antiga não fica pendurada no app do banco."""
    if acc.pix_auto_id and acc.pix_auto_status in (billing.PIX_AUTO_OFFERED, billing.PIX_AUTO_ACTIVE):
        try:
            await asaas_service.cancel_pix_authorization(acc.pix_auto_id)
        except Exception as exc:
            logger.warning("Autorização de Pix Automático %s não cancelada: %s", acc.pix_auto_id, exc)
    acc.pix_auto_id = None
    acc.pix_auto_status = None


@router.get("/status")
async def billing_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    acc = await billing.billing_account(db, current_user.tenant_id)
    await _sync_pix_automatic(acc)
    pending = await _pending_payment(acc)
    await db.flush()
    access = billing.compute_access(acc) if acc else billing.Access(billing.STATUS_UNMANAGED, True, None, None)
    plan = await db.get(Plan, acc.billing_plan) if acc and acc.billing_plan else None
    return {
        **billing.summary(access, acc, plan),
        "pending": pending,
        "is_child": bool(acc and acc.id != current_user.tenant_id),
        "trial_days": settings.billing_trial_days,
        "payments_ready": bool(settings.asaas_api_key),
        "pix_automatic": acc.pix_auto_status if acc and acc.asaas_subscription_id else None,
    }


class SubscribeIn(BaseModel):
    plan: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=120)
    document: str = Field(..., min_length=11, max_length=18)


def _require_owner(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(403, t("Só um admin da conta pode mudar o plano.", "Only an account admin can change the plan."))


@router.post("/subscribe")
async def subscribe(
    body: SubscribeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assina (ou troca) o plano. A primeira cobrança vence hoje, ou no fim do período já pago."""
    _require_owner(current_user)
    acc = await billing.billing_account(db, current_user.tenant_id)
    if acc is None or acc.id != current_user.tenant_id:
        raise HTTPException(400, t("A assinatura desta empresa é feita pela agência.", "This company's subscription is handled by the agency."))
    if not settings.asaas_api_key:
        raise HTTPException(503, t("O pagamento ainda não está configurado. Fale com o suporte.", "Payments are not set up yet. Contact support."))
    plan = await db.get(Plan, body.plan)
    if plan is None or not plan.active:
        raise HTTPException(404, t("Plano não encontrado.", "Plan not found."))
    document = re.sub(r"\D", "", body.document)
    if len(document) not in (11, 14):
        raise HTTPException(422, t("Informe um CPF ou CNPJ válido.", "Enter a valid CPF or CNPJ."))

    try:
        if not acc.asaas_customer_id:
            customer = await asaas_service.create_customer(
                name=body.name.strip(), email=acc.customer_email or current_user.username, cpf_cnpj=document,
            )
            acc.asaas_customer_id = customer.get("id")
        if acc.asaas_subscription_id:
            await _drop_pix_authorization(acc)
            try:
                await asaas_service.cancel_subscription(acc.asaas_subscription_id)
            except Exception as exc:
                logger.warning("Assinatura antiga %s não cancelada: %s", acc.asaas_subscription_id, exc)
        today = datetime.now(timezone.utc).date()
        paid_until = billing._aware(acc.paid_until)
        next_due = max(today, paid_until.date()) if paid_until else today
        sub = await asaas_service.create_subscription(
            acc.asaas_customer_id, plan.price_cents / 100, next_due.isoformat(),
            f"Prospecta — plano {plan.name}", external_reference=acc.id,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, t("Não foi possível criar a assinatura agora. Tente de novo em instantes.", "Could not create the subscription right now. Try again shortly."))

    acc.asaas_subscription_id = sub.get("id")
    billing.pix_auto_from_subscription(acc, sub)
    acc.billing_plan = plan.code
    acc.pending_payment_id = None
    if next_due == today:
        try:
            payments = await asaas_service.subscription_payments(acc.asaas_subscription_id)
            first = next((p for p in payments if p.get("status") in ("PENDING", "OVERDUE")), None)
            acc.pending_payment_id = first.get("id") if first else None
        except Exception as exc:
            logger.warning("Primeira cobrança da assinatura %s indisponível: %s", acc.asaas_subscription_id, exc)
    await db.flush()
    logger.info("Conta %s assinou o plano %s", acc.id, plan.code)
    return await billing_status(current_user, db)


@router.post("/cancel")
async def cancel(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancela a renovação. O acesso continua até o fim do período pago."""
    _require_owner(current_user)
    acc = await billing.billing_account(db, current_user.tenant_id)
    if acc is None or acc.id != current_user.tenant_id or not acc.asaas_subscription_id:
        raise HTTPException(400, t("Não há assinatura ativa para cancelar.", "There is no active subscription to cancel."))
    try:
        await asaas_service.cancel_subscription(acc.asaas_subscription_id)
    except Exception as exc:
        logger.warning("Cancelamento da assinatura %s falhou no Asaas: %s", acc.asaas_subscription_id, exc)
        raise HTTPException(502, t("Não foi possível cancelar agora. Tente de novo.", "Could not cancel right now. Try again."))
    await _drop_pix_authorization(acc)
    acc.asaas_subscription_id = None
    acc.pending_payment_id = None
    if acc.billing_status not in (None, billing.STATUS_COURTESY):
        acc.billing_status = billing.STATUS_CANCELED
    await db.flush()
    return await billing_status(current_user, db)



# ---------------------------------------------------------------------------
# Pacote extra de atendimentos com IA (Pix avulso no Asaas)
# ---------------------------------------------------------------------------

class AIPackIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    document: str | None = Field(default=None, max_length=18)


def _pack_info() -> dict:
    return {"conversations": settings.ai_pack_conversations, "price_cents": settings.ai_pack_price_cents,
            "tokens": settings.ai_pack_conversations * settings.ai_tokens_per_conversation}


async def mark_pack_paid(db: AsyncSession, purchase: AIPackPurchase) -> None:
    """Pacote pago: credita os tokens na conta que paga (idempotente)."""
    if purchase.status == "paid":
        return
    from app.models.account import Account
    purchase.status = "paid"
    purchase.paid_at = datetime.now(timezone.utc)
    acc = await db.get(Account, purchase.account_id)
    if acc is not None:
        acc.ai_extra_tokens = int(acc.ai_extra_tokens or 0) + purchase.tokens
    await db.flush()


@router.get("/ai-pack")
async def ai_pack_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preço do pacote e, se houver, o Pix do último pacote ainda não pago."""
    acc = await billing.billing_account(db, current_user.tenant_id)
    pending = None
    if acc is not None:
        purchase = (await db.execute(
            select(AIPackPurchase).where(AIPackPurchase.account_id == acc.id, AIPackPurchase.status == "pending")
            .order_by(AIPackPurchase.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if purchase and purchase.asaas_payment_id and settings.asaas_api_key:
            try:
                payment = await asaas_service.get_payment(purchase.asaas_payment_id)
                if payment.get("status") in ("RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"):
                    await mark_pack_paid(db, purchase)
                elif payment.get("status") in ("REFUNDED", "DELETED"):
                    purchase.status = "canceled"
                else:
                    qr = {}
                    try:
                        qr = await asaas_service.get_pix_qr(purchase.asaas_payment_id)
                    except Exception:
                        pass
                    pending = {"id": purchase.id, "value": purchase.amount, "invoice_url": payment.get("invoiceUrl"),
                               "pix_payload": qr.get("payload"), "pix_image": qr.get("encodedImage")}
            except Exception as exc:
                logger.warning("Pacote de IA %s indisponível no Asaas: %s", purchase.id, exc)
        await db.flush()
    return {**_pack_info(), "pending": pending, "has_customer": bool(acc and acc.asaas_customer_id),
            "is_child": bool(acc and acc.id != current_user.tenant_id)}


@router.post("/ai-pack")
async def buy_ai_pack(
    body: AIPackIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gera o Pix de um pacote extra de atendimentos com IA."""
    _require_owner(current_user)
    acc = await billing.billing_account(db, current_user.tenant_id)
    if acc is None or acc.id != current_user.tenant_id:
        raise HTTPException(400, t("A assinatura desta empresa é feita pela agência.", "This company's subscription is handled by the agency."))
    if not settings.asaas_api_key:
        raise HTTPException(503, t("O pagamento ainda não está configurado. Fale com o suporte.", "Payments are not set up yet. Contact support."))
    info = _pack_info()
    try:
        if not acc.asaas_customer_id:
            document = re.sub(r"\D", "", body.document or "")
            if len(document) not in (11, 14) or not (body.name or "").strip():
                raise HTTPException(422, t("Informe um CPF ou CNPJ válido.", "Enter a valid CPF or CNPJ."))
            customer = await asaas_service.create_customer(
                name=body.name.strip(), email=acc.customer_email or current_user.username, cpf_cnpj=document,
            )
            acc.asaas_customer_id = customer.get("id")
        payment = await asaas_service.create_payment(
            customer_id=acc.asaas_customer_id, value=info["price_cents"] / 100,
            due_date=asaas_service.calculate_due_date(days_ahead=1),
            description=f"Prospecta — +{info['conversations']} atendimentos com IA", billing_type="PIX",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, t("Não foi possível gerar a cobrança agora. Tente de novo em instantes.", "Could not create the charge right now. Try again shortly."))
    db.add(AIPackPurchase(account_id=acc.id, tokens=info["tokens"], amount=info["price_cents"] / 100,
                          asaas_payment_id=payment.get("id")))
    await db.flush()
    return await ai_pack_status(current_user, db)
