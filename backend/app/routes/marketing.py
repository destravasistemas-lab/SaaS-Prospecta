import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field, field_validator


def _coerce_optional_str(v):
    """Graph às vezes devolve orçamento/lance como int; normaliza pra string."""
    return None if v is None else str(v)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.lead import Lead
from app.models.meta_connection import MetaConnection, PROVIDER_ADS, STATUS_ACTIVE
from app.services.meta_token_service import safe_decrypt_token
from app.services import ads_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketing", tags=["marketing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AdAccountOut(BaseModel):
    id: str
    name: str
    account_status: int = 0
    currency: str = "BRL"
    business_name: str | None = None


class SwitchAdAccountRequest(BaseModel):
    ad_account_id: str = Field(..., description="ID no formato 'act_123' ou '123'")


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    objective: str = Field(default="OUTCOME_LEADS")
    status: str = Field(default="PAUSED")
    is_adset_budget_sharing_enabled: bool = Field(default=False)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, pattern="^(ACTIVE|PAUSED)$")
    daily_budget_cents: int | None = Field(default=None, ge=100)


class CampaignOut(BaseModel):
    id: str
    name: str
    status: str
    objective: str
    daily_budget: str | None = None
    lifetime_budget: str | None = None
    start_time: str | None = None
    stop_time: str | None = None

    _coerce = field_validator("daily_budget", "lifetime_budget", mode="before")(_coerce_optional_str)


class TargetingSpec(BaseModel):
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: list[int] | None = Field(default=None, description="1=masculino, 2=feminino; omitir = todos")
    country_codes: list[str] = Field(default_factory=lambda: ["BR"])
    interest_ids: list[str] = Field(default_factory=list)


class AdSetCreate(BaseModel):
    campaign_id: str
    name: str = Field(..., min_length=1, max_length=255)
    daily_budget_cents: int = Field(default=1000, ge=100)
    bid_amount_cents: int | None = Field(default=None, ge=1)
    billing_event: str = Field(default="IMPRESSIONS")
    optimization_goal: str = Field(default="REACH")
    end_time: str | None = None
    targeting: TargetingSpec = Field(default_factory=TargetingSpec)


class AdSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, pattern="^(ACTIVE|PAUSED)$")
    daily_budget_cents: int | None = Field(default=None, ge=100)
    bid_amount_cents: int | None = Field(default=None, ge=1)


class AdSetOut(BaseModel):
    id: str
    name: str
    status: str
    daily_budget: str | None = None
    lifetime_budget: str | None = None
    bid_amount: str | None = None
    billing_event: str | None = None
    optimization_goal: str | None = None
    end_time: str | None = None

    _coerce = field_validator("daily_budget", "lifetime_budget", "bid_amount", mode="before")(_coerce_optional_str)


class CarouselItem(BaseModel):
    image_url: str
    link_url: str | None = None
    message: str = ""


class AdCreativeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    message: str = Field(default="")
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    video_id: Optional[str] = None
    video_thumb_url: Optional[str] = None
    carousel_items: list[CarouselItem] | None = Field(default=None, min_length=2, max_length=10)
    # Impulsionar um post existente do Instagram (link_url é obrigatório nesse caso)
    source_instagram_media_id: Optional[str] = None
    cta_type: str = Field(default="LEARN_MORE")


class InstagramPostOut(BaseModel):
    id: str
    caption: str | None = None
    media_type: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None
    timestamp: str | None = None


class AdCreate(BaseModel):
    ad_set_id: str
    creative_id: str
    name: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="PAUSED")


class AdUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, pattern="^(ACTIVE|PAUSED)$")


class AdOut(BaseModel):
    id: str
    name: str
    status: str
    creative_id: str | None = None
    creative_name: str | None = None
    thumbnail_url: str | None = None


class AdInsightsOut(BaseModel):
    spend: float = 0.0
    impressions: int = 0
    reach: int = 0
    frequency: float = 0.0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    results: float = 0.0
    result_label: str = ""
    cost_per_result: float = 0.0
    purchase_value: float = 0.0
    roas: float = 0.0


class EntityInsightsOut(BaseModel):
    """Desempenho de uma entidade filha (conjunto ou anúncio) de uma campanha."""
    id: str
    name: str | None = None
    spend: float = 0.0
    impressions: int = 0
    reach: int = 0
    clicks: int = 0
    ctr: float = 0.0
    results: float = 0.0
    result_label: str = ""
    cost_per_result: float = 0.0


class BreakdownRowOut(BaseModel):
    """Uma linha de insights quebrada por dimensão (idade, gênero, plataforma...)."""
    key: str
    spend: float = 0.0
    impressions: int = 0
    reach: int = 0
    clicks: int = 0
    ctr: float = 0.0
    results: float = 0.0


class InsightsPoint(BaseModel):
    date: str
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0


class TargetingOptionOut(BaseModel):
    id: str
    name: str
    audience_size: int | None = None
    type: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_ads_connection(
    current_user: User, db: AsyncSession
) -> tuple[MetaConnection, str]:
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_ADS,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma conta de anúncios conectada. Conecte pelo onboarding.",
        )
    token = safe_decrypt_token(conn.access_token_encrypted)
    if not token:
        raise HTTPException(status_code=400, detail="Token de acesso inválido ou expirado.")
    return conn, token


def _require_ad_account(conn: MetaConnection) -> str:
    if not conn.ad_account_id:
        raise HTTPException(status_code=400, detail="Conta de anúncios não configurada.")
    return conn.ad_account_id


def _meta_error(result: dict, default: str) -> str:
    """Extrai a mensagem mais amigável do erro da Graph (prioriza error_user_msg)."""
    err = (result or {}).get("error", {}) or {}
    return err.get("error_user_msg") or err.get("error_user_title") or err.get("message") or default


def _build_targeting(t: TargetingSpec) -> dict:
    targeting: dict = {
        "age_min": t.age_min,
        "age_max": t.age_max,
        "geo_locations": {"countries": t.country_codes or ["BR"]},
    }
    if t.genders:
        targeting["genders"] = t.genders
    if t.interest_ids:
        targeting["flexible_spec"] = [{"interests": [{"id": i} for i in t.interest_ids]}]
    return targeting


# Prioridade de "resultado": a conversão mais valiosa presente vira o resultado
# principal (compras > leads > conversas > cliques no link). Cobre os objetivos
# mais comuns sem depender de saber o objetivo da campanha em cada linha.
_RESULT_ACTIONS: list[tuple[str, str]] = [
    ("offsite_conversion.fb_pixel_purchase", "Compras"),
    ("omni_purchase", "Compras"),
    ("purchase", "Compras"),
    ("onsite_conversion.purchase", "Compras"),
    ("offsite_conversion.fb_pixel_lead", "Leads"),
    ("onsite_conversion.lead_grouped", "Leads"),
    ("leadgen.other", "Leads"),
    ("lead", "Leads"),
    ("onsite_conversion.messaging_conversation_started_7d", "Conversas"),
    ("link_click", "Cliques no link"),
    ("landing_page_view", "Visitas à página"),
]
_PURCHASE_VALUE_KEYS = ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase")


def _actions_map(rows: list | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for a in rows or []:
        try:
            out[a.get("action_type", "")] = float(a.get("value", 0) or 0)
        except (TypeError, ValueError):
            continue
    return out


def _pick_result(actions: list | None) -> tuple[float, str]:
    """Escolhe a conversão mais relevante presente → (quantidade, rótulo)."""
    m = _actions_map(actions)
    for action_type, label in _RESULT_ACTIONS:
        if m.get(action_type, 0) > 0:
            return m[action_type], label
    return 0.0, ""


def _purchase_value(item: dict) -> float:
    vals = _actions_map(item.get("action_values"))
    for key in _PURCHASE_VALUE_KEYS:
        if vals.get(key, 0) > 0:
            return vals[key]
    return 0.0


def _roas(item: dict, spend: float) -> float:
    pr = item.get("purchase_roas") or []
    if pr:
        try:
            return float(pr[0].get("value", 0) or 0)
        except (TypeError, ValueError):
            pass
    value = _purchase_value(item)
    return round(value / spend, 2) if spend else 0.0


def _insights_row(item: dict) -> AdInsightsOut:
    spend = float(item.get("spend", 0) or 0)
    results, label = _pick_result(item.get("actions"))
    return AdInsightsOut(
        spend=spend,
        impressions=int(item.get("impressions", 0) or 0),
        reach=int(item.get("reach", 0) or 0),
        frequency=float(item.get("frequency", 0) or 0),
        clicks=int(item.get("clicks", 0) or 0),
        ctr=float(item.get("ctr", 0) or 0),
        cpc=float(item.get("cpc", 0) or 0),
        cpm=float(item.get("cpm", 0) or 0),
        results=results,
        result_label=label,
        cost_per_result=round(spend / results, 2) if results else 0.0,
        purchase_value=_purchase_value(item),
        roas=_roas(item, spend),
    )


def _entity_row(item: dict, id_field: str, name_field: str) -> EntityInsightsOut:
    spend = float(item.get("spend", 0) or 0)
    results, label = _pick_result(item.get("actions"))
    return EntityInsightsOut(
        id=item.get(id_field, ""),
        name=item.get(name_field),
        spend=spend,
        impressions=int(item.get("impressions", 0) or 0),
        reach=int(item.get("reach", 0) or 0),
        clicks=int(item.get("clicks", 0) or 0),
        ctr=float(item.get("ctr", 0) or 0),
        results=results,
        result_label=label,
        cost_per_result=round(spend / results, 2) if results else 0.0,
    )


# ---------------------------------------------------------------------------
# Ad Accounts
# ---------------------------------------------------------------------------

@router.get("/ad-accounts", response_model=list[AdAccountOut])
async def api_list_ad_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    accounts = await ads_service.list_ad_accounts(token)
    return [
        AdAccountOut(
            id=a.get("id", ""),
            name=a.get("name", ""),
            account_status=a.get("account_status", 0),
            currency=a.get("currency", "BRL"),
            business_name=a.get("business_name"),
        )
        for a in accounts
    ]


@router.put("/ad-account")
async def api_switch_ad_account(
    body: SwitchAdAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Troca qual conta de anúncios este tenant usa (para quem tem mais de uma)."""
    conn, _ = await _get_ads_connection(current_user, db)
    conn.ad_account_id = body.ad_account_id
    await db.flush()
    return {"success": True, "ad_account_id": conn.ad_account_id}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@router.get("/campaigns", response_model=list[CampaignOut])
async def api_list_campaigns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)
    data = await ads_service.list_campaigns(token, ad_account_id)
    return [
        CampaignOut(
            id=c.get("id", ""),
            name=c.get("name", ""),
            status=c.get("status", ""),
            objective=c.get("objective", ""),
            daily_budget=c.get("daily_budget"),
            lifetime_budget=c.get("lifetime_budget"),
            start_time=c.get("start_time"),
            stop_time=c.get("stop_time"),
        )
        for c in data
    ]


@router.post("/campaigns")
async def api_create_campaign(
    body: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)
    result = await ads_service.create_campaign(
        token, ad_account_id, body.name, body.objective, body.status,
        is_adset_budget_sharing_enabled=body.is_adset_budget_sharing_enabled,
    )
    if "id" not in result:
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao criar campanha"))
    return {"success": True, "campaign_id": result["id"]}


@router.patch("/campaigns/{campaign_id}")
async def api_update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    fields: dict = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.status is not None:
        fields["status"] = body.status
    if body.daily_budget_cents is not None:
        fields["daily_budget"] = str(body.daily_budget_cents)
    if not fields:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    result = await ads_service.update_campaign(token, campaign_id, **fields)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao atualizar campanha."))
    return {"success": True}


@router.delete("/campaigns/{campaign_id}")
async def api_delete_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    result = await ads_service.delete_campaign(token, campaign_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao excluir campanha."))
    return {"success": True}


@router.post("/campaigns/{campaign_id}/copy")
async def api_copy_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Duplica a campanha inteira (com conjuntos e anúncios), pausada."""
    _, token = await _get_ads_connection(current_user, db)
    result = await ads_service.copy_object(token, campaign_id, deep_copy=True)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao duplicar campanha."))
    return {"success": True, "result": result}


@router.get("/campaigns/{campaign_id}/insights", response_model=list[InsightsPoint])
async def api_campaign_insights(
    campaign_id: str,
    since: str | None = Query(None, description="YYYY-MM-DD"),
    until: str | None = Query(None, description="YYYY-MM-DD"),
    date_preset: str = Query("last_30d"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Série temporal (1 ponto por dia) para o gráfico de gastos da campanha."""
    _, token = await _get_ads_connection(current_user, db)
    data = await ads_service.get_insights(
        token, campaign_id, date_preset=date_preset, since=since, until=until,
        time_increment=1, fields="spend,impressions,clicks,date_start",
    )
    return [
        InsightsPoint(
            date=item.get("date_start", ""),
            spend=float(item.get("spend", 0) or 0),
            impressions=int(item.get("impressions", 0) or 0),
            clicks=int(item.get("clicks", 0) or 0),
        )
        for item in data
    ]


@router.get("/campaigns/{campaign_id}/ad-sets", response_model=list[AdSetOut])
async def api_list_ad_sets(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    data = await ads_service.list_ad_sets(token, campaign_id)
    return [
        AdSetOut(
            id=a.get("id", ""),
            name=a.get("name", ""),
            status=a.get("status", ""),
            daily_budget=a.get("daily_budget"),
            lifetime_budget=a.get("lifetime_budget"),
            bid_amount=a.get("bid_amount"),
            billing_event=a.get("billing_event"),
            optimization_goal=a.get("optimization_goal"),
            end_time=a.get("end_time"),
        )
        for a in data
    ]


# ---------------------------------------------------------------------------
# Ad Sets
# ---------------------------------------------------------------------------

@router.post("/ad-sets")
async def api_create_ad_set(
    body: AdSetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)
    result = await ads_service.create_ad_set(
        token, ad_account_id, body.campaign_id, body.name, body.daily_budget_cents,
        billing_event=body.billing_event, optimization_goal=body.optimization_goal,
        targeting=_build_targeting(body.targeting),
        bid_amount=body.bid_amount_cents, end_time=body.end_time,
    )
    if "id" not in result:
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao criar conjunto"))
    return {"success": True, "ad_set_id": result["id"]}


@router.patch("/ad-sets/{ad_set_id}")
async def api_update_ad_set(
    ad_set_id: str,
    body: AdSetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    fields: dict = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.status is not None:
        fields["status"] = body.status
    if body.daily_budget_cents is not None:
        fields["daily_budget"] = str(body.daily_budget_cents)
    if body.bid_amount_cents is not None:
        fields["bid_amount"] = str(body.bid_amount_cents)
    if not fields:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    result = await ads_service.update_ad_set(token, ad_set_id, **fields)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao atualizar conjunto."))
    return {"success": True}


@router.delete("/ad-sets/{ad_set_id}")
async def api_delete_ad_set(
    ad_set_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    result = await ads_service.delete_ad_set(token, ad_set_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao excluir conjunto."))
    return {"success": True}


@router.post("/ad-sets/{ad_set_id}/copy")
async def api_copy_ad_set(
    ad_set_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Duplica o conjunto de anúncios (com seus anúncios), pausado."""
    _, token = await _get_ads_connection(current_user, db)
    result = await ads_service.copy_object(token, ad_set_id, deep_copy=True)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao duplicar conjunto."))
    return {"success": True, "result": result}


@router.get("/ad-sets/{ad_set_id}/ads", response_model=list[AdOut])
async def api_list_ads(
    ad_set_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    data = await ads_service.list_ads(token, ad_set_id)
    out = []
    for a in data:
        creative = a.get("creative", {}) or {}
        out.append(AdOut(
            id=a.get("id", ""),
            name=a.get("name", ""),
            status=a.get("status", ""),
            creative_id=creative.get("id"),
            creative_name=creative.get("name"),
            thumbnail_url=creative.get("thumbnail_url"),
        ))
    return out


# ---------------------------------------------------------------------------
# Creatives & Ads
# ---------------------------------------------------------------------------

@router.post("/videos/upload")
async def api_upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sobe um vídeo para a conta de anúncios — necessário antes de criar um criativo de vídeo."""
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)

    content = await file.read()
    if len(content) > 300 * 1024 * 1024:
        raise HTTPException(413, "Vídeo excede o limite de 300 MB.")

    result = await ads_service.upload_ad_video(token, ad_account_id, content, file.filename or "video.mp4")
    video_id = result.get("id")
    if not video_id:
        raise HTTPException(502, result.get("error", {}).get("message", "Falha no upload do vídeo."))
    return {"video_id": video_id}


@router.get("/instagram-posts", response_model=list[InstagramPostOut])
async def api_list_instagram_posts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Posts do Instagram que podem ser impulsionados como anúncio."""
    conn, token = await _get_ads_connection(current_user, db)
    ig = await ads_service.get_promotable_instagram(token, conn.page_id)
    if not ig.get("ig_user_id"):
        raise HTTPException(400, "Nenhuma conta do Instagram vinculada a uma Página do Facebook nesta conta de anúncios.")
    posts = await ads_service.list_instagram_posts(token, ig["ig_user_id"])
    return [
        InstagramPostOut(
            id=p.get("id", ""),
            caption=p.get("caption"),
            media_type=p.get("media_type"),
            thumbnail_url=p.get("thumbnail_url") or p.get("media_url"),
            permalink=p.get("permalink"),
            timestamp=p.get("timestamp"),
        )
        for p in posts
    ]


@router.post("/creatives")
async def api_create_creative(
    body: AdCreativeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)

    # Impulsionar um post existente do Instagram
    if body.source_instagram_media_id:
        if not body.link_url:
            raise HTTPException(400, "Para impulsionar um post, informe o link de destino.")
        ig = await ads_service.get_promotable_instagram(token, conn.page_id)
        if not ig.get("ig_user_id"):
            raise HTTPException(400, "Nenhuma conta do Instagram vinculada a uma Página do Facebook.")
        result = await ads_service.create_creative_from_post(
            token, ad_account_id, body.name, ig["ig_user_id"],
            body.source_instagram_media_id, body.link_url, cta_type=body.cta_type,
        )
        if "id" not in result:
            raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao criar criativo do post"))
        return {"success": True, "creative_id": result["id"]}

    if not body.message.strip():
        raise HTTPException(422, "A mensagem do anúncio é obrigatória.")
    page_id = conn.page_id or ""
    if not page_id:
        raise HTTPException(
            status_code=400,
            detail="Página do Facebook não configurada nesta conexão de anúncios.",
        )
    result = await ads_service.create_ad_creative(
        token, ad_account_id, body.name, page_id, body.message,
        image_url=body.image_url, link_url=body.link_url,
        video_id=body.video_id, video_thumb_url=body.video_thumb_url,
        carousel_items=[i.model_dump() for i in body.carousel_items] if body.carousel_items else None,
    )
    if "id" not in result:
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao criar criativo"))
    return {"success": True, "creative_id": result["id"]}


@router.post("/ads")
async def api_create_ad(
    body: AdCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)
    result = await ads_service.create_ad(token, ad_account_id, body.ad_set_id, body.creative_id, body.name, body.status)
    if "id" not in result:
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao criar anúncio"))
    return {"success": True, "ad_id": result["id"]}


@router.patch("/ads/{ad_id}")
async def api_update_ad(
    ad_id: str,
    body: AdUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    fields: dict = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.status is not None:
        fields["status"] = body.status
    if not fields:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    result = await ads_service.update_ad(token, ad_id, **fields)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao atualizar anúncio."))
    return {"success": True}


@router.delete("/ads/{ad_id}")
async def api_delete_ad(
    ad_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    result = await ads_service.delete_ad(token, ad_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao excluir anúncio."))
    return {"success": True}


@router.post("/ads/{ad_id}/copy")
async def api_copy_ad(
    ad_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Duplica o anúncio, pausado."""
    _, token = await _get_ads_connection(current_user, db)
    result = await ads_service.copy_object(token, ad_id, deep_copy=False)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=_meta_error(result, "Erro ao duplicar anúncio."))
    return {"success": True, "result": result}


# ---------------------------------------------------------------------------
# Targeting search (autocomplete)
# ---------------------------------------------------------------------------

@router.get("/targeting/interests", response_model=list[TargetingOptionOut])
async def api_search_interests(
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    data = await ads_service.search_interests(token, q)
    return [
        TargetingOptionOut(id=i.get("id", ""), name=i.get("name", ""), audience_size=i.get("audience_size"))
        for i in data
    ]


@router.get("/targeting/locations", response_model=list[TargetingOptionOut])
async def api_search_locations(
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, token = await _get_ads_connection(current_user, db)
    data = await ads_service.search_geo_locations(token, q)
    return [
        TargetingOptionOut(id=i.get("key", i.get("id", "")), name=i.get("name", ""), type=i.get("type"))
        for i in data
    ]


# ---------------------------------------------------------------------------
# Account-level insights
# ---------------------------------------------------------------------------

@router.get("/insights", response_model=AdInsightsOut)
async def api_insights(
    since: str | None = Query(None, description="YYYY-MM-DD"),
    until: str | None = Query(None, description="YYYY-MM-DD"),
    date_preset: str = Query("last_30d"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn, token = await _get_ads_connection(current_user, db)
    ad_account_id = _require_ad_account(conn)
    data = await ads_service.get_account_insights(
        token, ad_account_id, date_preset=date_preset, since=since, until=until,
        fields=ads_service.INSIGHTS_FIELDS_RICH,
    )
    if not data:
        return AdInsightsOut()
    return _insights_row(data[0])


@router.get("/campaigns/{campaign_id}/insights/by-level", response_model=list[EntityInsightsOut])
async def api_campaign_insights_by_level(
    campaign_id: str,
    level: str = Query("adset", pattern="^(adset|ad)$"),
    date_preset: str = Query("last_30d"),
    since: str | None = Query(None),
    until: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Desempenho por conjunto (level=adset) ou por anúncio (level=ad) de uma campanha."""
    _, token = await _get_ads_connection(current_user, db)
    id_field, name_field = ("adset_id", "adset_name") if level == "adset" else ("ad_id", "ad_name")
    fields = f"{id_field},{name_field},spend,impressions,reach,clicks,ctr,actions"
    data = await ads_service.get_insights(
        token, campaign_id, date_preset=date_preset, since=since, until=until,
        fields=fields, level=level,
    )
    return [_entity_row(item, id_field, name_field) for item in data]


# Dimensões de breakdown suportadas → campo retornado pela Graph que carrega o valor
_BREAKDOWN_KEYS: dict[str, str] = {
    "age": "age",
    "gender": "gender",
    "publisher_platform": "publisher_platform",
    "impression_device": "impression_device",
    "region": "region",
}


@router.get("/campaigns/{campaign_id}/insights/breakdown", response_model=list[BreakdownRowOut])
async def api_campaign_insights_breakdown(
    campaign_id: str,
    dimension: str = Query("age"),
    date_preset: str = Query("last_30d"),
    since: str | None = Query(None),
    until: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Insights da campanha quebrados por dimensão (idade, gênero, plataforma, dispositivo, região)."""
    if dimension not in _BREAKDOWN_KEYS:
        raise HTTPException(422, f"Dimensão inválida. Use: {', '.join(_BREAKDOWN_KEYS)}")
    _, token = await _get_ads_connection(current_user, db)
    key = _BREAKDOWN_KEYS[dimension]
    data = await ads_service.get_insights(
        token, campaign_id, date_preset=date_preset, since=since, until=until,
        fields="spend,impressions,reach,clicks,ctr,actions", breakdowns=dimension,
    )
    rows: list[BreakdownRowOut] = []
    for item in data:
        results, _ = _pick_result(item.get("actions"))
        rows.append(BreakdownRowOut(
            key=str(item.get(key, "—")),
            spend=float(item.get("spend", 0) or 0),
            impressions=int(item.get("impressions", 0) or 0),
            reach=int(item.get("reach", 0) or 0),
            clicks=int(item.get("clicks", 0) or 0),
            ctr=float(item.get("ctr", 0) or 0),
            results=results,
        ))
    return rows


# ---------------------------------------------------------------------------
# Atribuição — leads gerados por anúncio (CTWA, IG Direct e Lead Ads)
# ---------------------------------------------------------------------------

class AdAttributionOut(BaseModel):
    ad_id: str
    ad_name: str | None = None
    leads: int


class AttributionSummaryOut(BaseModel):
    total_leads: int
    leads_from_ads: int
    by_ad: list[AdAttributionOut]


@router.get("/attribution", response_model=AttributionSummaryOut)
async def api_attribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Quantos leads cada anúncio gerou — cruzando os leads capturados
    (Click-to-WhatsApp, referral do Direct e formulários de Lead Ads) com o
    ID do anúncio de origem. É o ROI real: conversas/leads, não cliques.
    """
    total = (await db.execute(
        select(func.count(Lead.id)).where(Lead.account_id == current_user.tenant_id)
    )).scalar() or 0

    rows = (await db.execute(
        select(Lead.origin_ad_id, func.count(Lead.id))
        .where(
            Lead.account_id == current_user.tenant_id,
            Lead.origin_ad_id.isnot(None),
        )
        .group_by(Lead.origin_ad_id)
        .order_by(func.count(Lead.id).desc())
        .limit(50)
    )).all()

    # Enriquece com os nomes dos anúncios (melhor esforço — sem conexão de
    # Ads ativa, mostra só o ID)
    ad_names: dict[str, str] = {}
    if rows:
        try:
            _, token = await _get_ads_connection(current_user, db)
            ad_names = await ads_service.get_ad_names(token, [r[0] for r in rows])
        except HTTPException:
            pass
        except Exception as exc:
            logger.debug("Não foi possível resolver nomes de anúncios: %s", exc)

    by_ad = [
        AdAttributionOut(ad_id=ad_id, ad_name=ad_names.get(ad_id), leads=count)
        for ad_id, count in rows
    ]
    return AttributionSummaryOut(
        total_leads=total,
        leads_from_ads=sum(a.leads for a in by_ad),
        by_ad=by_ad,
    )


class AdLeadOut(BaseModel):
    name: str
    phone: str
    ad_name: str | None = None


@router.get("/attribution/leads", response_model=list[AdLeadOut])
async def api_attribution_leads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Leads gerados pelos anúncios que têm telefone — prontos para exportar em CSV
    (nome, telefone) e importar direto na ferramenta de disparo (Follow-ups).
    """
    rows = (await db.execute(
        select(Lead.name, Lead.phone, Lead.origin_ad_id)
        .where(
            Lead.account_id == current_user.tenant_id,
            Lead.origin_ad_id.isnot(None),
            Lead.phone.isnot(None),
        )
        .order_by(Lead.id.desc())
        .limit(5000)
    )).all()

    ad_ids = list({r[2] for r in rows if r[2]})
    ad_names: dict[str, str] = {}
    if ad_ids:
        try:
            _, token = await _get_ads_connection(current_user, db)
            ad_names = await ads_service.get_ad_names(token, ad_ids)
        except HTTPException:
            pass
        except Exception as exc:
            logger.debug("Não foi possível resolver nomes de anúncios: %s", exc)

    return [
        AdLeadOut(name=name or phone, phone=phone, ad_name=ad_names.get(ad_id))
        for name, phone, ad_id in rows
    ]
