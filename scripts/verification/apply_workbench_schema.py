"""Apply only additive workbench DDL; leave unrelated migrations untouched."""

import asyncio
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


async def main():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from app.database import engine

    try:
        async with engine.begin() as connection:
            before = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
            path = ROOT / "alembic" / "versions" / "20261025_workbench_assignments.py"
            spec = importlib.util.spec_from_file_location("workbench_migration", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            def apply(sync):
                with Operations.context(MigrationContext.configure(sync)):
                    module.upgrade()

            await connection.run_sync(apply)
            counts = {name: (await connection.execute(text("SELECT count(*) FROM " + name))).scalar_one()
                      for name in ("workbench_assignments", "workbench_assignment_events")}
            after = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
            print(json.dumps({"schema": "workbench only", "revision_unchanged": before == after,
                              "alembic_revision": after, "rows": counts}))
    except Exception as exc:
        print(json.dumps({"schema": "workbench", "error_type": type(exc).__name__}))
        raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.argv[1:] != ["--apply"]:
        raise SystemExit("Use --apply to create and verify the two workbench tables.")
    asyncio.run(main())
