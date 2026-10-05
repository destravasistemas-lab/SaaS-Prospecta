"""
Alembic environment — async (asyncpg) + metadata do SQLAlchemy 2.0.

A URL do banco vem de app.core.config.settings (env var DATABASE_URL),
com override opcional via `alembic -x db_url=postgresql+asyncpg://...`.

Todos os módulos de models são importados explicitamente para que
Base.metadata contenha TODAS as tabelas no autogenerate.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.core.database import Base

# --- Importa TODOS os models para popular Base.metadata --------------------
import app.models.account            # noqa: F401
import app.models.automation         # noqa: F401
import app.models.client_assignment  # noqa: F401
import app.models.conversation       # noqa: F401
import app.models.lead               # noqa: F401
import app.models.message            # noqa: F401
import app.models.meta_connection    # noqa: F401
import app.models.schedule           # noqa: F401
import app.models.subscription       # noqa: F401
import app.models.user               # noqa: F401
import app.models.video              # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL: override via -x db_url=... ou settings.database_url (DATABASE_URL)
_x = context.get_x_argument(as_dictionary=True)
db_url = _x.get("db_url") or settings.database_url
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera SQL sem conectar ao banco (alembic upgrade --sql)."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Conecta com engine async (asyncpg) e roda as migrations."""
    connectable = async_engine_from_config(
        {"sqlalchemy.url": db_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
