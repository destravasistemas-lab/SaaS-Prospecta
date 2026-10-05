import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.models.meta_connection import (
    MetaConnection,
    PROVIDER_INSTAGRAM,
    STATUS_ACTIVE,
)
from app.models.schedule import PostSchedule
from app.schemas.schedule import (
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
    PublishMediaRequest, PublishMediaResponse,
    InstagramMediaResponse, InstagramInsightsResponse,
)
from app.services.instagram_service import (
    publish_image_post, publish_video_post, list_media,
    TokenExpiredError,
)
from app.services.meta_token_service import decrypt_token
from app.services import storage_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["instagram-api"])


async def _get_ig_connection(
    db: AsyncSession,
    current_user: User,
    ig_user_id: str | None = None,
) -> tuple[MetaConnection, str, str]:
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_INSTAGRAM,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=400, detail="Instagram não conectado. Conecte-se primeiro.")

    try:
        token = decrypt_token(conn.access_token_encrypted)
    except Exception:
        raise HTTPException(status_code=400, detail="Erro ao descriptografar token. Reconecte o Instagram.")

    ig_id = ig_user_id or conn.ig_business_account_id or conn.meta_user_id
    if not ig_id:
        raise HTTPException(status_code=400, detail="Instagram Business ID não encontrado. Informe o ig_user_id na requisição.")

    return conn, token, ig_id


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_instagram_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn, token, ig_id = await _get_ig_connection(db, current_user)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.ig_graph_url}/{ig_id}",
            params={
                "fields": "id,username,name,account_type,followers_count,media_count,profile_picture_url",
                "access_token": token,
            },
        )
    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"].get("message", "Erro ao buscar perfil"))
    return data


# ---------------------------------------------------------------------------
# Upload de mídia — hospeda o arquivo localmente e devolve uma URL pública.
# A API de publicação do Instagram NÃO aceita bytes: ela busca a mídia por
# uma URL que precisa ser acessível pela internet (em dev, via túnel ngrok).
# ---------------------------------------------------------------------------

UPLOAD_DIR = Path("uploads")
_IMAGE_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_VIDEO_EXT = {"video/mp4": ".mp4", "video/quicktime": ".mov"}
_MAX_IMAGE = 8 * 1024 * 1024
# Alinhado ao limite do bucket do Supabase (50 MB). Se aumentar o bucket,
# aumente aqui também. 50 MB ≈ 1-2 min de vídeo 1080p.
_MAX_VIDEO = 50 * 1024 * 1024


@router.post("/upload-media")
async def upload_media_for_post(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Recebe uma imagem/vídeo, guarda no servidor e retorna a URL pública dela."""
    mime = file.content_type or ""
    if mime in _IMAGE_EXT:
        media_type, ext, limit = "IMAGE", _IMAGE_EXT[mime], _MAX_IMAGE
    elif mime in _VIDEO_EXT:
        media_type, ext, limit = "VIDEO", _VIDEO_EXT[mime], _MAX_VIDEO
    else:
        raise HTTPException(
            415,
            "Formato não suportado. Use JPEG/PNG/WebP (imagem) ou MP4/MOV (vídeo).",
        )

    content = await file.read()
    if len(content) > limit:
        raise HTTPException(413, f"Arquivo excede o limite de {limit // (1024 * 1024)} MB.")

    # Nome imprevisível (uuid) — a URL é pública, então não deve ser adivinhável
    fname = f"{uuid.uuid4().hex}{ext}"

    # Preferência: Supabase Storage (persistente). Fallback: disco local (dev).
    if settings.storage_enabled:
        media_url = await storage_service.upload(fname, content, mime)
    else:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / fname).write_bytes(content)
        media_url = f"{settings.public_backend_url}/api/v1/instagram/uploads/{fname}"

    logger.info("Mídia de post enviada: %s (%s, %d bytes)", fname, media_type, len(content))
    return {"media_url": media_url, "media_type": media_type}


@router.get("/uploads/{filename}")
async def serve_uploaded_media(filename: str):
    """
    Serve uma mídia enviada, SEM autenticação — os servidores da Meta precisam
    buscar essa URL ao publicar o post. O nome é um uuid imprevisível.
    """
    # Proteção contra path traversal: só aceita o nome-base dentro de UPLOAD_DIR
    safe = Path(filename).name
    path = (UPLOAD_DIR / safe).resolve()
    if not str(path).startswith(str(UPLOAD_DIR.resolve())) or not path.is_file():
        raise HTTPException(404, "Mídia não encontrada.")
    return FileResponse(path)


# ---------------------------------------------------------------------------
# Publish media (image or video)
# ---------------------------------------------------------------------------

@router.post("/publish", response_model=PublishMediaResponse)
async def publish_media(
    body: PublishMediaRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn, token, ig_id = await _get_ig_connection(db, current_user, body.ig_user_id)

    caption = body.caption or ""
    if body.hashtags:
        caption += f"\n\n{body.hashtags}"

    try:
        if body.media_type.upper() == "VIDEO":
            result = await publish_video_post(token, ig_id, body.media_url, caption)
        else:
            result = await publish_image_post(token, ig_id, body.media_url, caption)

        media_id = result.get("id")
        logger.info("Published media %s for account %s", media_id, current_user.tenant_id)

        # Ativa a automação de comentário deste post (se definida na publicação)
        if body.automation_keyword and media_id:
            from app.services.post_automation import create_post_automation
            await create_post_automation(
                db, current_user.tenant_id, media_id,
                body.automation_keyword, body.automation_comment_reply,
                body.automation_dm_message, body.automation_link_message,
            )

        # Já está no Instagram: apaga a mídia do storage para não acumular peso.
        await storage_service.delete_by_url(body.media_url)

        return PublishMediaResponse(success=True, media_id=media_id, message="Publicado com sucesso!")

    except TokenExpiredError as e:
        logger.warning("Publish token error (account %s): %s", current_user.tenant_id, e)
        raise HTTPException(status_code=401, detail=f"Token expirado: {e}. Reconecte o Instagram.")
    except ValueError as e:
        # Erro de validação da Meta (ex.: aspect ratio inválido). Fica no log
        # para diagnóstico e volta a mensagem exata da Meta para o usuário.
        logger.warning("Publish rejeitado pela Meta (account %s): %s", current_user.tenant_id, e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Publish failed: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao publicar. Tente novamente.")


# ---------------------------------------------------------------------------
# Schedule a post
# ---------------------------------------------------------------------------

@router.post("/schedule", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn, token, ig_id = await _get_ig_connection(db, current_user, body.ig_user_id)

    now = datetime.now(timezone.utc)
    scheduled_for = body.scheduled_for or (now + timedelta(hours=1))
    # Garante timezone-aware para comparar (datas vindas do front podem ser naive)
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

    if scheduled_for < now - timedelta(minutes=5):
        raise HTTPException(422, "A data de agendamento não pode estar no passado.")
    max_dt = now + timedelta(days=settings.max_schedule_days)
    if scheduled_for > max_dt:
        raise HTTPException(
            422,
            f"Só é possível agendar até {settings.max_schedule_days} dias à frente.",
        )

    schedule = PostSchedule(
        account_id=current_user.tenant_id,
        ig_user_id=ig_id,
        media_type=body.media_type.upper(),
        media_url=body.media_url,
        caption=body.caption,
        hashtags=body.hashtags,
        thumbnail_url=body.thumbnail_url,
        scheduled_for=scheduled_for,
        status="scheduled",
        automation_keyword=body.automation_keyword or None,
        automation_comment_reply=body.automation_comment_reply or None,
        automation_dm_message=body.automation_dm_message or None,
        automation_link_message=body.automation_link_message or None,
    )
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


@router.get("/schedule", response_model=list[ScheduleResponse])
async def list_schedules(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(PostSchedule).where(
        PostSchedule.account_id == current_user.tenant_id
    )
    if status:
        query = query.where(PostSchedule.status == status)
    query = query.order_by(desc(PostSchedule.scheduled_for))

    result = await db.execute(query)
    return result.scalars().all()


@router.put("/schedule/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PostSchedule).where(
            PostSchedule.id == schedule_id,
            PostSchedule.account_id == current_user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    if body.caption is not None:
        schedule.caption = body.caption
    if body.hashtags is not None:
        schedule.hashtags = body.hashtags
    if body.scheduled_for is not None:
        schedule.scheduled_for = body.scheduled_for
    if body.status is not None:
        schedule.status = body.status

    await db.flush()
    await db.refresh(schedule)
    return schedule


@router.delete("/schedule/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PostSchedule).where(
            PostSchedule.id == schedule_id,
            PostSchedule.account_id == current_user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    await db.delete(schedule)
    return {"success": True}


@router.post("/schedule/{schedule_id}/publish-now", response_model=PublishMediaResponse)
async def publish_scheduled_now(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PostSchedule).where(
            PostSchedule.id == schedule_id,
            PostSchedule.account_id == current_user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    conn, token, ig_id = await _get_ig_connection(db, current_user, schedule.ig_user_id)

    caption = schedule.caption or ""
    if schedule.hashtags:
        caption += f"\n\n{schedule.hashtags}"

    try:
        if schedule.media_type == "VIDEO":
            result = await publish_video_post(token, ig_id, schedule.media_url, caption)
        else:
            result = await publish_image_post(token, ig_id, schedule.media_url, caption)

        media_id = result.get("id")
        schedule.status = "published"
        schedule.published_at = datetime.now(timezone.utc)
        schedule.media_id_response = media_id
        schedule.error_message = None
        await db.flush()

        # Ativa a automação de comentário deste post (se definida no agendamento)
        if schedule.automation_keyword and media_id:
            from app.services.post_automation import create_post_automation
            await create_post_automation(
                db, current_user.tenant_id, media_id,
                schedule.automation_keyword, schedule.automation_comment_reply,
                schedule.automation_dm_message, schedule.automation_link_message,
            )

        # Já publicado: apaga a mídia do storage (o registro fica como "check").
        await storage_service.delete_by_url(schedule.media_url)

        return PublishMediaResponse(success=True, media_id=media_id, message="Publicado com sucesso!")

    except TokenExpiredError as e:
        schedule.status = "failed"
        schedule.error_message = str(e)
        await db.flush()
        logger.warning("Publish-now token error (schedule %s): %s", schedule.id, e)
        raise HTTPException(status_code=401, detail=f"Token expirado: {e}. Reconecte o Instagram.")
    except Exception as e:
        schedule.status = "failed"
        schedule.error_message = str(e)
        schedule.retry_count = (schedule.retry_count or 0) + 1
        await db.flush()
        logger.warning("Publish-now falhou (schedule %s): %s", schedule.id, e)
        raise HTTPException(status_code=500, detail=f"Erro ao publicar: {e}")


# ---------------------------------------------------------------------------
# List media from Instagram
# ---------------------------------------------------------------------------

@router.get("/media", response_model=list[InstagramMediaResponse])
async def get_media(
    ig_user_id: str | None = Query(None),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn, token, ig_id = await _get_ig_connection(db, current_user, ig_user_id)

    try:
        media_list = await list_media(token, ig_id, limit)
    except TokenExpiredError as e:
        raise HTTPException(status_code=401, detail=f"Token expirado: {e}. Reconecte o Instagram.")
    except Exception as e:
        logger.error("list_media failed: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao listar mídias.")

    result = []
    for m in media_list:
        ts = None
        if m.get("timestamp"):
            try:
                ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        result.append(InstagramMediaResponse(
            id=m["id"],
            media_type=m.get("media_type", ""),
            media_url=m.get("media_url"),
            thumbnail_url=m.get("thumbnail_url"),
            caption=m.get("caption"),
            timestamp=ts,
            like_count=m.get("like_count", 0),
            comments_count=m.get("comments_count", 0),
        ))
    return result


# ---------------------------------------------------------------------------
# Instagram Insights / Metrics
# ---------------------------------------------------------------------------

@router.get("/insights", response_model=InstagramInsightsResponse)
async def get_insights(
    ig_user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn, token, ig_id = await _get_ig_connection(db, current_user, ig_user_id)

    # 1) Dados do perfil (seguidores/posts) — precisa funcionar sempre.
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            user_resp = await client.get(
                f"{settings.ig_graph_url}/{ig_id}",
                params={
                    "access_token": token,
                    "fields": "id,username,name,followers_count,follows_count,media_count,profile_picture_url",
                },
            )
            user_data = user_resp.json()
            logger.info("IG user data: %s", user_data)
    except Exception as e:
        logger.error("Failed to fetch IG profile: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao buscar dados do Instagram.")

    # 2) Insights — best-effort. A API nova (Instagram Login) removeu métricas
    # antigas (impressions, email_contacts, phone_call_clicks, get_direction_clicks);
    # `views` substitui `impressions`. Se falhar (ex.: conta com poucos
    # seguidores), zera as métricas em vez de derrubar a resposta inteira.
    insights_data: dict = {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            insights_resp = await client.get(
                f"{settings.ig_graph_url}/{ig_id}/insights",
                params={
                    "access_token": token,
                    "metric": "reach,views,profile_views,website_clicks",
                    "period": "day",
                    "since": (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "until": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                },
            )
            insights_data = insights_resp.json()
            logger.info("IG insights: %s", insights_data)
            if insights_data.get("error"):
                logger.warning("IG insights indisponível: %s", insights_data["error"])
    except Exception as e:
        logger.warning("Falha ao buscar insights IG (seguindo sem métricas): %s", e)

    followers = user_data.get("followers_count", 0) or 0
    follows = user_data.get("follows_count", 0) or 0
    media_count = user_data.get("media_count", 0) or 0

    # `views` alimenta o campo "impressions" da resposta (equivalente novo).
    metrics = {
        "reach": 0, "views": 0, "profile_views": 0, "website_clicks": 0,
    }

    for item in insights_data.get("data", []):
        name = item.get("name")
        total = sum(v.get("value", 0) for v in item.get("values", []) if isinstance(v.get("value"), (int, float)))
        if name in metrics:
            metrics[name] = int(total)

    engagement = 0
    if followers > 0 and metrics["reach"] > 0:
        engagement = round((metrics["reach"] / followers) * 100, 2)

    return InstagramInsightsResponse(
        followers_count=followers,
        follows_count=follows,
        media_count=media_count,
        profile_views=metrics["profile_views"],
        reach=metrics["reach"],
        impressions=metrics["views"],  # `views` é o substituto de `impressions`
        engagement=engagement,
        website_clicks=metrics["website_clicks"],
        email_contacts=0,
        phone_call_clicks=0,
        get_direction_clicks=0,
        followers_delta=followers,
        profile_views_delta=metrics["profile_views"],
    )


# ---------------------------------------------------------------------------
# IG Stories insights
# ---------------------------------------------------------------------------

@router.get("/stories-insights")
async def get_stories_insights(
    ig_user_id: str | None = Query(None),
    limit: int = Query(10, le=25),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn, token, ig_id = await _get_ig_connection(db, current_user, ig_user_id)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            stories_resp = await client.get(
                f"{settings.ig_graph_url}/{ig_id}/stories",
                params={
                    "access_token": token,
                    "fields": "id,media_type,media_url,thumbnail_url,timestamp",
                    "limit": str(limit),
                },
            )
            stories_data = stories_resp.json()
            stories = stories_data.get("data", [])

            results = []
            for story in stories:
                story_id = story["id"]
                insights = await client.get(
                    f"{settings.ig_graph_url}/{story_id}/insights",
                    params={
                        "access_token": token,
                        "metric": "reach,impressions,exits,replies,taps_forward,taps_back",
                    },
                )
                ins_data = insights.json()
                ins_map = {}
                for item in ins_data.get("data", []):
                    vals = item.get("values", [{}])
                    ins_map[item["name"]] = vals[0].get("value", 0) if vals else 0

                ts = story.get("timestamp")
                if ts:
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        ts = None

                results.append({
                    "id": story_id,
                    "media_type": story.get("media_type"),
                    "media_url": story.get("media_url"),
                    "thumbnail_url": story.get("thumbnail_url"),
                    "timestamp": ts.isoformat() if ts else None,
                    "reach": ins_map.get("reach", 0),
                    "impressions": ins_map.get("impressions", 0),
                    "exits": ins_map.get("exits", 0),
                    "replies": ins_map.get("replies", 0),
                    "taps_forward": ins_map.get("taps_forward", 0),
                    "taps_back": ins_map.get("taps_back", 0),
                })

            return {"stories": results}

    except Exception as e:
        logger.error("Failed to fetch IG stories: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao buscar stories.")


# ---------------------------------------------------------------------------
# Update IG Business ID manually
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class UpdateIgIdRequest(BaseModel):
    ig_business_account_id: str


@router.put("/connection/ig-id")
async def update_ig_business_id(
    body: UpdateIgIdRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_INSTAGRAM,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=400, detail="Instagram não conectado.")

    conn.ig_business_account_id = body.ig_business_account_id
    await db.flush()
    return {"success": True, "ig_business_account_id": body.ig_business_account_id}


class SendDMRequest(BaseModel):
    recipient_ig_user_id: str
    message: str
    lead_id: str | None = None


@router.post("/dm/send")
async def send_instagram_dm(
    body: SendDMRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Envia uma DM para um usuário do Instagram via Graph API."""
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.account_id == current_user.tenant_id,
            MetaConnection.provider == PROVIDER_INSTAGRAM,
            MetaConnection.status == STATUS_ACTIVE,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=400, detail="Instagram não conectado.")

    if not conn.ig_business_account_id:
        raise HTTPException(
            status_code=400,
            detail="ID da conta Instagram Business não configurado.",
        )

    token = decrypt_token(conn.access_token_encrypted)
    ig_biz_id = conn.ig_business_account_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.ig_graph_url}/{ig_biz_id}/messages",
            json={
                "recipient": {"id": body.recipient_ig_user_id},
                "message": {"text": body.message},
            },
            params={"access_token": token},
        )

    if not resp.is_success:
        error_detail = resp.json().get("error", {}).get("message", resp.text)
        logger.error("Erro ao enviar DM Instagram: %s", resp.text)
        raise HTTPException(status_code=400, detail=f"Erro ao enviar DM: {error_detail}")

    # Atualiza o status do lead para 'contacted' se lead_id fornecido
    if body.lead_id:
        from app.models.lead import Lead, LeadStatus
        from sqlalchemy import select as sa_select
        lead_result = await db.execute(
            sa_select(Lead).where(
                Lead.id == body.lead_id,
                Lead.account_id == current_user.tenant_id,
            )
        )
        lead = lead_result.scalar_one_or_none()
        if lead and lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.CONTACTED
            await db.flush()

    return {"status": "sent", "message_id": resp.json().get("message_id")}
