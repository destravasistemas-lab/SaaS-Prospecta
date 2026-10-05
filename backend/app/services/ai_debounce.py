"""
Debounce de 3s da IA: aguarda a ÚLTIMA mensagem do cliente antes de acionar
a Gemini. Nova mensagem dentro da janela reseta o timer; as mensagens
pendentes são concatenadas num único job.

Implementação: timer asyncio por conversa (reset local) + coordenação via
Redis para múltiplos workers — o worker cujo timer dispara só processa se:
  1. nenhuma mensagem mais nova chegou dentro da janela (chave ai:lastmsg);
  2. conseguir o lock do lote (SET NX) — evita resposta duplicada.
Graceful shutdown: `shutdown()` cancela os timers pendentes.
"""
import asyncio
import logging
import time
from typing import Awaitable, Callable

from app.core.config import settings
from app.core.redis import get_store

logger = logging.getLogger(__name__)

# timers locais por conversation_id
_timers: dict[str, asyncio.Task] = {}


async def note_message(conversation_id: str) -> float:
    """Registra o timestamp da última mensagem da conversa (janela do debounce)."""
    store = await get_store()
    now = time.time()
    await store.set_ttl(f"ai:lastmsg:{conversation_id}", str(now), ttl=600)
    return now


def schedule(
    conversation_id: str,
    callback: Callable[[], Awaitable[None]],
    delay: float | None = None,
) -> None:
    """
    (Re)agenda o processamento da conversa. Se já existe timer local, cancela
    e recomeça — é o reset do debounce.
    """
    delay = settings.ai_debounce_seconds if delay is None else delay

    old = _timers.get(conversation_id)
    if old and not old.done():
        old.cancel()

    async def _run():
        try:
            await asyncio.sleep(delay)
            if not await should_fire(conversation_id, delay):
                return
            await callback()
        except asyncio.CancelledError:
            pass  # reset do debounce — outro timer assumiu
        except Exception as exc:
            logger.exception("Debounce IA: erro no job da conversa %s: %s", conversation_id, exc)
        finally:
            if _timers.get(conversation_id) is asyncio.current_task():
                _timers.pop(conversation_id, None)

    _timers[conversation_id] = asyncio.ensure_future(_run())


async def should_fire(conversation_id: str, delay: float) -> bool:
    """
    Decide se ESTE timer processa o lote:
    - se chegou mensagem mais nova dentro da janela → skip (timer dela cobre);
    - lock por lote (lastmsg_ts) → só um worker responde.
    """
    store = await get_store()
    raw = await store.get(f"ai:lastmsg:{conversation_id}")
    last_ts = float(raw) if raw else 0.0
    if last_ts and (time.time() - last_ts) < (delay - 0.2):
        return False
    lock_key = f"ai:proc:{conversation_id}:{last_ts:.3f}"
    return await store.set_nx_ttl(lock_key, "1", ttl=120)


async def shutdown() -> None:
    """Cancela timers pendentes (graceful shutdown do worker)."""
    for task in list(_timers.values()):
        if not task.done():
            task.cancel()
    _timers.clear()
