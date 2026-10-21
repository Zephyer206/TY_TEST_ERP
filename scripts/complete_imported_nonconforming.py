"""Apply the user's source-actual-date completion rule to this imported workbook only."""
import argparse
import asyncio
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


async def reconcile(bundle, apply=False):
    from sqlalchemy import select
    from app.database import async_session_maker, engine
    from app.models.nonconforming import NonconformingRecord
    from app.models.user import User
    from app.services.nonconforming_import_completion import complete_from_source_date, source_completion_date
    from app.services.nonconforming_service import lock_company, save_record
    engine.echo = False
    expected = {row['id']: source_completion_date(row) for row in bundle['records'] if source_completion_date(row)}
    if len(expected) != 37:
        raise RuntimeError('Source dated-row count changed; nothing updated')
    try:
        async with async_session_maker() as db:
            async with db.begin():
                for company in ['gaibo', 'tianyue']:
                    await lock_company(db, company)
                models = list((await db.execute(select(NonconformingRecord).where(
                    NonconformingRecord.payload['importInfo']['batchId'].astext == bundle['batchId']).with_for_update())).scalars())
                if {model.id for model in models} != {row['id'] for row in bundle['records']}:
                    raise RuntimeError('Database and workbook IDs differ; nothing updated')
                actor = (await db.execute(select(User).where(User.role_level == 4).order_by(User.id))).scalars().first()
                if not actor:
                    raise RuntimeError('No administrator configured')
                before = {model.id: (copy.deepcopy(model.payload), model.revision) for model in models}
                changes = []
                for model in models:
                    if model.id not in expected:
                        continue
                    if source_completion_date(model.payload) != expected[model.id]:
                        raise RuntimeError('Stored source date differs; nothing updated')
                    payload = copy.deepcopy(model.payload)
                    if complete_from_source_date(payload, actor):
                        changes.append({'id': model.id, 'no': payload['no'], 'partNo': payload['partNo'], 'actualDate': payload['actualDate']})
                        if apply:
                            save_record(model, payload)
                report = {'sourceRecords': len(models), 'datedRecords': len(expected), 'toUpdate': len(changes), 'applied': apply, 'records': changes}
            if apply:
                # Re-read in an independent transaction after commit, including untouched records.
                async with db.begin():
                    stored = list((await db.execute(select(NonconformingRecord).where(NonconformingRecord.id.in_(before)).execution_options(populate_existing=True))).scalars())
                    changed_ids = {row['id'] for row in changes}
                    for model in stored:
                        old, revision = before[model.id]
                        if model.id in changed_ids:
                            payload = model.payload
                            if model.status != 'closed' or payload['actualDate'] != expected[model.id] or model.revision != revision + 1:
                                raise RuntimeError('Committed completion did not reconcile')
                            retained = set(old) - {'status', 'actualDate', 'history'}
                            if any(old[key] != payload[key] for key in retained):
                                raise RuntimeError('An unrelated payload field changed')
                            if payload['history'][1:] != old['history']:
                                raise RuntimeError('Prior history was not preserved')
                        elif model.payload != old or model.revision != revision:
                            raise RuntimeError('An unrelated record changed')
                    report['committedClosed'] = sum(row.status == 'closed' for row in stored)
                    report['committedPending'] = sum(row.status == 'pending_confirmation' for row in stored)
                    report['quantityNeedsReview'] = sum(not row.quantity_verified for row in stored)
                    report['verifiedKnownQuantity'] = sum(row.quantity for row in stored if row.quantity_verified)
                    if any(row.status != 'closed' for row in stored if row.id in expected):
                        raise RuntimeError('Committed status counts did not reconcile')
            return report
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    arguments = parser.parse_args()
    bundle = json.loads((ROOT / 'frontend/src/data/nonconforming-workbook.json').read_text(encoding='utf-8'))
    report = asyncio.run(reconcile(bundle))
    if arguments.apply:
        from import_nonconforming_workbook import backup_database
        backup = backup_database()
        report = asyncio.run(reconcile(bundle, apply=True))
        report['backup'] = backup
        repeated = asyncio.run(reconcile(bundle))
        if repeated['toUpdate'] != 0:
            raise RuntimeError('Historical completion update is not idempotent')
        report['repeatToUpdate'] = 0
        target = ROOT / 'runtime/acceptance/nonconforming-completion/database-report.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ['records', 'backup']}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'success': False, 'error_type': type(error).__name__, 'message': str(error) if isinstance(error, RuntimeError) else 'Operation failed; database details hidden'}))
        sys.exit(1)
