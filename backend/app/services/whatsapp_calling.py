"""
Chamadas de voz do WhatsApp (Calling API): webhook `calls`, quem toca e o histórico.

O áudio vai direto do navegador do atendente para a Meta (WebRTC); o backend só faz
a sinalização. O SDP carrega credenciais ICE e a impressão digital DTLS: fica
criptografado só enquanto a chamada toca e nunca entra em log, evento WS ou payload.

A Meta não garante ordem nem entrega única: o `terminate` pode chegar antes do
`connect` e os dois podem repetir. Cada evento é aplicado sobre a linha única de
(tenant_id, wa_call_id), então repetir um evento não muda o resultado.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.modules import users_with_module
from app.core.ws_manager import ws_manager
from app.models.conversation import Conversation
from app.models.lead import LeadSource
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.whatsapp_call import (
    CALL_CLAIMED, CALL_COMPLETED, CALL_ENDED, CALL_FAILED, CALL_MISSED, CALL_REJECTED, CALL_RINGING,
    DIRECTION_INBOUND, WhatsAppCall,
)
from app.services.lead_identity import resolve_or_create_lead
from app.services.meta_token_service import encrypt_token

logger = logging.getLogger(__name__)

CALL_MEDIA_TYPE = "call"
USER_INITIATED = "USER_INITIATED"

Notification = tuple[str, dict]


def ice_servers() -> list[dict]:
    """Servidores STUN/TURN opcionais (a Meta não fornece nem exige)."""
    if not settings.webrtc_ice_servers:
        return []
    try:
        servers = json.loads(settings.webrtc_ice_servers)
    except ValueError:
        logger.warning("WEBRTC_ICE_SERVERS não é um JSON válido; seguindo sem servidores ICE")
        return []
    return servers if isinstance(servers, list) else []


def call_view(call: WhatsAppCall) -> dict:
    """Dados da chamada para o histórico e para os eventos (sem SDP)."""
    return {
        "id": call.id,
        "direction": call.direction,
        "status": call.status,
        "duration_seconds": call.duration_seconds,
        "answered_by": call.answered_by_name,
        "rejected_by": call.rejected_by_name,
        "error_code": call.error_code,
    }


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def is_ringing(call: WhatsAppCall, now: datetime | None = None) -> bool:
    return call.status == CALL_RINGING and _aware(call.ring_expires_at) > (now or datetime.now(timezone.utc))


def display_status(call: WhatsAppCall) -> str:
    """Se o terminate se perder, a chamada não pode ficar "tocando" para sempre."""
    if call.status in (CALL_RINGING, CALL_CLAIMED) and _aware(call.ring_expires_at) <= datetime.now(timezone.utc):
        return CALL_MISSED
    return call.status


def _timestamp(raw) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _seconds(raw) -> int | None:
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return None


async def ring_delay_ms(conv: Conversation | None, user_id: str, call: WhatsAppCall) -> int:
    """Conversa com atendente online: toca nele primeiro e nos demais depois da espera."""
    owner = conv.atendente_id if conv else None
    if not owner or owner == user_id or not await ws_manager.is_online(owner):
        return 0
    elapsed = datetime.now(timezone.utc) - _aware(call.created_at)
    wait = timedelta(seconds=settings.whatsapp_call_escalation_seconds) - elapsed
    return max(0, int(wait.total_seconds() * 1000))


def incoming_view(call: WhatsAppCall, delay_ms: int) -> dict:
    return {
        "id": call.id,
        "conversation_id": call.conversation_id,
        "contact_name": call.contact_name,
        "contact_wa_id": call.contact_wa_id,
        "ring_after_ms": delay_ms,
        "expires_at": _aware(call.ring_expires_at).isoformat(),
    }


async def _connection_for_number(phone_number_id: str, db: AsyncSession) -> MetaConnection | None:
    conns = (await db.execute(
        select(MetaConnection).where(
            MetaConnection.phone_number_id == phone_number_id,
            MetaConnection.provider == PROVIDER_WHATSAPP,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )).scalars().all()
    if len(conns) != 1:
        # Número em dois clientes: tocar para qualquer um deles vazaria a chamada.
        logger.warning("Chamada ignorada: %d conexões ativas para o número %s", len(conns), phone_number_id)
        return None
    return conns[0]


def _contact_names(value: dict) -> dict[str, str | None]:
    names: dict[str, str | None] = {}
    for contact in value.get("contacts") or []:
        name = (contact.get("profile") or {}).get("name")
        for key in (contact.get("wa_id"), contact.get("user_id")):
            if key:
                names[key] = name
    return names


async def _create_call(
    event: dict, names: dict[str, str | None], tenant_id: str, db: AsyncSession,
) -> tuple[WhatsAppCall, Conversation, Message]:
    from app.routes.webhook import _get_or_create_conversation

    phone = event.get("from")
    contact = phone or event.get("from_user_id")
    name = names.get(contact)
    lead = await resolve_or_create_lead(
        db, tenant_id, external_id=contact, phone=phone, name=name, source=LeadSource.INSTAGRAM_DM,
    )
    conv = await _get_or_create_conversation(tenant_id, lead.id, "whatsapp", db)

    created_at = _timestamp(event.get("timestamp")) or datetime.now(timezone.utc)
    call = WhatsAppCall(
        tenant_id=tenant_id,
        conversation_id=conv.id,
        lead_id=lead.id,
        wa_call_id=event["id"],
        direction=DIRECTION_INBOUND,
        status=CALL_RINGING,
        contact_wa_id=contact,
        contact_name=name or lead.name,
        created_at=created_at,
        ring_expires_at=created_at + timedelta(seconds=settings.whatsapp_call_ring_seconds),
    )
    db.add(call)
    await db.flush()

    # direction="inbound" reabre a janela de 24h: a Meta conta a chamada atendida ou não.
    msg = Message(
        tenant_id=tenant_id,
        conversation_id=conv.id,
        sender=contact or "whatsapp",
        text=None,
        direction="inbound",
        wa_id=contact,
        status="delivered",
        media_type=CALL_MEDIA_TYPE,
        payload={"call": call_view(call)},
        is_within_24h_window=True,
        created_at=created_at,
    )
    db.add(msg)
    conv.last_updated = datetime.now(timezone.utc)
    conv.atendimento_status = "aberto"
    await db.flush()
    await db.refresh(msg)
    call.message_db_id = msg.id
    await db.flush()
    return call, conv, msg


def _new_message_event(msg: Message) -> Notification:
    return "new_message", {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "wa_id": msg.wa_id,
        "sender": msg.sender,
        "text": None,
        "media_type": CALL_MEDIA_TYPE,
        "payload": msg.payload,
        "direction": msg.direction,
        "status": msg.status,
        "created_at": msg.created_at.isoformat(),
    }


def conversation_event(conv: Conversation) -> Notification:
    return "conversation_updated", {
        "id": conv.id,
        "unread_count": conv.unread_count,
        "atendimento_status": conv.atendimento_status,
        "atendente_id": conv.atendente_id,
        "bot_active": conv.bot_active,
        "last_updated": conv.last_updated.isoformat(),
    }


def call_updated_event(call: WhatsAppCall) -> Notification:
    return "call_updated", {
        "id": call.id,
        "conversation_id": call.conversation_id,
        "message_db_id": call.message_db_id,
        "call": call_view(call),
    }


async def sync_history(call: WhatsAppCall, db: AsyncSession) -> None:
    """Reflete o estado da chamada na linha do histórico da conversa."""
    if call.message_db_id is None:
        return
    msg = await db.get(Message, call.message_db_id)
    if msg:
        msg.payload = {"call": call_view(call)}


async def finish_call(
    call: WhatsAppCall,
    status: str,
    db: AsyncSession,
    *,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    duration: int | None = None,
    error_code: int | None = None,
) -> list[Notification]:
    was_open = call.status not in CALL_ENDED
    call.status = status
    call.sdp_offer_encrypted = None
    call.started_at = started_at or call.started_at
    call.ended_at = ended_at or call.ended_at or datetime.now(timezone.utc)
    call.duration_seconds = duration if duration is not None else call.duration_seconds
    call.error_code = error_code if error_code is not None else call.error_code
    await sync_history(call, db)

    events = [call_updated_event(call)]
    if was_open and status in (CALL_MISSED, CALL_FAILED):
        conv = await db.get(Conversation, call.conversation_id)
        if conv:
            conv.unread_count = (conv.unread_count or 0) + 1
            conv.last_updated = datetime.now(timezone.utc)
            events.append(conversation_event(conv))
    await db.flush()
    return events


def _error_code(event: dict, value: dict) -> int | None:
    errors = event.get("errors") or value.get("errors") or []
    code = errors[0].get("code") if errors and isinstance(errors[0], dict) else None
    return code if isinstance(code, int) else None


async def _apply_terminate(call: WhatsAppCall, event: dict, value: dict, db: AsyncSession) -> list[Notification]:
    duration = _seconds(event.get("duration"))
    started_at = _timestamp(event.get("start_time"))
    ended_at = _timestamp(event.get("end_time")) or _timestamp(event.get("timestamp"))

    if (event.get("status") or "").upper() == "FAILED":
        status = CALL_FAILED
    elif duration is not None or started_at:
        status = CALL_COMPLETED
    elif call.status == CALL_REJECTED:
        status = CALL_REJECTED
    else:
        # A Meta marca como COMPLETED também quem não atendeu; sem duração, ninguém falou.
        status = CALL_MISSED
    return await finish_call(
        call, status, db, started_at=started_at, ended_at=ended_at, duration=duration,
        error_code=_error_code(event, value),
    )


async def _apply_event(
    event: dict, value: dict, names: dict[str, str | None], tenant_id: str, db: AsyncSession,
) -> tuple[list[Notification], tuple[WhatsAppCall, Conversation] | None]:
    """Aplica um evento. Devolve o que notificar e, se for tocar, a chamada."""
    kind = event.get("event")
    if kind not in ("connect", "terminate"):
        return [], None

    call = (await db.execute(
        select(WhatsAppCall).where(
            WhatsAppCall.tenant_id == tenant_id, WhatsAppCall.wa_call_id == event["id"],
        )
    )).scalar_one_or_none()

    events: list[Notification] = []
    conv: Conversation | None = None
    created = call is None
    if created:
        call, conv, msg = await _create_call(event, names, tenant_id, db)
        events += [_new_message_event(msg), conversation_event(conv)]

    if kind == "terminate":
        return events + await _apply_terminate(call, event, value, db), None

    # connect repetido, ou depois do terminate: já foi tratado.
    if not created:
        return events, None

    sdp = (event.get("session") or {}).get("sdp")
    if not sdp or not is_ringing(call):
        return events + await finish_call(call, CALL_MISSED, db), None

    call.sdp_offer_encrypted = encrypt_token(sdp)
    await db.flush()
    return events, (call, conv)


async def notify(tenant_id: str, user_ids: list[str], events: list[Notification]) -> None:
    for event_type, data in events:
        await ws_manager.send_to_users(tenant_id, user_ids, event_type, data)


async def _ring(call: WhatsAppCall, conv: Conversation, user_ids: list[str]) -> None:
    for user_id in user_ids:
        delay = await ring_delay_ms(conv, user_id, call)
        await ws_manager.send_to_users(call.tenant_id, [user_id], "call_incoming", incoming_view(call, delay))


async def handle_calls_webhook(value: dict, db: AsyncSession) -> None:
    """Campo `calls` do webhook. Só chamadas recebidas (USER_INITIATED)."""
    if not settings.whatsapp_calling_enabled:
        logger.debug("Webhook de chamada ignorado: WHATSAPP_CALLING_ENABLED desligado")
        return

    phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
    conn = await _connection_for_number(phone_number_id, db) if phone_number_id else None
    if not conn:
        return

    tenant_id = conn.account_id
    names = _contact_names(value)
    events: list[Notification] = []
    to_ring: list[tuple[WhatsAppCall, Conversation]] = []

    for event in value.get("calls") or []:
        if not event.get("id") or (event.get("direction") or USER_INITIATED).upper() != USER_INITIATED:
            continue
        if not (event.get("from") or event.get("from_user_id")):
            logger.warning("Chamada sem identificação do contato ignorada")
            continue
        try:
            async with db.begin_nested():
                new_events, ringing = await _apply_event(event, value, names, tenant_id, db)
        except IntegrityError:
            # Duplicata concorrente: a outra requisição já criou a chamada.
            continue
        except Exception as exc:
            # Só o tipo: a mensagem de erro do banco pode citar os parâmetros do evento.
            logger.warning("Falha ao processar evento de chamada: %s", type(exc).__name__)
            continue
        events += new_events
        if ringing:
            to_ring.append(ringing)

    # Antes de avisar: o atendente pode clicar em Atender assim que o evento chegar.
    await db.commit()

    if not events and not to_ring:
        return
    user_ids = await users_with_module(db, tenant_id, "whatsapp")
    await notify(tenant_id, user_ids, events)
    for call, conv in to_ring:
        await _ring(call, conv, user_ids)
