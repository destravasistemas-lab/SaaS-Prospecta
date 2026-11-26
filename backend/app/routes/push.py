"""Notificações: aparelhos que recebem push, preferências e contatos silenciados."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.i18n import t
from app.core.security import get_current_user
from app.models.conversation import Conversation
from app.models.push import ConversationMute, NotificationPref, PushSubscription
from app.models.user import User
from app.services import push_service

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=20, max_length=200)
    auth: str = Field(..., min_length=8, max_length=100)


class SubscribeIn(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)
    keys: SubscriptionKeys


class UnsubscribeIn(BaseModel):
    endpoint: str


class PrefsIn(BaseModel):
    messages_enabled: bool | None = None
    interest_enabled: bool | None = None


class MuteIn(BaseModel):
    muted: bool


async def _prefs_view(db: AsyncSession, user: User) -> dict:
    pref = await push_service.get_prefs(db, user.id)
    muted = (await db.execute(
        select(ConversationMute.conversation_id).where(ConversationMute.user_id == user.id)
    )).scalars().all()
    devices = (await db.execute(
        select(func.count()).select_from(PushSubscription).where(PushSubscription.user_id == user.id)
    )).scalar() or 0
    return {
        "push_enabled": push_service.enabled(),
        "public_key": settings.vapid_public_key or None,
        "messages_enabled": pref.messages_enabled,
        "interest_enabled": pref.interest_enabled,
        "muted_conversation_ids": list(muted),
        "devices": devices,
    }


@router.get("/prefs")
async def get_prefs(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _prefs_view(db, current_user)


@router.put("/prefs")
async def update_prefs(
    body: PrefsIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    pref = await db.get(NotificationPref, current_user.id)
    if not pref:
        pref = NotificationPref(user_id=current_user.id, messages_enabled=True, interest_enabled=True)
        db.add(pref)
    if body.messages_enabled is not None:
        pref.messages_enabled = body.messages_enabled
    if body.interest_enabled is not None:
        pref.interest_enabled = body.interest_enabled
    await db.flush()
    return await _prefs_view(db, current_user)


@router.post("/subscribe", status_code=201)
async def subscribe(
    body: SubscribeIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    if not push_service.enabled():
        raise HTTPException(503, t("Notificações no celular ainda não estão configuradas no servidor.",
                                   "Phone notifications are not configured on the server yet."))
    if not body.endpoint.startswith("https://"):
        raise HTTPException(422, t("Endereço de notificação inválido.", "Invalid notification endpoint."))
    sub = (await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )).scalar_one_or_none()
    if not sub:
        sub = PushSubscription(endpoint=body.endpoint)
        db.add(sub)
    # O mesmo aparelho pode trocar de usuário (outro login no mesmo celular).
    sub.user_id = current_user.id
    sub.tenant_id = current_user.tenant_id
    sub.p256dh = body.keys.p256dh
    sub.auth = body.keys.auth
    await db.flush()
    return await _prefs_view(db, current_user)


@router.post("/unsubscribe")
async def unsubscribe(
    body: UnsubscribeIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(PushSubscription).where(
        PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == current_user.id,
    ))
    await db.flush()
    return await _prefs_view(db, current_user)


@router.post("/test")
async def test_push(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sent = await push_service.send_test(db, current_user.id)
    if not sent:
        raise HTTPException(404, t("Nenhum aparelho com notificação ligada.", "No device with notifications on."))
    return {"devices": sent}


@router.put("/mutes/{conversation_id}")
async def set_mute(
    conversation_id: str, body: MuteIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.tenant_id == current_user.tenant_id)
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(404, t("Conversa não encontrada.", "Conversation not found."))
    existing = (await db.execute(select(ConversationMute).where(
        ConversationMute.user_id == current_user.id, ConversationMute.conversation_id == conv.id,
    ))).scalar_one_or_none()
    if body.muted and not existing:
        db.add(ConversationMute(user_id=current_user.id, conversation_id=conv.id))
    elif not body.muted and existing:
        await db.delete(existing)
    await db.flush()
    return {"conversation_id": conv.id, "muted": body.muted}
