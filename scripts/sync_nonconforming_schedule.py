"""Apply the authorized source-plan status rule without overwriting subsequent human edits."""
import argparse
import asyncio
import copy
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


async def reconcile(bundle, apply=False):
    from sqlalchemy import select
    from app.database import async_session_maker, engine
    from app.models.nonconforming import NonconformingRecord
    from app.models.user import User
    from app.services.nonconforming_import_completion import apply_source_schedule, source_planned_date
    from app.services.nonconforming_service import lock_company, save_record
    engine.echo = False
    expected = {row['id']: source_planned_date(row) for row in bundle['records'] if source_planned_date(row)}
    if len(expected) != 40:
        raise RuntimeError('Source plan count changed; nothing updated')
    try:
        async with async_session_maker() as db:
            async with db.begin():
                for company in ['gaibo', 'tianyue']:
                    await lock_company(db, company)
                models = list((await db.execute(select(NonconformingRecord).where(
                    NonconformingRecord.payload['importInfo']['batchId'].astext == bundle['batchId']).with_for_update())).scalars())
                if {row.id for row in models} != {row['id'] for row in bundle['records']}:
                    raise RuntimeError('Database and workbook IDs differ; nothing updated')
                actor = (await db.execute(select(User).where(User.role_level == 4).order_by(User.id))).scalars().first()
                if not actor:
                    raise RuntimeError('No administrator configured')
                before = {row.id: (copy.deepcopy(row.payload), row.revision) for row in models}
                changes = []
                after = {}
                for model in models:
                    if model.id not in expected:
                        continue
                    payload = copy.deepcopy(model.payload)
                    if source_planned_date(payload) != expected[model.id]:
                        raise RuntimeError('Stored source date differs; nothing updated')
                    if apply_source_schedule(payload, actor):
                        changes.append({'id': model.id, 'no': payload['no'], 'partNo': payload['partNo'], 'plannedDate': payload['plannedDate'], 'beforeStatus': model.status, 'afterStatus': payload['status']})
                        after[model.id] = copy.deepcopy(payload)
                        if apply:
                            save_record(model, payload)
                report = {'sourceRecords': len(models), 'datedPlans': len(expected), 'toUpdate': len(changes),
                          'toProcessing': sum(row['beforeStatus'] != 'processing' and row['afterStatus'] == 'processing' for row in changes),
                          'closedPlansToFill': sum(row['afterStatus'] == 'closed' for row in changes), 'applied': apply, 'records': changes}
            if apply:
                async with db.begin():
                    stored = list((await db.execute(select(NonconformingRecord).where(NonconformingRecord.id.in_(before)).execution_options(populate_existing=True))).scalars())
                    for model in stored:
                        old, revision = before[model.id]
                        if model.id in after:
                            if model.payload != after[model.id] or model.revision != revision + 1 or model.status != after[model.id]['status']:
                                raise RuntimeError('Committed update did not reconcile')
                            retained = set(old) - {'status', 'plannedDate', 'week', 'history'}
                            if any(old[key] != model.payload[key] for key in retained) or model.payload['history'][1:] != old['history']:
                                raise RuntimeError('An unrelated field or history changed')
                        elif model.payload != old or model.revision != revision:
                            raise RuntimeError('An unrelated record changed')
                    report['committedStatuses'] = dict(Counter(row.status for row in stored))
                    report['quantityNeedsReview'] = sum(not row.quantity_verified for row in stored)
                    report['verifiedKnownQuantity'] = sum(row.quantity for row in stored if row.quantity_verified)
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
        if asyncio.run(reconcile(bundle))['toUpdate'] != 0:
            raise RuntimeError('Schedule adjustment is not idempotent')
        report['repeatToUpdate'] = 0
        target = ROOT / 'runtime/acceptance/nonconforming-schedule/database-report.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ['records', 'backup']}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'success': False, 'error_type': type(error).__name__, 'message': str(error) if isinstance(error, RuntimeError) else 'Operation failed; database details hidden'}))
        sys.exit(1)
