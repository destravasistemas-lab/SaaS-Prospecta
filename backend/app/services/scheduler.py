import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update

from app.core.database import async_session
from app.core.config import settings
from app.models.schedule import PostSchedule
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.services.instagram_service import publish_image_post, publish_video_post, TokenExpiredError
from app.services.meta_token_service import decrypt_token

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 60
_MAX_RETRIES = 3
# "publicando" há mais que isso: a instância caiu no meio. Não republica às cegas.
_STUCK_MINUTES = 15
_LATE_HOURS = 6


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def claim_due_posts(session_factory=async_session, limit: int = 50) -> list[str]:
    """Reserva os posts vencidos (scheduled -> publishing). Só quem reservou publica."""
    now = _now()
    async with session_factory() as db:
        # Muito atrasado (servidor fora do ar, ou preso na falha antiga do agendador):
        # pode já ter saído ou não fazer mais sentido. Pede confirmação em vez de publicar.
        await db.execute(
            update(PostSchedule).where(
                PostSchedule.status == "scheduled",
                PostSchedule.scheduled_for < now - timedelta(hours=_LATE_HOURS),
            ).values(
                status="failed", updated_at=now,
                error_message="Passou mais de 6 horas do horário e o post não saiu sozinho. "
                              "Confira no Instagram e use Tentar de novo se ainda quiser publicar.",
            ).execution_options(synchronize_session=False)
        )
        ids = (await db.execute(
            select(PostSchedule.id)
            .where(PostSchedule.status == "scheduled", PostSchedule.scheduled_for <= now)
            .order_by(PostSchedule.scheduled_for).limit(limit)
        )).scalars().all()
        claimed = []
        for sid in ids:
            res = await db.execute(
                update(PostSchedule).where(PostSchedule.id == sid, PostSchedule.status == "scheduled")
                .values(status="publishing", updated_at=now).execution_options(synchronize_session=False)
            )
            if res.rowcount:
                claimed.append(sid)
        await db.commit()
    return claimed


async def recover_stuck_posts(session_factory=async_session) -> int:
    async with session_factory() as db:
        res = await db.execute(
            update(PostSchedule).where(
                PostSchedule.status == "publishing",
                PostSchedule.updated_at < _now() - timedelta(minutes=_STUCK_MINUTES),
            ).values(
                status="failed", updated_at=_now(),
                error_message="A publicação foi interrompida. Confira no Instagram se o post saiu antes de tentar de novo.",
            ).execution_options(synchronize_session=False)
        )
        await db.commit()
        return res.rowcount or 0


async def _publish_scheduled_post(schedule_id: str, session_factory=async_session) -> None:
    async with session_factory() as db:
        schedule = await db.get(PostSchedule, schedule_id)
        if schedule is None or schedule.status != "publishing":
            return
        try:
            conn = (await db.execute(
                select(MetaConnection).where(
                    MetaConnection.account_id == schedule.account_id,
                    MetaConnection.provider == PROVIDER_INSTAGRAM,
                    MetaConnection.status == STATUS_ACTIVE,
                )
            )).scalar_one_or_none()
            ig_id = (conn.ig_business_account_id or conn.meta_user_id) if conn else None
            if not conn or not ig_id:
                schedule.status = "failed"
                schedule.error_message = "Instagram não conectado" if not conn else "IG Business ID não encontrado"
                await db.commit()
                return
            token = decrypt_token(conn.access_token_encrypted)

            caption = schedule.caption or ""
            if schedule.hashtags:
                caption += f"\n\n{schedule.hashtags}"

            if schedule.media_type == "VIDEO":
                result = await publish_video_post(token, ig_id, schedule.media_url, caption)
            else:
                result = await publish_image_post(token, ig_id, schedule.media_url, caption)
        except TokenExpiredError as e:
            schedule.status = "failed"
            schedule.error_message = f"Token expirado: {e}"
            await db.commit()
            return
        except Exception as e:
            schedule.retry_count = (schedule.retry_count or 0) + 1
            schedule.error_message = str(e)[:1000]
            if schedule.retry_count >= _MAX_RETRIES:
                schedule.status = "failed"
            else:
                schedule.status = "scheduled"
                schedule.scheduled_for = _now() + timedelta(minutes=5 * schedule.retry_count)
            logger.warning("Failed to publish scheduled post %s (retry %d): %s", schedule.id, schedule.retry_count, e)
            await db.commit()
            return

        # Saiu no Instagram: grava já, antes de qualquer passo que possa falhar
        schedule.status = "published"
        schedule.published_at = _now()
        schedule.media_id_response = result.get("id")
        schedule.error_message = None
        await db.commit()
        logger.info("Scheduled post %s published for account %s", schedule.id, schedule.account_id)

        try:
            if schedule.automation_keyword and schedule.media_id_response:
                from app.services.post_automation import create_post_automation
                await create_post_automation(
                    db, schedule.account_id, schedule.media_id_response,
                    schedule.automation_keyword, schedule.automation_comment_reply,
                    schedule.automation_dm_message, schedule.automation_link_message,
                )
            from app.services import post_media
            await post_media.release(db, schedule.media_url)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning("Post %s publicado, mas a automação ou a limpeza falhou: %s", schedule_id, e)


async def run_due_posts(session_factory=async_session) -> int:
    await recover_stuck_posts(session_factory)
    claimed = await claim_due_posts(session_factory)
    for sid in claimed:
        await _publish_scheduled_post(sid, session_factory)
    return len(claimed)


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
                PostSchedule.status.in_(["scheduled", "publishing", "failed"])
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


async def _run_followups() -> None:
    from app.services.followup_service import run_due_followups
    async with async_session() as db:
        try:
            await run_due_followups(db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _run_post_cleanup() -> None:
    from app.services import post_media
    async with async_session() as db:
        try:
            await post_media.cleanup(db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def scheduler_loop():
    logger.info("Scheduler started (polling every %ds)", _POLL_INTERVAL)
    _cleanup_every = 24 * 60 * 60  # bucket: 1x por dia
    _post_cleanup_every = 60 * 60  # cotas, posts parados e automações vencidas: 1x por hora
    _followup_every = 10 * 60      # follow-up automático a cada 10 min
    last_cleanup = last_post_cleanup = last_followup = float("-inf")
    while True:
        try:
            await run_due_posts()

            loop_now = asyncio.get_event_loop().time()
            if loop_now - last_post_cleanup >= _post_cleanup_every:
                try:
                    await _run_post_cleanup()
                except Exception as e:
                    logger.error("Post cleanup error: %s", e)
                last_post_cleanup = loop_now

            # Limpeza de órfãos no boot e depois 1x por dia.
            if loop_now - last_cleanup >= _cleanup_every:
                try:
                    await cleanup_orphan_media()
                except Exception as e:
                    logger.error("Orphan cleanup error: %s", e)
                last_cleanup = loop_now

            if loop_now - last_followup >= _followup_every:
                try:
                    await _run_followups()
                except Exception as e:
                    logger.error("Follow-up run error: %s", e)
                last_followup = loop_now

        except Exception as e:
            logger.error("Scheduler error: %s", e)

        await asyncio.sleep(_POLL_INTERVAL)
