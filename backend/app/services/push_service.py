"""
Notificação no celular e no computador (Web Push): Android, iPhone/iPad (app
instalado pela tela de início, iOS 16.4+), Windows e Mac.

Criptografia do conteúdo pela RFC 8291 (aes128gcm) e identificação do servidor
pela RFC 8292 (VAPID), feitas com o `cryptography` que o projeto já usa. O
pywebpush atual exige cryptography>=47, que conflita com o pin do projeto.

Dois avisos:
  - mensagem nova: respeita "silenciar todos" e o contato silenciado; conversa
    com atendente vai só para ele; no máximo 1 aviso a cada 20 s por conversa;
  - lead interessado: vai para todos que deixaram esse aviso ligado.
"""
import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.core.redis import get_store
from app.models.conversation import Conversation
from app.models.push import ConversationMute, NotificationPref, PushSubscription
from app.models.user import User

logger = logging.getLogger(__name__)

KIND_MESSAGE = "message"
KIND_INTEREST = "interest"
MESSAGE_THROTTLE_SECONDS = 20
RECORD_SIZE = 4096
TTL_SECONDS = 24 * 3600
BODY_MAX = 140

MEDIA_LABELS = {
    "image": "📷 Foto", "audio": "🎤 Áudio", "video": "🎥 Vídeo", "document": "📄 Documento",
    "sticker": "Figurinha", "location": "📍 Localização", "contacts": "👤 Contato",
}


@dataclass(frozen=True)
class Target:
    endpoint: str
    p256dh: str
    auth: str


def enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ---------------------------------------------------------------------------
# Criptografia (RFC 8291) e VAPID (RFC 8292)
# ---------------------------------------------------------------------------

def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(
    payload: bytes, p256dh: str, auth: str, *,
    salt: bytes | None = None, as_private: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """salt e as_private só são passados no teste com o exemplo da RFC 8291."""
    ua_public = b64u_decode(p256dh)
    auth_secret = b64u_decode(auth)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    as_public = as_private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    )
    shared = as_private.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + ciphertext


_jwt_cache: dict[str, tuple[str, int]] = {}


def vapid_authorization(endpoint: str) -> str:
    url = urlparse(endpoint)
    audience = f"{url.scheme}://{url.netloc}"
    now = int(time.time())
    cached = _jwt_cache.get(audience)
    if cached and cached[1] - now > 3600:
        token = cached[0]
    else:
        exp = now + 12 * 3600
        header = b64u(b'{"typ":"JWT","alg":"ES256"}')
        claims = b64u(json.dumps({"aud": audience, "exp": exp, "sub": settings.vapid_subject},
                                 separators=(",", ":")).encode())
        key = ec.derive_private_key(int.from_bytes(b64u_decode(settings.vapid_private_key), "big"), ec.SECP256R1())
        r, s = decode_dss_signature(key.sign(f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256())))
        token = f"{header}.{claims}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
        _jwt_cache[audience] = (token, exp)
    return f"vapid t={token}, k={settings.vapid_public_key}"


# ---------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------

async def _post(client: httpx.AsyncClient, target: Target, body: bytes, urgency: str) -> int:
    resp = await client.post(target.endpoint, content=body, headers={
        "Authorization": vapid_authorization(target.endpoint),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(TTL_SECONDS),
        "Urgency": urgency,
    })
    return resp.status_code


async def deliver(targets: list[Target], payload: dict, urgency: str = "normal") -> list[str]:
    """Envia para cada aparelho. Devolve os endpoints que não existem mais (404/410)."""
    data = json.dumps(payload, ensure_ascii=False).encode()
    dead: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def one(target: Target) -> None:
            try:
                status = await _post(client, target, encrypt(data, target.p256dh, target.auth), urgency)
            except Exception as exc:
                logger.warning("Push falhou (%s): %s", urlparse(target.endpoint).netloc, type(exc).__name__)
                return
            if status in (404, 410):
                dead.append(target.endpoint)
            elif status >= 400:
                logger.warning("Push recusado %s (%s)", status, urlparse(target.endpoint).netloc)

        await asyncio.gather(*(one(t) for t in targets))
    return dead


_pending: set[asyncio.Task] = set()


async def _deliver_and_prune(targets: list[Target], payload: dict, urgency: str) -> None:
    dead = await deliver(targets, payload, urgency)
    if not dead:
        return
    try:
        async with async_session() as db:
            await db.execute(delete(PushSubscription).where(PushSubscription.endpoint.in_(dead)))
            await db.commit()
    except Exception as exc:
        logger.warning("Push: não consegui remover aparelhos inativos: %s", type(exc).__name__)


def _spawn(targets: list[Target], payload: dict, urgency: str) -> None:
    # Fora do request: o webhook da Meta responde sem esperar os envios.
    task = asyncio.create_task(_deliver_and_prune(targets, payload, urgency))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def wait_pending() -> None:
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)


# ---------------------------------------------------------------------------
# Quem recebe
# ---------------------------------------------------------------------------

async def _subscriptions(db: AsyncSession, tenant_id: str) -> list[PushSubscription]:
    return list((await db.execute(
        select(PushSubscription)
        .join(User, User.id == PushSubscription.user_id)
        .where(PushSubscription.tenant_id == tenant_id, User.is_active.is_(True))
    )).scalars().all())


async def get_prefs(db: AsyncSession, user_id: str) -> NotificationPref:
    pref = await db.get(NotificationPref, user_id)
    return pref or NotificationPref(user_id=user_id, messages_enabled=True, interest_enabled=True)


async def _prefs(db: AsyncSession, user_ids: set[str]) -> dict[str, NotificationPref]:
    rows = (await db.execute(select(NotificationPref).where(NotificationPref.user_id.in_(user_ids)))).scalars()
    return {p.user_id: p for p in rows}


def preview(text: str | None, media_type: str | None = None) -> str:
    body = " ".join((text or "").split())
    if not body:
        body = MEDIA_LABELS.get(media_type or "", "Nova mensagem")
    return body if len(body) <= BODY_MAX else body[: BODY_MAX - 1] + "…"


def _target(sub: PushSubscription) -> Target:
    return Target(sub.endpoint, sub.p256dh, sub.auth)


async def notify_new_message(
    db: AsyncSession, *, conv: Conversation, title: str, text: str | None,
    media_type: str | None = None, url: str = "/app/whatsapp",
) -> int:
    """Aviso de mensagem nova do cliente. Devolve quantos aparelhos vão receber."""
    if not enabled():
        return 0
    subs = await _subscriptions(db, conv.tenant_id)
    if conv.atendente_id:
        subs = [s for s in subs if s.user_id == conv.atendente_id]
    if not subs:
        return 0
    users = {s.user_id for s in subs}
    prefs = await _prefs(db, users)
    muted = set((await db.execute(
        select(ConversationMute.user_id).where(
            ConversationMute.conversation_id == conv.id, ConversationMute.user_id.in_(users),
        )
    )).scalars())
    targets = [
        _target(s) for s in subs
        if s.user_id not in muted and (prefs[s.user_id].messages_enabled if s.user_id in prefs else True)
    ]
    if not targets:
        return 0
    # Várias mensagens seguidas do mesmo cliente: um aviso só.
    store = await get_store()
    if not await store.set_nx_ttl(f"push:msg:{conv.id}", "1", MESSAGE_THROTTLE_SECONDS):
        return 0
    _spawn(targets, {
        "kind": KIND_MESSAGE, "title": title, "body": preview(text, media_type),
        "url": url, "tag": f"conv-{conv.id}", "conversation_id": conv.id,
    }, "normal")
    return len(targets)


async def notify_interest(
    db: AsyncSession, *, conv: Conversation, title: str, text: str | None, url: str = "/app/whatsapp",
) -> int:
    """Aviso de lead interessado (vale mesmo com o contato ou as mensagens silenciados)."""
    if not enabled():
        return 0
    subs = await _subscriptions(db, conv.tenant_id)
    if not subs:
        return 0
    prefs = await _prefs(db, {s.user_id for s in subs})
    targets = [
        _target(s) for s in subs
        if (prefs[s.user_id].interest_enabled if s.user_id in prefs else True)
    ]
    if targets:
        _spawn(targets, {
            "kind": KIND_INTEREST, "title": title, "body": preview(text),
            "url": url, "tag": f"interest-{conv.id}", "conversation_id": conv.id,
        }, "high")
    return len(targets)


async def send_test(db: AsyncSession, user_id: str) -> int:
    subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()
    targets = [_target(s) for s in subs]
    if targets and enabled():
        _spawn(targets, {
            "kind": "test", "title": "Prospecta", "body": "Notificações ligadas neste aparelho ✅",
            "url": "/app", "tag": "test",
        }, "normal")
    return len(targets)
