"""
WhatsApp Business Cloud API service.

Requer:
  - Phone Number ID (por tenant)
  - WABA ID (por tenant)
  - System User Token ou token de longa duração
"""
import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503}
_MAX_RETRIES = 3


async def _request(method: str, url: str, **kwargs) -> dict:
    last_resp = None
    for attempt in range(_MAX_RETRIES):
        async with httpx.AsyncClient(timeout=15.0) as client:
            last_resp = await client.request(method, url, **kwargs)

        if last_resp.status_code not in _RETRY_STATUSES:
            data = last_resp.json()
            if last_resp.status_code >= 400:
                logger.warning("Meta API error %s: %s", last_resp.status_code, data)
            return data

        wait = 2 ** attempt
        logger.warning("HTTP %s from %s — retry in %ss", last_resp.status_code, url, wait)
        await asyncio.sleep(wait)

    return last_resp.json() if last_resp else {}


# ---------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------

async def send_text(
    token: str,
    phone_number_id: str,
    to: str,
    body: str,
    reply_to: str | None = None,
) -> dict:
    """Texto livre — válido apenas dentro da janela de 24h.

    reply_to: wamid de uma mensagem anterior para responder citando (quote).
    """
    payload: dict = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": True, "body": body},
    }
    if reply_to:
        payload["context"] = {"message_id": reply_to}
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


async def send_template(
    token: str,
    phone_number_id: str,
    to: str,
    template_name: str,
    language_code: str = "pt_BR",
    components: list | None = None,
) -> dict:
    """Template aprovado — funciona fora da janela de 24h."""
    payload: dict = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components

    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


async def send_media(
    token: str,
    phone_number_id: str,
    to: str,
    media_type: str,
    media_url: str,
    caption: str | None = None,
) -> dict:
    """Envia mídia (image/video/document/audio) por URL pública."""
    media_payload: dict = {"link": media_url}
    if caption and media_type in ("image", "video", "document"):
        media_payload["caption"] = caption

    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
            media_type: media_payload,
        },
    )


async def send_media_by_id(
    token: str,
    phone_number_id: str,
    to: str,
    media_type: str,
    media_id: str,
    caption: str | None = None,
    filename: str | None = None,
    reply_to: str | None = None,
) -> dict:
    """Envia mídia previamente enviada via upload_media (por Media ID)."""
    media_payload: dict = {"id": media_id}
    if caption and media_type in ("image", "video", "document"):
        media_payload["caption"] = caption
    if filename and media_type == "document":
        media_payload["filename"] = filename

    payload: dict = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": media_type,
        media_type: media_payload,
    }
    if reply_to:
        payload["context"] = {"message_id": reply_to}
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


async def send_interactive_buttons(
    token: str,
    phone_number_id: str,
    to: str,
    body: str,
    buttons: list[dict],
    header: str | None = None,
    footer: str | None = None,
) -> dict:
    """
    Mensagem interativa com até 3 botões de resposta rápida.
    buttons: [{"id": "opcao_1", "title": "Sim"}, ...] — title máx. 20 chars.
    """
    interactive: dict = {
        "type": "button",
        "body": {"text": body},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                for b in buttons[:3]
            ]
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        },
    )


async def send_interactive_list(
    token: str,
    phone_number_id: str,
    to: str,
    body: str,
    button_text: str,
    sections: list[dict],
    header: str | None = None,
    footer: str | None = None,
) -> dict:
    """
    Mensagem de lista (menu de até 10 opções).
    sections: [{"title": "Seção", "rows": [{"id": "r1", "title": "Opção", "description": "..."}]}]
    """
    interactive: dict = {
        "type": "list",
        "body": {"text": body},
        "action": {"button": button_text[:20], "sections": sections},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        },
    )


async def send_reaction(
    token: str, phone_number_id: str, to: str, message_id: str, emoji: str
) -> dict:
    """Reage a uma mensagem com emoji. Emoji vazio remove a reação."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "reaction",
            "reaction": {"message_id": message_id, "emoji": emoji},
        },
    )


async def mark_as_read(token: str, phone_number_id: str, message_id: str) -> dict:
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        },
    )


async def send_typing_indicator(token: str, phone_number_id: str, message_id: str) -> dict:
    """
    Marca a mensagem como lida E exibe "digitando..." para o cliente
    (dura até 25s ou até a próxima mensagem enviada).
    """
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"},
        },
    )


# ---------------------------------------------------------------------------
# Embedded Signup — pós-onboarding do WABA
# ---------------------------------------------------------------------------

async def subscribe_app_to_waba(token: str, waba_id: str) -> dict:
    """Inscreve o app para receber webhooks deste WABA (obrigatório após o signup)."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{waba_id}/subscribed_apps",
        headers={"Authorization": f"Bearer {token}"},
    )


async def register_phone_number(token: str, phone_number_id: str, pin: str) -> dict:
    """
    Finaliza o registro do número na Cloud API (obrigatório uma vez após o
    Embedded Signup). O PIN é usado apenas para verificação em duas etapas
    caso o número seja migrado no futuro.
    """
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{phone_number_id}/register",
        headers={"Authorization": f"Bearer {token}"},
        json={"messaging_product": "whatsapp", "pin": pin},
    )


async def get_phone_number_info(token: str, phone_number_id: str) -> dict:
    """Busca o número de exibição e o nome verificado do Phone Number ID."""
    return await _request(
        "GET",
        f"{settings.meta_graph_url}/{phone_number_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "display_phone_number,verified_name"},
    )


# ---------------------------------------------------------------------------
# Upload / download de mídia
# ---------------------------------------------------------------------------

async def upload_media(
    token: str,
    phone_number_id: str,
    content: bytes,
    mime_type: str,
    filename: str = "file",
) -> dict:
    """Sobe um arquivo para a Meta e retorna {"id": "<media_id>"}."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.meta_graph_url}/{phone_number_id}/media",
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": mime_type},
            files={"file": (filename, content, mime_type)},
        )
    data = resp.json()
    if resp.status_code >= 400:
        logger.warning("Falha no upload de mídia: %s", data)
    return data


async def fetch_media(token: str, media_id: str) -> tuple[bytes, str]:
    """Baixa uma mídia da Meta. Retorna (bytes, mime_type)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r1 = await client.get(
            f"{settings.meta_graph_url}/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r1.raise_for_status()
        info = r1.json()
        media_url = info.get("url")
        if not media_url:
            raise ValueError(f"Meta não retornou URL para media_id={media_id}")

        r2 = await client.get(media_url, headers={"Authorization": f"Bearer {token}"})
        r2.raise_for_status()
        return r2.content, info.get("mime_type") or "application/octet-stream"


async def download_media(token: str, media_id: str, return_url_only: bool = False) -> bytes | str:
    """
    Passo 1: obtém a URL do arquivo.
    Passo 2: baixa o arquivo (se return_url_only=False).
    Retorna os bytes brutos ou a URL pública.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r1 = await client.get(
            f"{settings.meta_graph_url}/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r1.raise_for_status()
        media_url = r1.json().get("url")
        if not media_url:
            raise ValueError(f"Meta não retornou URL para media_id={media_id}")

        if return_url_only:
            return media_url

        r2 = await client.get(media_url, headers={"Authorization": f"Bearer {token}"})
        r2.raise_for_status()
        return r2.content


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

async def list_templates(token: str, waba_id: str, limit: int = 100) -> list[dict]:
    """Retorna todos os templates do WABA (atravessa paginação)."""
    templates: list[dict] = []
    url = f"{settings.meta_graph_url}/{waba_id}/message_templates"
    params = {"limit": limit, "fields": "id,name,language,status,category,components"}

    while url:
        data = await _request("GET", url, headers={"Authorization": f"Bearer {token}"},
                              params=params)
        templates.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}  # next URL already has params embedded

    return templates


async def create_template(
    token: str,
    waba_id: str,
    name: str,
    category: str,
    language: str,
    components: list[dict],
) -> dict:
    """Envia template para aprovação da Meta."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{waba_id}/message_templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "category": category,
            "language": language,
            "components": components,
        },
    )


async def delete_template(token: str, waba_id: str, name: str) -> dict:
    return await _request(
        "DELETE",
        f"{settings.meta_graph_url}/{waba_id}/message_templates",
        headers={"Authorization": f"Bearer {token}"},
        params={"name": name},
    )
