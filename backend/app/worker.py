"""
Processo de tarefas de fundo, separado da API: `python -m app.worker`.

Roda o agendador (posts, follow-ups, reprocessamento de webhooks), a fila de
disparos e o sync de anúncios. Para usar, defina BACKGROUND_JOBS_ENABLED=false
nas instâncias da API e suba este processo como worker. Cada tarefa tem trava
no banco, então mais de um worker também é seguro.
"""
import asyncio
import logging

from app.core.config import settings
from app.core.database import engine
from app.main import app  # noqa: F401  (registra os modelos)

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    from app.core import http
    from app.services.broadcast_worker import broadcast_loop
    from app.services.scheduler import scheduler_loop

    loops = [scheduler_loop(), broadcast_loop()]
    if settings.ads_sync_enabled:
        from app.services.ads_sync import ads_sync_loop
        loops.append(ads_sync_loop())
    try:
        await asyncio.gather(*loops)
    finally:
        await http.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
