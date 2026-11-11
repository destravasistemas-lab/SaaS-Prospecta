"""
Webhooks da Meta: a rota grava o evento e responde na hora; o processamento
roda logo depois, fora da requisição, e é repetido se falhar.

A Meta reenvia (e com o tempo desativa) webhooks que demoram a responder. Antes,
cada automação chamava a Meta dentro da própria requisição e uma rajada de
comentários deixava a resposta em dezenas de segundos.
"""
import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select, update

from app.core.config import settings
from app.core.database import async_session
from app.models.queue import EVENT_FAILED, EVENT_PENDING, EVENT_PROCESSING, WebhookEvent
from app.services.meta_token_service import decrypt_token

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
# Quantos eventos processam ao mesmo tempo por instância: o resto espera na fila,
# em vez de disputar as conexões do banco até estourar o pool.
_slots: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(settings.webhook_concurrency)
    return _slots


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _where(exc: Exception) -> str:
    """Tipo e linha do erro, sem a mensagem: ela pode citar dados do cliente."""
    frame = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
    place = f" em {frame.filename.rsplit('app', 1)[-1]}:{frame.lineno}" if frame else ""
    return f"{type(exc).__name__}{place}"[:255]


async def process_event(event_id: str, session_factory=async_session) -> None:
    from app.routes.webhook import process_payload

    async with _semaphore():
        async with session_factory() as db:
            claimed = await db.execute(
                update(WebhookEvent)
                .where(WebhookEvent.id == event_id, WebhookEvent.status.in_((EVENT_PENDING, EVENT_FAILED)))
                .values(status=EVENT_PROCESSING, attempts=WebhookEvent.attempts + 1, updated_at=_now())
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                return  # outra instância já pegou
            await db.commit()

            event = (await db.execute(
                select(WebhookEvent).where(WebhookEvent.id == event_id).execution_options(populate_existing=True)
            )).scalar_one()
            attempts = event.attempts  # depois do rollback o objeto expira
            try:
                payload = json.loads(decrypt_token(event.payload_encrypted))
                await process_payload(payload, db)
                await db.execute(delete(WebhookEvent).where(WebhookEvent.id == event_id))
                await db.commit()
            except Exception as exc:
                await db.rollback()
                logger.warning("Webhook: evento %s falhou (tentativa %d): %s", event_id, attempts, _where(exc))
                await db.execute(
                    update(WebhookEvent).where(WebhookEvent.id == event_id)
                    .values(status=EVENT_FAILED, last_error=_where(exc), updated_at=_now())
                    .execution_options(synchronize_session=False)
                )
                await db.commit()


async def retry_pending(session_factory=async_session, limit: int = 200) -> int:
    """Reprocessa eventos que ficaram para trás: instância reiniciada no meio ou falha temporária."""
    now = _now()
    async with session_factory() as db:
        # Preso em "processando" há muito tempo: a instância caiu no meio.
        await db.execute(
            update(WebhookEvent)
            .where(WebhookEvent.status == EVENT_PROCESSING, WebhookEvent.updated_at < now - timedelta(minutes=5))
            .values(status=EVENT_FAILED, last_error="interrompido", updated_at=now)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        ids = (await db.execute(
            select(WebhookEvent.id).where(or_(
                (WebhookEvent.status == EVENT_PENDING) & (WebhookEvent.created_at < now - timedelta(seconds=60)),
                (WebhookEvent.status == EVENT_FAILED) & (WebhookEvent.attempts < MAX_ATTEMPTS)
                & (WebhookEvent.updated_at < now - timedelta(seconds=60)),
            )).order_by(WebhookEvent.created_at).limit(limit)
        )).scalars().all()
    for event_id in ids:
        await process_event(event_id, session_factory)
    return len(ids)


async def purge_old(session_factory=async_session) -> None:
    """Eventos que esgotaram as tentativas ficam 7 dias para diagnóstico."""
    async with session_factory() as db:
        await db.execute(delete(WebhookEvent).where(WebhookEvent.created_at < _now() - timedelta(days=7)))
        await db.commit()
