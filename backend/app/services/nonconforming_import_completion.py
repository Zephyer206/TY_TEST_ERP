"""Import-only status and date reconciliation; never manufactures inspection evidence."""
import re
from datetime import date, timedelta
from app.services.nonconforming_workflow import fail, history, now, require_action, snapshot


def source_date(row, field):
    value = (row.get('importInfo') or {}).get(field, '')
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.strip()):
        return ''
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return ''


def source_completion_date(row):
    return source_date(row, 'originalActual')


def source_planned_date(row):
    return source_date(row, 'originalPlanned')


def apply_source_schedule(row, actor):
    planned = source_planned_date(row)
    # Never replay the migration over a subsequently returned or edited plan.
    if not planned or row.get('importedProgress') or row.get('plannedDate'):
        return False
    require_action(actor, 'inspect')
    closed = row['status'] == 'closed'
    if not closed and (row['status'] != 'pending_confirmation' or row.get('paused') or row.get('submission')
            or row.get('acceptedQty') or row.get('scrappedQty') or row.get('otherQty')
            or row['importInfo'].get('reviewed') or any(step.get('completedAt') for step in row.get('planSteps', []))):
        fail('已有新系统计划或执行记录，不能用历史计划覆盖', 409)
    previous = snapshot(row)
    target = date.fromisoformat(planned)
    row.update(plannedDate=planned, week=(target - timedelta(days=target.weekday())).isoformat())
    if not closed:
        row.update(status='processing', importedProgress={'basis': 'source_planned_date', 'originalPlanned': planned, 'recordedAt': now()})
    history(row, actor, '登记计划与在办进度' if not closed else '登记计划完成时间',
            f'按用户要求沿用预计完成日期 {planned}；' + ('已完成记录保持关闭。' if closed else '未完成记录标记为处理中，处理方案及验收要求仍按实际情况完善。'), previous)
    return True


def complete_from_source_date(row, actor):
    completed = source_completion_date(row)
    if not completed or row['status'] == 'closed':
        return False
    require_action(actor, 'inspect')
    if (row['status'] != 'pending_confirmation' or row.get('paused') or row.get('submission')
            or row.get('acceptedQty') or row.get('scrappedQty') or row.get('otherQty')
            or row['importInfo'].get('reviewed') or any(step.get('completedAt') for step in row.get('planSteps', []))):
        fail('已有新系统处理记录，不能用历史完成日期覆盖', 409)
    previous = snapshot(row)
    row.update(status='closed', actualDate=completed,
               historicalCompletion={'basis': 'source_actual_date', 'originalActual': completed, 'recordedAt': now()})
    history(row, actor, '按原表完成日期结案',
            f'按用户要求，依据原表实际完成日期 {completed} 标记历史处理已完成；保留原始数量、方案及来源，不补造合格、报废分项或品质验收实测。', previous)
    return True
