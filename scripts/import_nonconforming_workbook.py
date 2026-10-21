"""Backup, apply only the additive NC migration, and import the authorized workbook once."""
import argparse
import asyncio
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

async def database_state():
    from sqlalchemy import text
    from app.database import engine
    engine.echo = False
    try:
        async with engine.connect() as connection:
            versions = list((await connection.execute(text('SELECT version_num FROM alembic_version'))).scalars())
            return versions
    finally:
        await engine.dispose()

def backup_database():
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    destination = Path(os.environ['USERPROFILE']) / '.codex' / 'backups' / 'ZephyrERP'
    destination.mkdir(parents=True, exist_ok=True)
    backup = destination / f"before-nonconforming-{datetime.now():%Y%m%d-%H%M%S}.dump"
    url = make_url(settings.DATABASE_URL)
    environment = os.environ.copy()
    environment.update(PGHOST=url.host, PGPORT=str(url.port or 5432), PGUSER=url.username, PGPASSWORD=url.password or '', PGDATABASE=url.database)
    if url.query.get('sslmode'):
        environment['PGSSLMODE'] = url.query['sslmode']
    process = subprocess.run(['C:/Program Files/PostgreSQL/16/bin/pg_dump.exe', '--format=custom', '--no-owner', '--no-privileges', '--file', str(backup)], env=environment, capture_output=True, timeout=300)
    if process.returncode or not backup.is_file() or backup.stat().st_size == 0:
        raise RuntimeError('Database backup failed; no migration/import was attempted')
    return {'path': str(backup), 'bytes': backup.stat().st_size, 'sha256': hashlib.sha256(backup.read_bytes()).hexdigest()}

async def import_and_verify(bundle):
    from sqlalchemy import select, text
    from app.database import async_session_maker, engine
    from app.models.user import User
    from app.services.nonconforming_service import import_workbook
    engine.echo = False
    try:
        async with async_session_maker() as session:
            async with session.begin():
                actor = (await session.execute(select(User).where(User.role_level == 4).order_by(User.id))).scalars().first()
                if actor is None:
                    raise RuntimeError('No administrator configured')
                result = await import_workbook(session, bundle, actor)
            # A separate transaction proves the inserted data was committed.
            async with session.begin():
                stored = (await session.execute(text("SELECT count(*) AS total, count(*) FILTER (WHERE NOT quantity_verified) AS quantity_review, sum(quantity) FILTER (WHERE quantity_verified) AS known_quantity FROM nonconforming_records WHERE payload->'importInfo'->>'batchId'=:batch"), {'batch': bundle['batchId']})).mappings().one()
                if stored['total'] != 105 or (result['inserted'] == 105 and (stored['quantity_review'] != 6 or stored['known_quantity'] != 747197)):
                    raise RuntimeError('Imported database quantities do not reconcile')
                result['committed'] = dict(stored)
            async with session.begin():
                repeated = await import_workbook(session, bundle, actor)
                if repeated['inserted'] != 0:
                    raise RuntimeError('Import was not idempotent')
                result['repeatInserted'] = 0
            return result
    finally:
        await engine.dispose()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    arguments = parser.parse_args()
    bundle = json.loads((ROOT / 'frontend/src/data/nonconforming-workbook.json').read_text(encoding='utf-8'))
    if len(bundle['records']) != 105 or len({row['id'] for row in bundle['records']}) != 105:
        raise RuntimeError('Unexpected workbook record count')
    current = asyncio.run(database_state())
    report = {'beforeRevision': current, 'expectedRecords': 105, 'sourceHash': bundle['sha256']}
    if not arguments.apply:
        print(json.dumps(report)); return
    if current not in [['20261009_qg_pricing_costs'], ['20261017_nonconforming']]:
        raise RuntimeError('Unexpected database revision; unrelated migrations will not be run')
    report['backup'] = backup_database()
    if current != ['20261017_nonconforming']:
        from alembic.config import Config
        from alembic import command
        command.upgrade(Config(str(ROOT / 'alembic.ini')), '20261017_nonconforming')
    report['import'] = asyncio.run(import_and_verify(bundle))
    report['afterRevision'] = asyncio.run(database_state())
    target = ROOT / 'runtime/acceptance/nonconforming-server/database-import.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'backupCreated': True, 'revision': report['afterRevision'], **report['import']}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Connection parameters and subprocess diagnostics are intentionally never logged.
        print(json.dumps({'success': False, 'error_type': type(error).__name__, 'message': str(error) if isinstance(error, RuntimeError) else 'Database operation failed; connection details hidden'}))
        sys.exit(1)
