"""
Mídia, fila de posts e automações do Instagram: cotas por empresa e limpeza.

Cada upload fica registrado em `media_uploads` e conta na cota até ser apagado,
o que acontece ao publicar, ao remover o agendamento, quando o upload sobra sem
virar post (24h) e quando o post falhou e ficou parado (FAILED_MEDIA_DAYS).
"""
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import t
from app.models.automation import AutomationConfig
from app.models.schedule import MediaUpload, PostSchedule
from app.services import storage_service
from app.services.billing import content_limit

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
MB = 1024 * 1024
# Posts que ainda vão sair (contam na fila)
QUEUED = ("scheduled", "publishing")
# Posts cuja mídia ainda pode ser usada
KEEPS_MEDIA = ("scheduled", "publishing", "failed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def local_prefix() -> str:
    return f"{settings.public_backend_url}/api/v1/instagram/uploads/"


async def used_bytes(db: AsyncSession, account_id: str) -> int:
    return int((await db.execute(
        select(func.coalesce(func.sum(MediaUpload.bytes), 0))
        .where(MediaUpload.account_id == account_id, MediaUpload.released_at.is_(None))
    )).scalar() or 0)


async def queued_posts(db: AsyncSession, account_id: str) -> int:
    return int((await db.execute(
        select(func.count(PostSchedule.id))
        .where(PostSchedule.account_id == account_id, PostSchedule.status.in_(QUEUED))
    )).scalar() or 0)


async def active_automations(db: AsyncSession, account_id: str) -> int:
    """Automações ligadas mais os posts na fila que vão criar uma ao publicar."""
    active = (await db.execute(
        select(func.count(AutomationConfig.id))
        .where(AutomationConfig.account_id == account_id, AutomationConfig.is_active.is_(True))
    )).scalar() or 0
    reserved = (await db.execute(
        select(func.count(PostSchedule.id)).where(
            PostSchedule.account_id == account_id,
            PostSchedule.status.in_(QUEUED),
            PostSchedule.automation_keyword.isnot(None),
        )
    )).scalar() or 0
    return int(active) + int(reserved)


async def check_storage(db: AsyncSession, account_id: str, size: int) -> None:
    limit = await content_limit(db, account_id, "storage_mb")
    if limit is None:
        return
    used = await used_bytes(db, account_id)
    if used + size > limit * MB:
        free = max(0, limit * MB - used) // MB
        raise HTTPException(413, t(
            f"Espaço de mídia cheio: o plano guarda até {limit} MB de posts esperando publicação e restam {free} MB. "
            "Publique ou remova agendamentos para liberar espaço.",
            f"Media space is full: the plan keeps up to {limit} MB of posts waiting to be published and {free} MB are left. "
            "Publish or remove scheduled posts to free up space.",
        ))


async def check_queue(db: AsyncSession, account_id: str) -> None:
    limit = await content_limit(db, account_id, "scheduled_posts")
    if limit is not None and await queued_posts(db, account_id) >= limit:
        raise HTTPException(422, t(
            f"O plano permite até {limit} posts agendados ao mesmo tempo. Espere algum sair ou remova um agendamento.",
            f"The plan allows up to {limit} scheduled posts at a time. Wait for one to go out or remove a scheduled post.",
        ))


async def check_automations(db: AsyncSession, account_id: str, adding: int = 1) -> None:
    limit = await content_limit(db, account_id, "automations")
    if limit is not None and await active_automations(db, account_id) + adding > limit:
        raise HTTPException(422, t(
            f"O plano permite até {limit} automações ativas. Pause ou remova uma automação antes de criar outra.",
            f"The plan allows up to {limit} active automations. Pause or remove an automation before creating another.",
        ))


async def record(db: AsyncSession, account_id: str, url: str, size: int, media_type: str) -> None:
    db.add(MediaUpload(account_id=account_id, url=url, bytes=size, media_type=media_type))
    await db.flush()


async def release(db: AsyncSession, url: str | None) -> None:
    """Apaga o arquivo (bucket ou disco) e tira da cota. Sem erro se já não existir."""
    if not url:
        return
    if url.startswith(local_prefix()):
        name = Path(url[len(local_prefix()):]).name
        try:
            (UPLOAD_DIR / name).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Mídia local não apagada (%s): %s", name, type(exc).__name__)
    elif settings.storage_enabled:
        await storage_service.delete_by_url(url)
    await db.execute(
        update(MediaUpload).where(MediaUpload.url == url, MediaUpload.released_at.is_(None))
        .values(released_at=_now()).execution_options(synchronize_session=False)
    )


async def usage(db: AsyncSession, account_id: str) -> dict:
    return {
        "storage_used_mb": round(await used_bytes(db, account_id) / MB, 1),
        "storage_limit_mb": await content_limit(db, account_id, "storage_mb"),
        "scheduled_posts": await queued_posts(db, account_id),
        "scheduled_posts_limit": await content_limit(db, account_id, "scheduled_posts"),
        "automations": await active_automations(db, account_id),
        "automations_limit": await content_limit(db, account_id, "automations"),
        "post_automation_days": settings.post_automation_days,
        "max_schedule_days": settings.max_schedule_days,
    }


async def cleanup(db: AsyncSession) -> dict:
    """Limpeza periódica: uploads que sobraram, mídia de posts parados e automações vencidas."""
    now = _now()
    keep = set((await db.execute(
        select(PostSchedule.media_url).where(PostSchedule.status.in_(KEEPS_MEDIA))
    )).scalars().all())

    # Upload que não virou post em 24h
    leftovers = (await db.execute(
        select(MediaUpload.url).where(
            MediaUpload.released_at.is_(None), MediaUpload.created_at < now - timedelta(hours=24),
        )
    )).scalars().all()
    leftovers = [u for u in leftovers if u not in keep]
    for url in leftovers:
        await release(db, url)

    # Post que falhou e ficou parado: apaga a mídia e explica
    stale_failed = (await db.execute(
        select(PostSchedule).where(
            PostSchedule.status == "failed",
            PostSchedule.updated_at < now - timedelta(days=settings.failed_media_days),
        )
    )).scalars().all()
    for post in stale_failed:
        await release(db, post.media_url)
        post.status = "expired"
        post.error_message = t(
            f"A mídia foi apagada depois de {settings.failed_media_days} dias com falha. Envie de novo para agendar.",
            f"The media was deleted after {settings.failed_media_days} days failing. Upload it again to schedule.",
        )

    # Automação de post parada há mais do prazo (religar conta um prazo novo)
    expired = 0
    if settings.post_automation_days > 0:
        expired = (await db.execute(
            update(AutomationConfig).where(
                AutomationConfig.media_id.isnot(None),
                AutomationConfig.is_active.is_(True),
                func.coalesce(AutomationConfig.updated_at, AutomationConfig.created_at)
                < now - timedelta(days=settings.post_automation_days),
            ).values(is_active=False).execution_options(synchronize_session=False)
        )).rowcount or 0

    await db.flush()
    result = {"uploads": len(leftovers), "failed_posts": len(stale_failed), "automations": expired}
    if any(result.values()):
        logger.info("Limpeza de posts: %s", result)
    return result
