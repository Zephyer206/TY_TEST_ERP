from logging.config import fileConfig
from pathlib import Path
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import sys

config = context.config

# Resolve backend directory (where alembic.ini lives)
backend_dir = Path(__file__).resolve().parent  # alembic/ directory
project_root = backend_dir.parent  # project root (/) or backend/ parent
# If backend/ subdirectory exists, use it as the Python package root
if (project_root / "backend" / "src").is_dir():
    sys.path.insert(0, str(project_root / "backend"))
elif (project_root / "src").is_dir():
    sys.path.insert(0, str(project_root))
else:
    # Fallback: add both potential roots
    sys.path.insert(0, str(project_root / "backend"))
    sys.path.insert(0, str(project_root))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from src.models import *  # noqa: F401, F403
from src.database import Base

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
    import asyncio
    asyncio.run(run_migrations_online())
