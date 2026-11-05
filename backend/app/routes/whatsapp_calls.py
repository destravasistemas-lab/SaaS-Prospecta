"""
Chamadas de voz do WhatsApp: configurações do número e atender, recusar e encerrar.

Tudo aqui exige o módulo WhatsApp (ver main.py) e WHATSAPP_CALLING_ENABLED ligado.
"""
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.i18n import t
from app.core.modules import users_with_module
from app.core.security import get_current_user
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.meta_connection import MetaConnection
from app.models.user import User
from app.routes.whatsapp import _find_conn
from app.models.whatsapp_call import (
    CALL_CLAIMED, CALL_COMPLETED, CALL_CONNECTED, CALL_ENDED, CALL_MISSED, CALL_REJECTED, CALL_RINGING,
    WhatsAppCall,
)
from app.services import messaging_policy, whatsapp_calling, whatsapp_service
from app.services.meta_token_service import decrypt_token, safe_decrypt_token

logger = logging.getLogger(__name__)


def require_calling_enabled() -> None:
    if not settings.whatsapp_calling_enabled:
        raise HTTPException(404, t("Recurso indisponível.", "Feature unavailable."))


router = APIRouter(prefix="/whatsapp", tags=["whatsapp-calls"], dependencies=[Depends(require_calling_enabled)])

# Limites em que a Meta não ativa ligações (mínimo: 2.000 destinatários por dia)
_TIERS_BELOW_CALLING_MINIMUM = {"TIER_50", "TIER_250"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WeeklyHours(BaseModel):
    day_of_week: Literal["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    open_time: str = Field(..., pattern=r"^([01]\d|2[0-3])[0-5]\d$")
    close_time: str = Field(..., pattern=r"^([01]\d|2[0-3])[0-5]\d$")

    @model_validator(mode="after")
    def _open_before_close(self):
        if self.open_time >= self.close_time:
            raise ValueError("open_time must be before close_time")
        return self


class CallHoursIn(BaseModel):
    status: Literal["ENABLED", "DISABLED"]
    timezone_id: str = Field(default="America/Sao_Paulo", min_length=1, max_length=64)
    weekly_operating_hours: list[WeeklyHours] = Field(..., min_length=1, max_length=14)


class CallingSettingsIn(BaseModel):
    enabled: bool
    call_hours: CallHoursIn | None = None


class CallingSettingsOut(BaseModel):
    connected: bool
    enabled: bool = False
    messaging_limit: str | None = None
    meets_messaging_limit: bool | None = None
    call_hours: dict | None = None
    restrictions: list[dict] = Field(default_factory=list)


class SdpIn(BaseModel):
    sdp: str = Field(..., min_length=10, max_length=20000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token(conn: MetaConnection) -> str:
    try:
        return decrypt_token(conn.access_token_encrypted)
    except Exception:
        raise HTTPException(400, t(
            "Não foi possível ler as credenciais do WhatsApp. Reconecte o número.",
            "Could not read the WhatsApp credentials. Reconnect the number.",
        ))


async def _conn_or_404(tenant_id: str, db: AsyncSession) -> MetaConnection:
    conn = await _find_conn(tenant_id, db)
    if not conn or not conn.phone_number_id:
        raise HTTPException(404, t("WhatsApp não conectado.", "WhatsApp is not connected."))
    return conn


async def _call_or_404(call_id: str, tenant_id: str, db: AsyncSession) -> WhatsAppCall:
    call = (await db.execute(
        select(WhatsAppCall).where(WhatsAppCall.id == call_id, WhatsAppCall.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not call:
        raise HTTPException(404, t("Chamada não encontrada.", "Call not found."))
    return call


def _unavailable() -> HTTPException:
    return HTTPException(409, detail={
        "code": "call_unavailable",
        "message": t(
            "Esta chamada não está mais disponível: outra pessoa atendeu ou ela terminou.",
            "This call is no longer available: someone else answered or it ended.",
        ),
    })


def _not_yours() -> HTTPException:
    return HTTPException(403, t("Esta chamada foi atendida por outra pessoa.", "This call was answered by someone else."))


async def _send_action(call: WhatsAppCall, action: str, db: AsyncSession, sdp: str | None = None) -> None:
    conn = await _conn_or_404(call.tenant_id, db)
    try:
        result = await whatsapp_service.call_action(_token(conn), conn.phone_number_id, call.wa_call_id, action, sdp)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Falha de rede na ação de chamada %s: %s", action, type(exc).__name__)
        raise HTTPException(502, t(
            "Não foi possível falar com a Meta. Tente de novo.", "Could not reach Meta. Please try again.",
        ))
    if result.get("error") or not result.get("success", True):
        raise messaging_policy.meta_send_error(result)


async def _calling_settings_out(conn: MetaConnection) -> CallingSettingsOut:
    token = _token(conn)
    data = await whatsapp_service.get_calling_settings(token, conn.phone_number_id)
    if data.get("error"):
        raise messaging_policy.meta_send_error(data)
    limit = (await whatsapp_service.get_phone_number_info(
        token, conn.phone_number_id, fields="whatsapp_business_manager_messaging_limit",
    )).get("whatsapp_business_manager_messaging_limit")

    calling = data.get("calling") or {}
    restrictions = data.get("restrictions") or calling.get("restrictions") or {}
    return CallingSettingsOut(
        connected=True,
        enabled=calling.get("status") == "ENABLED",
        messaging_limit=limit,
        meets_messaging_limit=limit not in _TIERS_BELOW_CALLING_MINIMUM if limit else None,
        call_hours=calling.get("call_hours"),
        restrictions=restrictions.get("restrictions_list") or [],
    )


# ---------------------------------------------------------------------------
# Configurações do número
# ---------------------------------------------------------------------------

@router.get("/calling/settings", response_model=CallingSettingsOut)
async def get_calling_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = await _find_conn(current_user.tenant_id, db)
    if not conn or not conn.phone_number_id:
        return CallingSettingsOut(connected=False)
    return await _calling_settings_out(conn)


@router.put("/calling/settings", response_model=CallingSettingsOut)
async def update_calling_settings(
    body: CallingSettingsIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(403, t("Apenas admins podem alterar as ligações.", "Only admins can change calling settings."))
    conn = await _conn_or_404(current_user.tenant_id, db)
    token = _token(conn)

    calling: dict = {"status": "ENABLED" if body.enabled else "DISABLED"}
    if body.call_hours:
        calling["call_hours"] = body.call_hours.model_dump()
        # A Meta apaga os feriados que não vierem no pedido; preserva os já configurados.
        current = await whatsapp_service.get_calling_settings(token, conn.phone_number_id)
        holidays = ((current.get("calling") or {}).get("call_hours") or {}).get("holiday_schedule")
        if holidays:
            calling["call_hours"]["holiday_schedule"] = holidays

    result = await whatsapp_service.update_calling_settings(token, conn.phone_number_id, calling)
    if result.get("error"):
        raise messaging_policy.meta_send_error(result)
    logger.info("Ligações %s no número %s (tenant %s)", calling["status"], conn.phone_number_id, conn.account_id)
    return await _calling_settings_out(conn)


# ---------------------------------------------------------------------------
# Chamadas
# ---------------------------------------------------------------------------

@router.get("/calls/active")
async def active_calls(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Chamadas tocando agora (ao abrir o painel ou reconectar o WebSocket)."""
    rows = (await db.execute(
        select(WhatsAppCall, Conversation)
        .join(Conversation, Conversation.id == WhatsAppCall.conversation_id)
        .where(WhatsAppCall.tenant_id == current_user.tenant_id, WhatsAppCall.status == CALL_RINGING)
        .order_by(WhatsAppCall.created_at.asc())
    )).all()
    return [
        whatsapp_calling.incoming_view(call, await whatsapp_calling.ring_delay_ms(conv, current_user.id, call))
        for call, conv in rows
        if whatsapp_calling.is_ringing(call)
    ]


@router.post("/calls/{call_id}/claim")
async def claim_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assume a chamada e devolve o offer. Quem chega primeiro leva; os outros recebem 409."""
    call = await _call_or_404(call_id, current_user.tenant_id, db)
    if not whatsapp_calling.is_ringing(call) or not call.sdp_offer_encrypted:
        raise _unavailable()
    sdp_offer = safe_decrypt_token(call.sdp_offer_encrypted)

    result = await db.execute(
        update(WhatsAppCall)
        .where(
            WhatsAppCall.id == call.id,
            WhatsAppCall.tenant_id == current_user.tenant_id,
            WhatsAppCall.status == CALL_RINGING,
        )
        .values(
            status=CALL_CLAIMED,
            answered_by_user_id=current_user.id,
            answered_by_name=current_user.full_name or current_user.username,
            sdp_offer_encrypted=None,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1 or not sdp_offer:
        raise _unavailable()
    await db.refresh(call)

    # Mesmo efeito de "Assumir": sai das filas Bot/Espera e o bot para de responder.
    conv = await db.get(Conversation, call.conversation_id)
    if conv:
        conv.atendente_id = current_user.id
        conv.bot_active = False
        conv.atendimento_status = "em_atendimento"
    await whatsapp_calling.sync_history(call, db)
    await db.commit()

    events = [whatsapp_calling.call_updated_event(call)]
    if conv:
        events.append(whatsapp_calling.conversation_event(conv))
    await whatsapp_calling.notify(
        call.tenant_id, await users_with_module(db, call.tenant_id, "whatsapp"), events,
    )
    return {"id": call.id, "sdp_offer": sdp_offer, "ice_servers": whatsapp_calling.ice_servers()}


def _require_claimed_by(call: WhatsAppCall, user: User) -> None:
    if call.answered_by_user_id != user.id:
        raise _not_yours()
    if call.status != CALL_CLAIMED:
        raise _unavailable()


@router.post("/calls/{call_id}/pre-accept")
async def pre_accept_call(
    call_id: str,
    body: SdpIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await _call_or_404(call_id, current_user.tenant_id, db)
    _require_claimed_by(call, current_user)
    await _send_action(call, "pre_accept", db, body.sdp)
    return {"success": True}


@router.post("/calls/{call_id}/accept")
async def accept_call(
    call_id: str,
    body: SdpIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    call = await _call_or_404(call_id, current_user.tenant_id, db)
    _require_claimed_by(call, current_user)
    await _send_action(call, "accept", db, body.sdp)

    call.status = CALL_CONNECTED
    call.started_at = datetime.now(timezone.utc)
    await whatsapp_calling.sync_history(call, db)
    await db.commit()
    await whatsapp_calling.notify(
        call.tenant_id, await users_with_module(db, call.tenant_id, "whatsapp"),
        [whatsapp_calling.call_updated_event(call)],
    )
    return {"success": True}


@router.post("/calls/{call_id}/reject")
async def reject_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recusa para todos: a Meta encerra a chamada do cliente."""
    call = await _call_or_404(call_id, current_user.tenant_id, db)
    # Reserva antes de falar com a Meta: um reject depois do claim derrubaria quem atendeu.
    result = await db.execute(
        update(WhatsAppCall)
        .where(WhatsAppCall.id == call.id, WhatsAppCall.status == CALL_RINGING)
        .values(status=CALL_REJECTED)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise _unavailable()
    await db.commit()

    try:
        await _send_action(call, "reject", db)
    except HTTPException:
        await db.execute(
            update(WhatsAppCall)
            .where(WhatsAppCall.id == call.id, WhatsAppCall.status == CALL_REJECTED)
            .values(status=CALL_RINGING)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        raise

    await db.refresh(call)
    call.rejected_by_name = current_user.full_name or current_user.username
    events = await whatsapp_calling.finish_call(call, CALL_REJECTED, db)
    await db.commit()
    await whatsapp_calling.notify(
        call.tenant_id, await users_with_module(db, call.tenant_id, "whatsapp"), events,
    )
    return {"success": True}


@router.post("/calls/{call_id}/terminate")
async def terminate_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Encerra a chamada de quem atendeu. A duração final vem depois, no webhook da Meta."""
    call = await _call_or_404(call_id, current_user.tenant_id, db)
    if call.answered_by_user_id != current_user.id and current_user.role != "admin":
        raise _not_yours()
    if call.status in CALL_ENDED:
        return {"success": True}
    if call.status not in (CALL_CLAIMED, CALL_CONNECTED):
        raise _unavailable()

    connected = call.status == CALL_CONNECTED
    await _send_action(call, "terminate" if connected else "reject", db)

    now = datetime.now(timezone.utc)
    duration = None
    if connected and call.started_at:
        started_at = call.started_at if call.started_at.tzinfo else call.started_at.replace(tzinfo=timezone.utc)
        duration = max(0, int((now - started_at).total_seconds()))
    events = await whatsapp_calling.finish_call(
        call, CALL_COMPLETED if connected else CALL_MISSED, db, ended_at=now, duration=duration,
    )
    await db.commit()
    await whatsapp_calling.notify(
        call.tenant_id, await users_with_module(db, call.tenant_id, "whatsapp"), events,
    )
    return {"success": True}


@router.get("/leads/{lead_id}/calls")
async def lead_calls(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Histórico de chamadas do lead."""
    lead = (await db.execute(
        select(Lead.id).where(Lead.id == lead_id, Lead.account_id == current_user.tenant_id)
    )).first()
    if not lead:
        raise HTTPException(404, t("Lead não encontrado.", "Lead not found."))

    calls = (await db.execute(
        select(WhatsAppCall)
        .where(WhatsAppCall.tenant_id == current_user.tenant_id, WhatsAppCall.lead_id == lead_id)
        .order_by(WhatsAppCall.created_at.desc())
        .limit(100)
    )).scalars().all()

    return [
        {
            **whatsapp_calling.call_view(call),
            "status": whatsapp_calling.display_status(call),
            "conversation_id": call.conversation_id,
            "created_at": call.created_at,
        }
        for call in calls
    ]
