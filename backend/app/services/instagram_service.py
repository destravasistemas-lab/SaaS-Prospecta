"""
Instagram Graph API service.

All functions receive a decrypted access token (use meta_token_service.decrypt_token
to obtain it from MetaConnection.access_token_encrypted).
"""
import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503}
_MAX_RETRIES = 3


async def _request(method: str, url: str, **kwargs) -> dict:
    """HTTP request with exponential back-off on rate-limit / server errors."""
    for attempt in range(_MAX_RETRIES):
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, url, **kwargs)

        if resp.status_code not in _RETRY_STATUSES:
            data = resp.json()
            _check_token_error(data)
            return data

        wait = 2 ** attempt
        logger.warning("HTTP %s from %s — retrying in %ss (attempt %d)", resp.status_code, url, wait, attempt + 1)
        await asyncio.sleep(wait)

    return resp.json()


def _check_token_error(data: dict) -> None:
    """Raise a descriptive error when Meta returns a token-related error."""
    error = data.get("error", {})
    code = error.get("code")
    if code in (190, 102, 2500):
        raise TokenExpiredError(f"Meta token error (code {code}): {error.get('message')}")


class TokenExpiredError(Exception):
    """Raised when Meta returns a token-expired / invalid-token error."""


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

async def subscribe_webhooks(token: str, ig_user_id: str) -> dict:
    """
    Inscreve a conta Instagram para receber webhooks de comentários e
    mensagens neste app (obrigatório após o login — a Meta não inscreve
    automaticamente, mesmo no fluxo de Instagram Login).
    """
    return await _request(
        "POST",
        f"{settings.ig_graph_url}/{ig_user_id}/subscribed_apps",
        params={"access_token": token, "subscribed_fields": "comments,messages"},
    )


# ---------------------------------------------------------------------------
# Direct Messages (IG Messaging API)
# ---------------------------------------------------------------------------

async def send_dm(token: str, recipient_id: str, message: str) -> dict:
    """Send a direct message to an Instagram user."""
    return await _request(
        "POST",
        f"{settings.ig_graph_url}/me/messages",
        params={"access_token": token},
        json={"recipient": {"id": recipient_id}, "message": {"text": message}},
    )


async def mark_seen(token: str, recipient_id: str) -> dict:
    """Marca as mensagens do usuário como lidas (ticks azuis no Instagram Direct)."""
    return await _request(
        "POST",
        f"{settings.ig_graph_url}/me/messages",
        params={"access_token": token},
        json={"recipient": {"id": recipient_id}, "sender_action": "mark_seen"},
    )


async def get_user_profile(token: str, igsid: str) -> dict:
    """
    Busca nome, @username e foto de um usuário a partir do ID dele no Direct
    (IGSID). O webhook de DM só manda o ID — este é o passo para exibir o nome
    real em vez do número. Requer a permissão instagram_business_manage_messages.
    """
    return await _request(
        "GET",
        f"{settings.ig_graph_url}/{igsid}",
        params={"access_token": token, "fields": "name,username,profile_pic"},
    )


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

async def reply_to_comment(token: str, comment_id: str, message: str) -> dict:
    """Reply to an Instagram comment (public, visible under the post)."""
    return await _request(
        "POST",
        f"{settings.ig_graph_url}/{comment_id}/replies",
        params={"access_token": token},
        json={"message": message},
    )


async def send_private_reply(token: str, comment_id: str, message: str) -> dict:
    """
    Send a private DM in response to a specific comment ("private reply").

    Meta constraints (not configurable): the reply must be sent within 7 days
    of the comment, and only one private reply is allowed per comment_id —
    a second attempt returns an error from the Graph API.
    """
    return await _request(
        "POST",
        f"{settings.ig_graph_url}/me/messages",
        params={"access_token": token},
        json={"recipient": {"comment_id": comment_id}, "message": {"text": message}},
    )


# ---------------------------------------------------------------------------
# Media publishing (container flow)
# ---------------------------------------------------------------------------

async def _wait_for_container(token: str, container_id: str, max_tries: int, delay: float) -> None:
    """
    Aguarda o container de mídia ficar FINISHED antes de publicar. Publicar
    cedo demais (container ainda ERROR/IN_PROGRESS) faz a Meta recusar com 400.
    Levanta ValueError se o processamento falhar.
    """
    for _ in range(max_tries):
        status = await _request(
            "GET",
            f"{settings.ig_graph_url}/{container_id}",
            params={"access_token": token, "fields": "status_code,status"},
        )
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise ValueError(f"Processamento da mídia falhou: {status.get('status') or status}")
        await asyncio.sleep(delay)
    # Não ficou pronto no tempo — tenta publicar assim mesmo (a Meta valida)


async def _publish_container(token: str, ig_user_id: str, container_id: str) -> dict:
    """Publica o container e garante que a Meta devolveu um id de mídia."""
    result = await _request(
        "POST",
        f"{settings.ig_graph_url}/{ig_user_id}/media_publish",
        params={"access_token": token},
        json={"creation_id": container_id},
    )
    if not result.get("id"):
        err = result.get("error", {})
        raise ValueError(err.get("message") or f"Falha ao publicar: {result}")
    return result


async def publish_image_post(
    token: str,
    ig_user_id: str,
    image_url: str,
    caption: str = "",
) -> dict:
    """
    Publica uma imagem única pelo fluxo de container em dois passos:
    1. cria o container; 2. espera ficar FINISHED; 3. publica.
    Imagens costumam processar em ~1-2s (retry rápido).
    """
    container = await _request(
        "POST",
        f"{settings.ig_graph_url}/{ig_user_id}/media",
        params={"access_token": token},
        json={"image_url": image_url, "caption": caption},
    )
    container_id = container.get("id")
    if not container_id:
        err = container.get("error", {})
        raise ValueError(err.get("message") or f"Falha ao criar o container: {container}")

    await _wait_for_container(token, container_id, max_tries=10, delay=2)
    return await _publish_container(token, ig_user_id, container_id)


async def publish_video_post(
    token: str,
    ig_user_id: str,
    video_url: str,
    caption: str = "",
) -> dict:
    """
    Publica um Reel/vídeo. Vídeo demora mais para processar — espera até
    ~50s (10 × 5s) o container ficar FINISHED antes de publicar.
    """
    container = await _request(
        "POST",
        f"{settings.ig_graph_url}/{ig_user_id}/media",
        params={"access_token": token},
        json={"video_url": video_url, "caption": caption, "media_type": "REELS"},
    )
    container_id = container.get("id")
    if not container_id:
        err = container.get("error", {})
        raise ValueError(err.get("message") or f"Falha ao criar o container de vídeo: {container}")

    await _wait_for_container(token, container_id, max_tries=10, delay=5)
    return await _publish_container(token, ig_user_id, container_id)


# ---------------------------------------------------------------------------
# Media listing
# ---------------------------------------------------------------------------

async def list_media(token: str, ig_user_id: str, limit: int = 20) -> list[dict]:
    """List recent media objects for an IG Business account."""
    data = await _request(
        "GET",
        f"{settings.ig_graph_url}/{ig_user_id}/media",
        params={
            "access_token": token,
            "fields": "id,media_type,media_url,thumbnail_url,caption,timestamp,like_count,comments_count",
            "limit": str(limit),
        },
    )
    return data.get("data", [])
