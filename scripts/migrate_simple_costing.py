"""Apply only the additive costing domain; leave unrelated pending migrations alone."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.database import engine


def apply(connection):
    path = ROOT / 'alembic/versions/20261029_simple_costing.py'
    spec = importlib.util.spec_from_file_location('simple_costing_revision', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = connection.scalar(text('SELECT count(*) FROM parts'))
    version = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    with Operations.context(MigrationContext.configure(connection)):
        module.upgrade()
    assert connection.scalar(text('SELECT count(*) FROM parts')) == before
    assert connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all() == version
    print(f'Costing additive schema installed; {before} part rows preserved; migration baseline unchanged.')


async def main():
    engine.echo = False
    try:
        async with engine.begin() as connection:
            await connection.run_sync(apply)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as error:
        print('Costing schema migration failed:', type(error).__name__)
        sys.exit(1)
