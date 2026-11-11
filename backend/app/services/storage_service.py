"""
Storage de mídias de post (Instagram) no Supabase Storage.

Por que existe: o disco do Fly é efêmero — arquivos salvos localmente somem a
cada deploy/restart, quebrando posts agendados. Aqui as mídias vão para um
bucket PÚBLICO do Supabase (a Meta precisa baixar a URL ao publicar o post).

Se o Supabase não estiver configurado (`storage_enabled == False`), o chamador
deve cair no fallback de disco local — mantendo o dev local funcionando.

Usa a REST API do Supabase Storage via httpx (sem adicionar o SDK).
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _base() -> str:
    return settings.supabase_url.rstrip("/") + "/storage/v1"


def _headers() -> dict:
    # As chaves novas do Supabase (sb_secret_...) não são JWT, então além do
    # Bearer é preciso mandar o header `apikey` — senão o Storage responde
    # "Invalid Compact JWS".
    key = settings.supabase_service_key
    return {"Authorization": f"Bearer {key}", "apikey": key}


def public_url(path: str) -> str:
    """URL pública (imutável) de um objeto no bucket público."""
    return f"{_base()}/object/public/{settings.supabase_bucket}/{path}"


def path_from_url(url: str) -> str | None:
    """Extrai o caminho do objeto a partir de uma URL pública deste bucket.

    Retorna None se a URL não for do nosso Supabase Storage (ex.: mídia antiga
    servida pelo disco local), para o chamador saber que não há o que apagar.
    """
    marker = f"/object/public/{settings.supabase_bucket}/"
    if not url or marker not in url:
        return None
    return url.split(marker, 1)[1]


async def upload(path: str, content: bytes, content_type: str) -> str:
    """Sobe um objeto e devolve a URL pública. Levanta em caso de falha."""
    url = f"{_base()}/object/{settings.supabase_bucket}/{path}"
    headers = {
        **_headers(),
        "Content-Type": content_type,
        # sobrescreve se já existir (nomes são uuid, então praticamente nunca)
        "x-upsert": "true",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, content=content)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Falha ao subir mídia no Supabase ({resp.status_code}): {resp.text}"
        )
    logger.info("Mídia enviada ao Supabase Storage: %s (%d bytes)", path, len(content))
    return public_url(path)


async def delete(path: str) -> None:
    """Apaga um objeto do bucket. Best-effort — só loga se falhar."""
    url = f"{_base()}/object/{settings.supabase_bucket}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(url, headers=_headers())
        if resp.status_code not in (200, 204):
            logger.warning("Falha ao apagar mídia %s (%s): %s", path, resp.status_code, resp.text)
        else:
            logger.info("Mídia apagada do Supabase Storage: %s", path)
    except Exception as e:  # nunca deixa a limpeza derrubar o fluxo de publicação
        logger.warning("Erro ao apagar mídia %s: %s", path, e)


async def delete_by_url(url: str) -> None:
    """Conveniência: apaga a partir da URL pública, se for do nosso bucket."""
    path = path_from_url(url)
    if path:
        await delete(path)


async def list_objects(prefix: str = "", limit: int = 1000) -> list[dict]:
    """Lista objetos do bucket (cada item tem 'name' e 'created_at').

    Best-effort: retorna [] em caso de erro (a limpeza não deve derrubar nada).
    """
    url = f"{_base()}/object/list/{settings.supabase_bucket}"
    body = {
        "prefix": prefix,
        "limit": limit,
        "sortBy": {"column": "created_at", "order": "asc"},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers={**_headers(), "Content-Type": "application/json"}, json=body)
        if resp.status_code != 200:
            logger.warning("Falha ao listar bucket (%s): %s", resp.status_code, resp.text)
            return []
        # A API às vezes retorna um placeholder de pasta sem created_at — filtra.
        return [o for o in resp.json() if o.get("name") and o.get("created_at")]
    except Exception as e:
        logger.warning("Erro ao listar bucket: %s", e)
        return []
