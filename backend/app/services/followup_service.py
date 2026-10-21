"""
Follow-up automático no WhatsApp.

Regra: N dias depois de um template enviado sem resposta do cliente, envia o
template de follow-up configurado. Só WhatsApp — o Instagram não permite
mensagens iniciadas pela empresa fora da janela de 24h.

Garantias:
  - no máximo um follow-up por mensagem original (constraint única);
  - nunca segue um follow-up (sem cadeia infinita);
  - só contatos com opt-in e sem opt-out;
  - só dentro da janela de horário da regra (horário local da empresa);
  - envios até 14 dias depois do original.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ws_manager import ws_manager
from app.models.conversation import Conversation
from app.models.followup import FollowUpDispatch, FollowUpRule
from app.models.lead import Lead
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.services import whatsapp_service
from app.services.meta_token_service import decrypt_token

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 14
BATCH_LIMIT = 200  # envios por regra por execução


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def in_send_window(rule: FollowUpRule, now: datetime) -> bool:
    local = now + timedelta(hours=settings.followup_utc_offset_hours)
    return rule.send_hour_start <= local.hour < rule.send_hour_end


async def run_due_followups(db: AsyncSession, now: datetime | None = None) -> int:
    """Executa todas as regras ativas. Retorna quantos follow-ups foram enviados."""
    now = now or datetime.now(timezone.utc)
    rules = (await db.execute(select(FollowUpRule).where(FollowUpRule.enabled.is_(True)))).scalars().all()
    sent = 0
    for rule in rules:
        if not in_send_window(rule, now):
            continue
        try:
            sent += await _run_rule(db, rule, now)
        except Exception as exc:
            logger.warning("Follow-up rule %s failed: %s", rule.id, exc)
    return sent


async def _run_rule(db: AsyncSession, rule: FollowUpRule, now: datetime) -> int:
    conn = (await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == rule.account_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )).scalar_one_or_none()
    if not conn or not conn.phone_number_id:
        return 0

    history = (await db.execute(
        select(FollowUpDispatch.original_message_id, FollowUpDispatch.followup_message_id)
        .where(FollowUpDispatch.account_id == rule.account_id)
    )).all()
    handled = {orig for orig, _ in history}
    followup_ids = {fid for _, fid in history if fid is not None}

    oldest = now - timedelta(days=MAX_AGE_DAYS)
    due_before = now - timedelta(days=rule.delay_days)

    msgs = (await db.execute(
        select(Message).where(
            Message.tenant_id == rule.account_id,
            Message.direction == "outbound",
            Message.template_name.isnot(None),
            Message.created_at >= oldest,
        ).order_by(Message.created_at.desc())
    )).scalars().all()

    # Último template de cada conversa
    latest: dict[str, Message] = {}
    for m in msgs:
        latest.setdefault(m.conversation_id, m)

    token: str | None = None
    sent = 0
    for conv_id, original in latest.items():
        if sent >= BATCH_LIMIT:
            break
        if original.id in handled or original.id in followup_ids:
            continue
        if _aware(original.created_at) > due_before:
            continue
        if rule.trigger_template and original.template_name != rule.trigger_template:
            continue
        if not original.wa_id:
            continue

        replied = (await db.execute(
            select(Message.id).where(
                Message.conversation_id == conv_id,
                Message.direction == "inbound",
                Message.created_at > original.created_at,
            ).limit(1)
        )).first()
        if replied:
            continue

        conv = await db.get(Conversation, conv_id)
        lead = await db.get(Lead, conv.customer_id) if conv and conv.customer_id else None

        dispatch = FollowUpDispatch(
            rule_id=rule.id, account_id=rule.account_id, conversation_id=conv_id,
            original_message_id=original.id, status="sending",
        )
        db.add(dispatch)
        await db.flush()  # constraint única: um follow-up por mensagem original
        handled.add(original.id)

        if lead is None or not lead.can_receive_whatsapp_templates:
            dispatch.status = "skipped"
            dispatch.detail = "opted_out" if lead is not None and lead.whatsapp_opted_out_at else "no_opt_in"
            await db.flush()
            continue

        if token is None:
            token = decrypt_token(conn.access_token_encrypted)
        variables = list(rule.variables or [])
        components = (
            [{"type": "body", "parameters": [{"type": "text", "text": v} for v in variables]}]
            if variables else None
        )
        try:
            resp = await whatsapp_service.send_template(
                token, conn.phone_number_id, original.wa_id,
                rule.template_name, rule.template_language, components,
            )
        except Exception as exc:
            dispatch.status = "failed"
            dispatch.detail = str(exc)[:500]
            await db.flush()
            continue

        wamid = (resp.get("messages") or [{}])[0].get("id")
        if not wamid:
            dispatch.status = "failed"
            dispatch.detail = str(resp.get("error", {}).get("message") or resp)[:500]
            await db.flush()
            continue

        msg = Message(
            tenant_id=rule.account_id, conversation_id=conv_id, sender="followup",
            text=f"[template:{rule.template_name}] {' | '.join(variables)}".strip(),
            direction="outbound", wa_id=original.wa_id, status="sent", message_id=wamid,
            template_name=rule.template_name, template_vars={"variables": variables},
            is_within_24h_window=False, payload={"followup_rule_id": rule.id},
        )
        db.add(msg)
        await db.flush()
        dispatch.status = "sent"
        dispatch.followup_message_id = msg.id
        await db.flush()
        sent += 1

        await ws_manager.broadcast(rule.account_id, "new_message", {
            "id": msg.id, "conversation_id": conv_id, "sender": "followup", "text": msg.text,
            "direction": "outbound", "wa_id": original.wa_id, "status": "sent",
            "message_id": wamid, "template_name": rule.template_name,
            "created_at": msg.created_at.isoformat(),
        })

    if sent:
        logger.info("Follow-up rule %s: %d sent", rule.id, sent)
    return sent
