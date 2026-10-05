import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, desc

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.ws_manager import ws_manager
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.meta_connection import (
    MetaConnection, PROVIDER_WHATSAPP, PROVIDER_INSTAGRAM, STATUS_ACTIVE,
)
from app.services.meta_token_service import decrypt_token
from app.services import whatsapp_service, instagram_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations/{conv_id}/messages", tags=["messages"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MessageOut(BaseModel):
    id: int
    tenant_id: str
    conversation_id: str
    sender: str
    text: str | None
    direction: str
    wa_id: str | None
    status: str
    message_id: str | None
    media_type: str | None
    media_url: str | None
    context_text: str | None
    meta_category: str | None
    meta_cost: float | None
    is_within_24h_window: bool
    template_vars: dict | None
    template_name: str | None
    payload: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    text: str | None = None
    direction: str = "outbound"
    sender: str | None = None
    wa_id: str | None = None
    media_type: str | None = None
    media_url: str | None = None
    # Mídia enviada via POST /whatsapp/media/upload (envio por Media ID)
    media_id: str | None = None
    media_filename: str | None = None
    # ID (do banco) da mensagem sendo respondida — vira quote no WhatsApp
    reply_to_message_id: int | None = None
    template_name: str | None = None
    template_vars: dict | None = None
    message_id: str | None = None
    payload: dict | None = None


# Janela de atendimento do WhatsApp: 24h após a última mensagem do cliente
WA_SESSION_WINDOW = timedelta(hours=24)


async def _last_inbound_at(conv_id: str, db: AsyncSession) -> datetime | None:
    result = await db.execute(
        select(Message.created_at).where(
            Message.conversation_id == conv_id,
            Message.direction == "inbound",
        ).order_by(desc(Message.created_at)).limit(1)
    )
    row = result.first()
    if not row:
        return None
    ts = row[0]
    # SQLite (testes) devolve datetime naive — normaliza para UTC
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[MessageOut])
async def list_messages(
    conv_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_conv_access(conv_id, current_user.tenant_id, db)

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id, Message.tenant_id == current_user.tenant_id)
        .order_by(asc(Message.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=MessageOut, status_code=201)
async def send_message(
    conv_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_conv(conv_id, current_user.tenant_id, db)

    sender = body.sender or current_user.username
    status = "sent"
    message_id = body.message_id
    wa_id = body.wa_id
    media_url = body.media_url
    context_text: str | None = None
    within_window = True

    # Envio real via Graph API (apenas mensagens outbound) — o canal da
    # conversa decide se vai pelo WhatsApp Cloud API ou pela Instagram
    # Messaging API, já que as duas têm regras e payloads bem diferentes.
    if body.direction == "outbound":
        # Destinatário: wa_id do body ou o handle do lead (o webhook grava o wa_id/PSID ali).
        if not wa_id and conv.customer_id:
            lead = await db.get(Lead, conv.customer_id)
            wa_id = lead.instagram_handle if lead else None

        if conv.channel == "instagram":
            message_id, status = await _send_instagram_outbound(
                conv_id, current_user.tenant_id, wa_id, body, db
            )
        else:
            message_id, status, media_url, context_text, within_window = await _send_whatsapp_outbound(
                conv_id, current_user.tenant_id, wa_id, body, db
            )

    payload = body.payload
    if body.media_filename:
        payload = {**(payload or {}), "filename": body.media_filename}

    msg = Message(
        tenant_id=current_user.tenant_id,
        conversation_id=conv_id,
        sender=sender,
        text=body.text,
        direction=body.direction,
        wa_id=wa_id,
        status=status,
        message_id=message_id,
        media_type=body.media_type,
        media_url=media_url,
        context_text=context_text,
        is_within_24h_window=within_window,
        template_name=body.template_name,
        template_vars=body.template_vars,
        payload=payload,
    )
    db.add(msg)
    await db.flush()

    # Toca a conversa (ordena no topo da lista)
    conv.last_updated = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(msg)

    await ws_manager.broadcast(
        current_user.tenant_id,
        "new_message",
        MessageOut.model_validate(msg).model_dump(),
    )
    return msg


@router.patch("/{msg_id}/status", response_model=MessageOut)
async def update_message_status(
    conv_id: str,
    msg_id: int,
    new_status: str = Query(..., pattern="^(sent|delivered|read|failed)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_conv_access(conv_id, current_user.tenant_id, db)

    result = await db.execute(
        select(Message).where(Message.id == msg_id, Message.conversation_id == conv_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")

    msg.status = new_status
    await db.flush()
    await db.refresh(msg)

    await ws_manager.broadcast(
        current_user.tenant_id,
        "message_status_updated",
        {"id": msg.id, "status": msg.status, "conversation_id": conv_id},
    )
    return msg


async def _send_whatsapp_outbound(
    conv_id: str, tenant_id: str, wa_id: str | None, body: SendMessageRequest, db: AsyncSession,
) -> tuple[str | None, str, str | None, str | None, bool]:
    """Returns (message_id, status, media_url, context_text, within_window)."""
    message_id = body.message_id
    status = "sent"
    media_url = body.media_url
    context_text: str | None = None

    conn = (
        await db.execute(
            select(MetaConnection).where(
                MetaConnection.account_id == tenant_id,
                MetaConnection.provider == PROVIDER_WHATSAPP,
                MetaConnection.status == STATUS_ACTIVE,
            )
        )
    ).scalar_one_or_none()

    # Janela de 24h: mensagem livre só pode ser enviada se o cliente
    # respondeu nas últimas 24h. Fora dela, a Meta rejeita — orienta a
    # usar template em vez de deixar falhar silenciosamente.
    within_window = True
    if conn and wa_id:
        last_inbound = await _last_inbound_at(conv_id, db)
        within_window = (
            last_inbound is not None
            and datetime.now(timezone.utc) - last_inbound < WA_SESSION_WINDOW
        )
        if not within_window and not body.template_name:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "outside_24h_window",
                    "message": (
                        "Janela de 24h expirada — o cliente não responde há mais de "
                        "24 horas. Envie um template aprovado para reabrir a conversa."
                    ),
                },
            )

    # Reply (quote): resolve o wamid e o texto da mensagem citada
    reply_to_wamid: str | None = None
    if body.reply_to_message_id:
        target = (
            await db.execute(
                select(Message).where(
                    Message.id == body.reply_to_message_id,
                    Message.conversation_id == conv_id,
                    Message.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if target:
            reply_to_wamid = target.message_id
            context_text = target.text or f"[{target.media_type or 'mídia'}]"

    if conn and wa_id and (body.text or body.media_url or body.media_id):
        try:
            token = decrypt_token(conn.access_token_encrypted)
            if body.media_id and body.media_type:
                resp = await whatsapp_service.send_media_by_id(
                    token, conn.phone_number_id, wa_id,
                    body.media_type, body.media_id,
                    caption=body.text, filename=body.media_filename,
                    reply_to=reply_to_wamid,
                )
                # Guarda o caminho do proxy para exibir a mídia no chat
                media_url = f"/whatsapp/media/{body.media_id}"
            elif body.media_type and body.media_url:
                resp = await whatsapp_service.send_media(
                    token, conn.phone_number_id, wa_id,
                    body.media_type, body.media_url, body.text,
                )
            else:
                resp = await whatsapp_service.send_text(
                    token, conn.phone_number_id, wa_id, body.text or "",
                    reply_to=reply_to_wamid,
                )
            sent_id = (resp.get("messages") or [{}])[0].get("id")
            if sent_id:
                message_id = sent_id
            else:
                status = "failed"
                logger.warning("Envio WhatsApp sem wamid (conv=%s): %s", conv_id, resp)
        except Exception as exc:
            status = "failed"
            logger.warning("Falha ao enviar WhatsApp (conv=%s): %s", conv_id, exc)
    elif not conn:
        logger.info(
            "Sem conexão WhatsApp ativa — mensagem apenas armazenada (conv=%s)", conv_id
        )

    return message_id, status, media_url, context_text, within_window


async def _send_instagram_outbound(
    conv_id: str, tenant_id: str, recipient_id: str | None, body: SendMessageRequest, db: AsyncSession,
) -> tuple[str | None, str]:
    """
    Returns (message_id, status). MVP: texto apenas — a Instagram Messaging
    API suporta envio de mídia por anexo, mas isso fica para uma iteração
    futura (hoje só recebemos e exibimos mídia enviada pelo cliente).
    """
    message_id = body.message_id
    status = "sent"

    if not body.text:
        raise HTTPException(422, "Envio de mídia pelo Instagram ainda não é suportado — apenas texto.")

    conn = (
        await db.execute(
            select(MetaConnection).where(
                MetaConnection.account_id == tenant_id,
                MetaConnection.provider == PROVIDER_INSTAGRAM,
                MetaConnection.status == STATUS_ACTIVE,
            )
        )
    ).scalar_one_or_none()

    if conn and recipient_id:
        try:
            token = decrypt_token(conn.access_token_encrypted)
            resp = await instagram_service.send_dm(token, recipient_id, body.text)
            sent_id = resp.get("message_id")
            if sent_id:
                message_id = sent_id
            else:
                status = "failed"
                logger.warning("Envio Instagram sem message_id (conv=%s): %s", conv_id, resp)
        except Exception as exc:
            status = "failed"
            logger.warning("Falha ao enviar DM Instagram (conv=%s): %s", conv_id, exc)
    elif not conn:
        logger.info(
            "Sem conexão Instagram ativa — mensagem apenas armazenada (conv=%s)", conv_id
        )

    return message_id, status


async def _get_conv(conv_id: str, tenant_id: str, db: AsyncSession) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.tenant_id == tenant_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return conv


async def _assert_conv_access(conv_id: str, tenant_id: str, db: AsyncSession) -> None:
    await _get_conv(conv_id, tenant_id, db)
