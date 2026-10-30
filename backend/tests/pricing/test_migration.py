import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text, inspect
from backend.tests.qr.conftest import owned_database_factory


def migration(connection):
    path = Path(__file__).resolve().parents[3] / 'alembic/versions/20261029_simple_costing.py'
    spec = importlib.util.spec_from_file_location('simple_costing_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(connection)):
        module.upgrade()


def test_additive_migration_preserves_existing_rows_and_is_repeatable():
    generator = owned_database_factory()
    factory = next(generator)
    try:
        with factory() as engine:
            with engine.begin() as c:
                for name in ['customers','users','parts','part_customer_aliases','tooling','part_tooling_specs']:
                    c.execute(text(f'CREATE TABLE {name} (id integer PRIMARY KEY)'))
                    c.execute(text(f'INSERT INTO {name} VALUES (1)'))
                migration(c)
                migration(c)
                assert c.scalar(text('SELECT count(*) FROM parts')) == 1
                assert c.scalar(text('SELECT surface_treatment FROM parts WHERE id=1')) is None
                assert set(['costing_tasks','costing_items','costing_revisions']).issubset(inspect(c).get_table_names())
    finally:
        generator.close()
