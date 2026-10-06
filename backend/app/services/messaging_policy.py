"""
Meta messaging policy rules shared by WhatsApp and Instagram routes.

WhatsApp Business Messaging Policy:
  - Free-form messages only inside the 24h customer service window (opened by
    the customer's last message). Outside it, only approved templates.
  - Business-initiated (template) messages only to people who opted in, and
    opt-out requests must be honored.

Instagram Messaging (Messenger Platform):
  - Replies only within 24h of the user's last message. Comment → DM uses
    Private Replies (one per comment, within 7 days).
"""
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.models.lead import Lead
from app.models.message import Message

SERVICE_WINDOW = timedelta(hours=24)

OPT_OUT_KEYWORDS = {
    "stop", "unsubscribe", "cancel", "opt out", "optout",
    "parar", "pare", "sair", "cancelar", "descadastrar", "nao quero mais",
}
OPT_IN_KEYWORDS = {"start", "subscribe", "opt in", "optin", "voltar", "aceito"}

OPT_OUT_CONFIRMATION = {
    "pt": "Pronto! Você não receberá mais mensagens promocionais nossas por aqui. "
          "Se mudar de ideia, envie VOLTAR.",
    "en": "Done! You won't receive promotional messages from us here anymore. "
          "If you change your mind, reply START.",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


def is_opt_out(text: str | None) -> bool:
    return bool(text) and _normalize(text) in OPT_OUT_KEYWORDS


def is_opt_in(text: str | None) -> bool:
    return bool(text) and _normalize(text) in OPT_IN_KEYWORDS


def opt_out_reply(text: str) -> str:
    return OPT_OUT_CONFIRMATION["en" if _normalize(text) in {
        "stop", "unsubscribe", "cancel", "opt out", "optout"
    } else "pt"]


def _aware(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


async def last_inbound_at(
    db: AsyncSession, tenant_id: str, *, conv_id: str | None = None, sender_id: str | None = None,
) -> datetime | None:
    """Timestamp of the customer's last message (by conversation or by wa_id/IGSID)."""
    q = select(Message.created_at).where(
        Message.tenant_id == tenant_id, Message.direction == "inbound",
    )
    if conv_id:
        q = q.where(Message.conversation_id == conv_id)
    elif sender_id:
        q = q.where(Message.wa_id == sender_id)
    else:
        return None
    row = (await db.execute(q.order_by(desc(Message.created_at)).limit(1))).first()
    return _aware(row[0]) if row else None


async def is_within_window(
    db: AsyncSession, tenant_id: str, *, conv_id: str | None = None, sender_id: str | None = None,
) -> bool:
    last = await last_inbound_at(db, tenant_id, conv_id=conv_id, sender_id=sender_id)
    return bool(last) and datetime.now(timezone.utc) - last <= SERVICE_WINDOW


async def require_whatsapp_window(
    db: AsyncSession, tenant_id: str, *, conv_id: str | None = None, sender_id: str | None = None,
) -> None:
    if not await is_within_window(db, tenant_id, conv_id=conv_id, sender_id=sender_id):
        raise HTTPException(422, detail={
            "code": "outside_24h_window",
            "message": t(
                "Janela de 24h expirada — o cliente não responde há mais de 24 horas. "
                "Envie um template aprovado para reabrir a conversa.",
                "24-hour window expired — the customer hasn't replied in over 24 hours. "
                "Send an approved template to reopen the conversation.",
            ),
        })


async def require_instagram_window(
    db: AsyncSession, tenant_id: str, *, conv_id: str | None = None, sender_id: str | None = None,
) -> None:
    if not await is_within_window(db, tenant_id, conv_id=conv_id, sender_id=sender_id):
        raise HTTPException(422, detail={
            "code": "outside_24h_window",
            "message": t(
                "O Instagram só permite responder em até 24h após a última mensagem do cliente.",
                "Instagram only allows replies within 24 hours of the customer's last message.",
            ),
        })


def require_template_consent(lead: Lead | None) -> None:
    """Templates (business-initiated) require opt-in and no opt-out."""
    if lead is not None and lead.whatsapp_opted_out_at is not None:
        raise HTTPException(409, detail={
            "code": "opted_out",
            "message": t(
                "Este contato pediu para não receber mensagens (opt-out).",
                "This contact asked not to receive messages (opted out).",
            ),
        })
    if lead is None or not lead.whatsapp_opt_in:
        raise HTTPException(422, detail={
            "code": "opt_in_required",
            "message": t(
                "Este contato não tem opt-in registrado para WhatsApp. Registre o consentimento antes de enviar um template.",
                "This contact has no WhatsApp opt-in on record. Record their consent before sending a template.",
            ),
        })


def mark_opt_in(lead: Lead, source: str) -> None:
    lead.whatsapp_opt_in = True
    lead.whatsapp_opt_in_at = datetime.now(timezone.utc)
    lead.whatsapp_opt_in_source = source
    lead.whatsapp_opted_out_at = None


def mark_opt_out(lead: Lead) -> None:
    lead.whatsapp_opt_in = False
    lead.whatsapp_opted_out_at = datetime.now(timezone.utc)
