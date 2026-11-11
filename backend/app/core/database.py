from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
_engine_kwargs: dict = {"echo": settings.debug}
if not _is_sqlite:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True})

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def session_factory_for(app):
    """Sessão para tarefas fora da requisição, respeitando o override de get_db (testes)."""
    override = app.dependency_overrides.get(get_db)
    if override is None:
        return async_session

    @asynccontextmanager
    async def from_override():
        gen = override()
        try:
            yield await gen.__anext__()
        finally:
            await gen.aclose()

    return from_override


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
