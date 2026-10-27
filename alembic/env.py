from logging.config import fileConfig
from pathlib import Path
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import sys

config = context.config

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "backend"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.models import *  # noqa: F401, F403
from app.database import Base
from app.core.config import settings

# 用 .env 里的 DATABASE_URL 覆盖 alembic.ini（支持远程DB）
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Programmatic migration/acceptance callers can supply an already verified
    # isolated connection. Never open the configured application DB in that case.
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        do_run_migrations(supplied_connection)
    else:
        import asyncio
        asyncio.run(run_migrations_online())
