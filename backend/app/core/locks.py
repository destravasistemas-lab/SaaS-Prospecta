"""
Trava global no Postgres para tarefas de fundo (agendador, follow-up, sync).

Com várias instâncias da API ou um worker separado, cada tarefa periódica roda
em uma só instância por vez: quem não consegue a trava pula a rodada. No
SQLite (testes) não há concorrência entre processos, então a trava é livre.
"""
import zlib
from contextlib import asynccontextmanager

from sqlalchemy import text

from app.core.database import _is_sqlite, engine


@asynccontextmanager
async def singleton(name: str):
    """Entrega True se esta instância deve rodar a tarefa agora."""
    if _is_sqlite:
        yield True
        return
    key = zlib.crc32(name.encode())
    async with engine.connect() as conn:
        got = bool(await conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}))
        try:
            yield got
        finally:
            if got:
                await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
