import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, update

from app.core.database import async_session
from app.core.config import settings
from app.core.locks import singleton
from app.models.schedule import PostSchedule
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.services.instagram_service import publish_image_post, publish_video_post, TokenExpiredError
from app.services.meta_token_service import decrypt_token

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 60
# Post em "publicando" por mais que isso: a instância caiu no meio da publicação.
_STUCK_AFTER = timedelta(minutes=15)


async def _publish_scheduled_post(schedule_id: str, session_factory=async_session) -> None:
    async with session_factory() as db:
        # Reserva o post: com várias instâncias, só uma publica.
        claimed = await db.execute(
            update(PostSchedule)
            .where(PostSchedule.id == schedule_id, PostSchedule.status == "scheduled")
            .values(status="publishing", updated_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            return
        await db.commit()

        # Lido nesta sessão: antes o objeto vinha de outra sessão e o status
        # "published" nunca era gravado, então o post era publicado de novo a cada minuto.
        schedule = (await db.execute(
            select(PostSchedule).where(PostSchedule.id == schedule_id).execution_options(populate_existing=True)
        )).scalar_one()
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
                await db.commit()
                return

            token = decrypt_token(conn.access_token_encrypted)
            ig_id = conn.ig_business_account_id or conn.meta_user_id
            if not ig_id:
                schedule.status = "failed"
                schedule.error_message = "IG Business ID não encontrado"
                await db.commit()
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
            # Grava já: o que vem depois é acessório e não pode fazer o post sair de novo.
            await db.commit()
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
            if schedule.status != "published":
                schedule.retry_count = (schedule.retry_count or 0) + 1
                schedule.status = "failed" if schedule.retry_count >= 3 else "scheduled"
                schedule.error_message = str(e)
            logger.warning("Failed to publish scheduled post %s (retry %d): %s", schedule.id, schedule.retry_count, e)

        await db.commit()


async def publish_due_posts(session_factory=async_session) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as db:
        await db.execute(
            update(PostSchedule)
            .where(PostSchedule.status == "publishing", PostSchedule.updated_at < now - _STUCK_AFTER)
            .values(status="failed", error_message="Publicação interrompida. Confira no Instagram antes de reagendar.")
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        due = (await db.execute(
            select(PostSchedule.id).where(
                and_(PostSchedule.status == "scheduled", PostSchedule.scheduled_for <= now)
            )
        )).scalars().all()
    for schedule_id in due:
        await _publish_scheduled_post(schedule_id, session_factory)


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


async def _guarded(name: str, job) -> None:
    """Roda a tarefa só se esta instância pegar a trava; erros não derrubam o loop."""
    try:
        async with singleton(name) as mine:
            if mine:
                await job()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error("Tarefa %s falhou: %s", name, e)


async def scheduler_loop():
    from app.services import webhook_queue

    logger.info("Scheduler started (polling every %ds)", _POLL_INTERVAL)
    _cleanup_every = 24 * 60 * 60  # 1x por dia
    _followup_every = 10 * 60      # follow-up automático a cada 10 min
    last_cleanup = 0.0
    last_followup = 0.0
    loop = asyncio.get_event_loop()
    while True:
        await _guarded("scheduler:posts", publish_due_posts)
        await _guarded("scheduler:webhooks", webhook_queue.retry_pending)

        loop_now = loop.time()
        if loop_now - last_cleanup >= _cleanup_every:
            await _guarded("scheduler:cleanup", cleanup_orphan_media)
            await _guarded("scheduler:webhook-purge", webhook_queue.purge_old)
            last_cleanup = loop_now

        if loop_now - last_followup >= _followup_every:
            await _guarded("scheduler:followups", _run_followups)
            last_followup = loop_now

        await asyncio.sleep(_POLL_INTERVAL)
