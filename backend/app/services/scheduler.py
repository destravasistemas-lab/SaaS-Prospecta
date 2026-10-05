import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_

from app.core.database import async_session
from app.core.config import settings
from app.models.schedule import PostSchedule
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.services.instagram_service import publish_image_post, publish_video_post, TokenExpiredError
from app.services.meta_token_service import decrypt_token

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 60


async def _publish_scheduled_post(schedule: PostSchedule) -> None:
    async with async_session() as db:
        try:
            result = await db.execute(
                select(MetaConnection).where(
                    MetaConnection.account_id == schedule.account_id,
                    MetaConnection.provider == PROVIDER_INSTAGRAM,
                    MetaConnection.status == STATUS_ACTIVE,
                )
            )
            conn = result.scalar_one_or_none()
            if not conn:
                schedule.status = "failed"
                schedule.error_message = "Instagram não conectado"
                await db.flush()
                return

            token = decrypt_token(conn.access_token_encrypted)
            ig_id = conn.ig_business_account_id or conn.meta_user_id
            if not ig_id:
                schedule.status = "failed"
                schedule.error_message = "IG Business ID não encontrado"
                await db.flush()
                return

            caption = schedule.caption or ""
            if schedule.hashtags:
                caption += f"\n\n{schedule.hashtags}"

            if schedule.media_type == "VIDEO":
                result = await publish_video_post(token, ig_id, schedule.media_url, caption)
            else:
                result = await publish_image_post(token, ig_id, schedule.media_url, caption)

            schedule.status = "published"
            schedule.published_at = datetime.now(timezone.utc)
            schedule.media_id_response = result.get("id")
            schedule.error_message = None
            logger.info("Scheduled post %s published for account %s", schedule.id, schedule.account_id)

            # Ativa a automação de comentário deste post (se definida no agendamento)
            if schedule.automation_keyword and schedule.media_id_response:
                from app.services.post_automation import create_post_automation
                await create_post_automation(
                    db, schedule.account_id, schedule.media_id_response,
                    schedule.automation_keyword, schedule.automation_comment_reply,
                    schedule.automation_dm_message, schedule.automation_link_message,
                )

            # Já publicado: apaga a mídia do storage (o registro fica como "check").
            from app.services import storage_service
            await storage_service.delete_by_url(schedule.media_url)

        except TokenExpiredError as e:
            schedule.status = "failed"
            schedule.error_message = f"Token expirado: {e}"
        except Exception as e:
            schedule.retry_count = (schedule.retry_count or 0) + 1
            if schedule.retry_count >= 3:
                schedule.status = "failed"
            schedule.error_message = str(e)
            logger.warning("Failed to publish scheduled post %s (retry %d): %s", schedule.id, schedule.retry_count, e)

        await db.commit()


async def cleanup_orphan_media() -> None:
    """Apaga do bucket arquivos que sobraram (upload sem publicar/agendar).

    Mantém: arquivos ligados a agendamentos pendentes/falhos (ainda podem ser
    publicados) e arquivos recentes (< 24h — podem estar prestes a virar post).
    Só roda quando o Supabase Storage está ligado.
    """
    if not settings.storage_enabled:
        return
    from app.services import storage_service

    files = await storage_service.list_objects()
    if not files:
        return

    # Caminhos que NÃO podem ser apagados (agendamentos ainda vivos).
    async with async_session() as db:
        result = await db.execute(
            select(PostSchedule.media_url).where(
                PostSchedule.status.in_(["scheduled", "failed"])
            )
        )
        referenced: set[str] = set()
        for (url,) in result.all():
            path = storage_service.path_from_url(url or "")
            if path:
                referenced.add(path)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    removed = 0
    for obj in files:
        name = obj["name"]
        if name in referenced:
            continue
        try:
            created = datetime.fromisoformat(obj["created_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError, KeyError):
            continue
        if created < cutoff:
            await storage_service.delete(name)
            removed += 1
    if removed:
        logger.info("Limpeza de órfãos: %d arquivo(s) removido(s) do bucket", removed)


async def scheduler_loop():
    logger.info("Scheduler started (polling every %ds)", _POLL_INTERVAL)
    _cleanup_every = 24 * 60 * 60  # 1x por dia
    last_cleanup = 0.0
    while True:
        try:
            now = datetime.now(timezone.utc)
            async with async_session() as db:
                result = await db.execute(
                    select(PostSchedule).where(
                        and_(
                            PostSchedule.status == "scheduled",
                            PostSchedule.scheduled_for <= now,
                        )
                    )
                )
                due_posts = result.scalars().all()

            for post in due_posts:
                await _publish_scheduled_post(post)

            # Limpeza de órfãos no boot e depois 1x por dia.
            loop_now = asyncio.get_event_loop().time()
            if loop_now - last_cleanup >= _cleanup_every:
                try:
                    await cleanup_orphan_media()
                except Exception as e:
                    logger.error("Orphan cleanup error: %s", e)
                last_cleanup = loop_now

        except Exception as e:
            logger.error("Scheduler error: %s", e)

        await asyncio.sleep(_POLL_INTERVAL)
