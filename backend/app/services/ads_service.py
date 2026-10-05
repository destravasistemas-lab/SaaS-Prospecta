"""
Meta Ads (Marketing API) service.

act_ prefix handling: Meta ad account IDs come back either as "act_123" or plain
"123" depending on the endpoint.  _act() normalises them.
"""
import asyncio
import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503}
_MAX_RETRIES = 3


def _act(ad_account_id: str) -> str:
    """Ensure the ID has the act_ prefix expected by the Marketing API."""
    return ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"


async def _request(method: str, url: str, **kwargs) -> dict:
    for attempt in range(_MAX_RETRIES):
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(method, url, **kwargs)

        if resp.status_code not in _RETRY_STATUSES:
            return resp.json()

        wait = 2 ** attempt
        logger.warning("HTTP %s from %s — retrying in %ss", resp.status_code, url, wait)
        await asyncio.sleep(wait)

    return resp.json()


# ---------------------------------------------------------------------------
# Ad Accounts
# ---------------------------------------------------------------------------

async def list_ad_accounts(token: str) -> list[dict]:
    """List all ad accounts the token's user has access to."""
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/me/adaccounts",
        params={
            "access_token": token,
            "fields": "id,name,account_status,currency,amount_spent,business_name",
            "limit": "100",
        },
    )
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

async def list_campaigns(token: str, ad_account_id: str) -> list[dict]:
    """List campaigns for an ad account."""
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/{_act(ad_account_id)}/campaigns",
        params={
            "access_token": token,
            "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time",
            "limit": "50",
        },
    )
    return data.get("data", [])


async def create_campaign(
    token: str,
    ad_account_id: str,
    name: str,
    objective: str,
    status: str = "PAUSED",
    special_ad_categories: list[str] | None = None,
    is_adset_budget_sharing_enabled: bool = False,
) -> dict:
    """
    Create a campaign.

    objective examples: OUTCOME_LEADS, OUTCOME_SALES, OUTCOME_AWARENESS
    status: ACTIVE | PAUSED
    """
    payload = {
        "name": name,
        "objective": objective,
        "status": status,
        "special_ad_categories": special_ad_categories or ["NONE"],
        "is_adset_budget_sharing_enabled": is_adset_budget_sharing_enabled,
    }
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{_act(ad_account_id)}/campaigns",
        params={"access_token": token},
        json=payload,
    )


async def update_campaign(token: str, campaign_id: str, **fields) -> dict:
    """Update a campaign (status, name, daily_budget, lifetime_budget, ...)."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{campaign_id}",
        params={"access_token": token},
        json=fields,
    )


async def delete_campaign(token: str, campaign_id: str) -> dict:
    return await _request(
        "DELETE",
        f"{settings.meta_graph_url}/{campaign_id}",
        params={"access_token": token},
    )


async def copy_object(token: str, node_id: str, deep_copy: bool = False) -> dict:
    """
    Duplica um objeto de anúncio (campanha, conjunto ou anúncio) usando a edge
    /copies da Meta. A cópia nasce PAUSADA. deep_copy=True (só campanha/conjunto)
    também copia os filhos (conjuntos/anúncios).
    """
    payload: dict = {"status_option": "PAUSED"}
    if deep_copy:
        payload["deep_copy"] = True
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{node_id}/copies",
        params={"access_token": token},
        json=payload,
    )


# ---------------------------------------------------------------------------
# Ad Sets
# ---------------------------------------------------------------------------

async def create_ad_set(
    token: str,
    ad_account_id: str,
    campaign_id: str,
    name: str,
    daily_budget: int,
    billing_event: str = "IMPRESSIONS",
    optimization_goal: str = "REACH",
    targeting: dict | None = None,
    bid_amount: int | None = None,
    end_time: str | None = None,
) -> dict:
    """
    Create an ad set inside a campaign.

    daily_budget/bid_amount are in account currency minor units (e.g. centavos for BRL).
    end_time is an ISO-8601 string; omit for an ad set that runs indefinitely.
    """
    payload: dict = {
        "name": name,
        "campaign_id": campaign_id,
        "daily_budget": str(daily_budget),
        "billing_event": billing_event,
        "optimization_goal": optimization_goal,
        "targeting": targeting or {"geo_locations": {"countries": ["BR"]}},
        "status": "PAUSED",
    }
    if bid_amount:
        # Lance manual → estratégia com teto de lance (exige o valor do lance).
        payload["bid_strategy"] = "LOWEST_COST_WITH_BID_CAP"
        payload["bid_amount"] = str(bid_amount)
    else:
        # Sem lance manual → "maior volume de resultados pelo orçamento" (não exige
        # valor de lance). Sem definir a estratégia, a Meta recusa com o subcode
        # 2490487 ("valor ou restrições de lance obrigatórios").
        payload["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
    if end_time:
        payload["end_time"] = end_time
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{_act(ad_account_id)}/adsets",
        params={"access_token": token},
        json=payload,
    )


async def list_ad_sets(token: str, campaign_id: str) -> list[dict]:
    """List ad sets belonging to a campaign."""
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/{campaign_id}/adsets",
        params={
            "access_token": token,
            "fields": "id,name,status,daily_budget,lifetime_budget,bid_amount,"
                      "billing_event,optimization_goal,targeting,end_time",
            "limit": "50",
        },
    )
    return data.get("data", [])


async def update_ad_set(token: str, ad_set_id: str, **fields) -> dict:
    """Update an ad set (status, daily_budget, bid_amount, targeting, ...)."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{ad_set_id}",
        params={"access_token": token},
        json=fields,
    )


async def delete_ad_set(token: str, ad_set_id: str) -> dict:
    return await _request(
        "DELETE",
        f"{settings.meta_graph_url}/{ad_set_id}",
        params={"access_token": token},
    )


# ---------------------------------------------------------------------------
# Video upload (obrigatório para criativos de vídeo — a Marketing API não
# aceita uma video_url pública direta como aceita para imagens).
# ---------------------------------------------------------------------------

async def upload_ad_video(
    token: str, ad_account_id: str, content: bytes, filename: str,
) -> dict:
    """Sobe um vídeo para a conta de anúncios. Retorna {"id": "<video_id>"}."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.meta_graph_url}/{_act(ad_account_id)}/advideos",
            params={"access_token": token},
            files={"source": (filename, content, "video/mp4")},
        )
    data = resp.json()
    if resp.status_code >= 400:
        logger.warning("Falha no upload de vídeo de anúncio: %s", data)
    return data


# ---------------------------------------------------------------------------
# Ad Creatives & Ads
# ---------------------------------------------------------------------------

async def create_ad_creative(
    token: str,
    ad_account_id: str,
    name: str,
    page_id: str,
    message: str,
    image_url: str | None = None,
    link_url: str | None = None,
    video_id: str | None = None,
    video_thumb_url: str | None = None,
    carousel_items: list[dict] | None = None,
) -> dict:
    """
    Create an ad creative — imagem única, vídeo (via video_id já enviado por
    upload_ad_video) ou carrossel (2-10 itens: image_url + link_url + message).
    """
    object_story_spec: dict = {"page_id": page_id}

    if carousel_items:
        object_story_spec["link_data"] = {
            "message": message,
            "link": link_url or "",
            "child_attachments": [
                {
                    "link": item.get("link_url") or link_url or "",
                    "picture": item.get("image_url"),
                    "name": item.get("message", ""),
                }
                for item in carousel_items
            ],
        }
    elif video_id:
        object_story_spec["video_data"] = {
            "video_id": video_id,
            "message": message,
            **({"image_url": video_thumb_url} if video_thumb_url else {}),
            **({"call_to_action": {"type": "LEARN_MORE", "value": {"link": link_url}}} if link_url else {}),
        }
    else:
        object_story_spec["link_data"] = {
            "message": message,
            **({"link": link_url} if link_url else {}),
            **({"picture": image_url} if image_url else {}),
        }

    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{_act(ad_account_id)}/adcreatives",
        params={"access_token": token},
        json={"name": name, "object_story_spec": object_story_spec},
    )


async def get_promotable_instagram(token: str, page_id: str | None = None) -> dict:
    """
    Descobre a conta do Instagram vinculada (para impulsionar posts existentes).
    Retorna {ig_user_id, username, page_id} — usa a página informada ou a 1ª
    página com Instagram conectado.
    """
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/me/accounts",
        params={"access_token": token, "fields": "id,name,instagram_business_account{id,username}"},
    )
    pages = data.get("data", [])
    chosen = None
    if page_id:
        chosen = next((p for p in pages if p.get("id") == page_id and p.get("instagram_business_account")), None)
    if not chosen:
        chosen = next((p for p in pages if p.get("instagram_business_account")), None)
    if not chosen:
        return {}
    ig = chosen["instagram_business_account"]
    return {"ig_user_id": ig.get("id"), "username": ig.get("username"), "page_id": chosen.get("id")}


async def list_instagram_posts(token: str, ig_user_id: str, limit: int = 25) -> list[dict]:
    """Lista os posts do Instagram que podem ser impulsionados como anúncio."""
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/{ig_user_id}/media",
        params={
            "access_token": token,
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": limit,
        },
    )
    return data.get("data", [])


async def create_creative_from_post(
    token: str,
    ad_account_id: str,
    name: str,
    ig_user_id: str,
    source_instagram_media_id: str,
    link_url: str,
    cta_type: str = "LEARN_MORE",
) -> dict:
    """
    Cria um criativo a partir de um post existente do Instagram (impulsionar).
    Recipe validada: source_instagram_media_id + instagram_user_id + call_to_action
    (a Meta exige um link de destino, mesmo impulsionando um post orgânico).
    """
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{_act(ad_account_id)}/adcreatives",
        params={"access_token": token},
        json={
            "name": name,
            "source_instagram_media_id": source_instagram_media_id,
            "instagram_user_id": ig_user_id,
            "call_to_action": {"type": cta_type, "value": {"link": link_url}},
        },
    )


async def create_ad(
    token: str,
    ad_account_id: str,
    ad_set_id: str,
    creative_id: str,
    name: str,
    status: str = "PAUSED",
) -> dict:
    """Create an ad linking an ad set to a creative."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{_act(ad_account_id)}/ads",
        params={"access_token": token},
        json={
            "name": name,
            "adset_id": ad_set_id,
            "creative": {"creative_id": creative_id},
            "status": status,
        },
    )


async def list_ads(token: str, ad_set_id: str) -> list[dict]:
    """List ads belonging to an ad set."""
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/{ad_set_id}/ads",
        params={
            "access_token": token,
            "fields": "id,name,status,creative{id,name,thumbnail_url,object_story_spec}",
            "limit": "50",
        },
    )
    return data.get("data", [])


async def update_ad(token: str, ad_id: str, **fields) -> dict:
    """Update an ad (status, name, ...)."""
    return await _request(
        "POST",
        f"{settings.meta_graph_url}/{ad_id}",
        params={"access_token": token},
        json=fields,
    )


async def delete_ad(token: str, ad_id: str) -> dict:
    return await _request(
        "DELETE",
        f"{settings.meta_graph_url}/{ad_id}",
        params={"access_token": token},
    )


# ---------------------------------------------------------------------------
# Lead Ads (formulários instantâneos)
# ---------------------------------------------------------------------------

async def get_leadgen(token: str, leadgen_id: str) -> dict:
    """
    Busca os dados preenchidos de um lead de formulário (Lead Ads).
    Requer a permissão leads_retrieval (App Review) em produção.
    """
    return await _request(
        "GET",
        f"{settings.meta_graph_url}/{leadgen_id}",
        params={
            "access_token": token,
            "fields": "id,ad_id,form_id,created_time,field_data",
        },
    )


async def get_ad_names(token: str, ad_ids: list[str]) -> dict[str, str]:
    """Resolve nomes de anúncios em lote (uma única chamada via ?ids=)."""
    if not ad_ids:
        return {}
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/",
        params={"access_token": token, "ids": ",".join(ad_ids), "fields": "name"},
    )
    return {
        k: v.get("name", k)
        for k, v in data.items()
        if isinstance(v, dict) and not v.get("error")
    }


# ---------------------------------------------------------------------------
# Targeting search (autocomplete de interesses e localizações)
# ---------------------------------------------------------------------------

async def search_interests(token: str, query: str, limit: int = 10) -> list[dict]:
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/search",
        params={
            "access_token": token,
            "type": "adinterest",
            "q": query,
            "limit": str(limit),
        },
    )
    return data.get("data", [])


async def search_geo_locations(token: str, query: str, limit: int = 10) -> list[dict]:
    data = await _request(
        "GET",
        f"{settings.meta_graph_url}/search",
        params={
            "access_token": token,
            "type": "adgeolocation",
            "q": query,
            "location_types": json.dumps(["country", "region", "city"]),
            "limit": str(limit),
        },
    )
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Insights — funciona para qualquer nó (conta, campanha, ad set ou anúncio)
# ---------------------------------------------------------------------------

# Campos ricos de insights: além de gasto/impressões/cliques, traz alcance,
# frequência, CPC e os resultados/valores de conversão + ROAS que a Meta calcula.
INSIGHTS_FIELDS_RICH = (
    "spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,"
    "actions,action_values,purchase_roas,cost_per_action_type"
)


async def get_insights(
    token: str,
    node_id: str,
    date_preset: str = "last_30d",
    since: str | None = None,
    until: str | None = None,
    time_increment: int | str | None = None,
    fields: str = "spend,impressions,clicks,ctr,cpm,actions",
    level: str | None = None,
    breakdowns: str | None = None,
) -> list[dict]:
    """
    Busca insights de qualquer nó da Marketing API (conta, campanha, ad set
    ou anúncio — todos expõem a edge /insights com o mesmo formato).

    since/until (YYYY-MM-DD) têm prioridade sobre date_preset quando informados.
    time_increment=1 retorna uma linha por dia (para gráficos de série temporal).
    level ('adset'/'ad') retorna uma linha por entidade filha (desempenho por
    conjunto/anúncio). breakdowns ('age', 'gender', 'publisher_platform'...)
    quebra os números por dimensão.
    """
    params: dict = {"access_token": token, "fields": fields}
    if since and until:
        params["time_range"] = json.dumps({"since": since, "until": until})
    else:
        params["date_preset"] = date_preset
    if time_increment:
        params["time_increment"] = str(time_increment)
    if level:
        params["level"] = level
    if breakdowns:
        params["breakdowns"] = breakdowns

    data = await _request(
        "GET", f"{settings.meta_graph_url}/{node_id}/insights", params=params,
    )
    return data.get("data", [])


async def get_account_insights(
    token: str,
    ad_account_id: str,
    date_preset: str = "last_30d",
    since: str | None = None,
    until: str | None = None,
    fields: str = "spend,impressions,clicks,ctr,cpm,actions",
) -> list[dict]:
    """Fetch account-level insights (level=account is implicit on the act_ node)."""
    return await get_insights(
        token, _act(ad_account_id), date_preset=date_preset, since=since, until=until, fields=fields,
    )
