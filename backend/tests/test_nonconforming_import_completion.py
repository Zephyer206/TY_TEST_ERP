import copy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services.nonconforming_import_completion import apply_source_schedule, complete_from_source_date, source_completion_date
from app.services.nonconforming_workflow import apply_action, remaining

quality = SimpleNamespace(id=1, real_name='品质', username='quality', dept='quality', role_level=2)


def imported(actual='2026-10-12'):
    return dict(status='pending_confirmation', quantity=3000, quantityVerified=False, actualDate='',
                acceptedQty=0, scrappedQty=0, otherQty=0, paused=False, moldReady=False, submission=None,
                planSteps=[], history=[], importInfo=dict(originalActual=actual, reviewed=False))


def test_source_date_closure_preserves_unknown_results_and_audit_and_is_idempotent():
    row = imported(); before = copy.deepcopy(row)
    assert complete_from_source_date(row, quality)
    assert row['status'] == 'closed' and row['actualDate'] == '2026-10-12' and remaining(row) == 0
    assert row['quantity'] == 3000 and row['quantityVerified'] is False
    assert row['acceptedQty'] == row['scrappedQty'] == row['otherQty'] == 0
    assert row['importInfo'] == before['importInfo'] and row['planSteps'] == [] and row['moldReady'] is False
    assert row['history'][0]['action'] == '按原表完成日期结案'
    after = copy.deepcopy(row)
    assert not complete_from_source_date(row, quality) and row == after


@pytest.mark.parametrize('actual', ['', '正在返', '5.0尺寸已返好，另外一个尺寸待返工', '9.23前', '2026-02-30', '20261012'])
def test_progress_text_deadlines_and_invalid_dates_do_not_close(actual):
    row = imported(actual); before = copy.deepcopy(row)
    assert source_completion_date(row) == ''
    assert not complete_from_source_date(row, quality) and row == before


@pytest.mark.parametrize('patch', [dict(status='processing'), dict(acceptedQty=1000), dict(paused=True), dict(importInfo=dict(originalActual='2026-10-12', reviewed=True)), dict(planSteps=[dict(completedAt='2026-10-17T00:00:00Z')])])
def test_active_or_reviewed_records_are_not_overwritten(patch):
    row = imported() | patch; before = copy.deepcopy(row)
    with pytest.raises(HTTPException) as error:
        complete_from_source_date(row, quality)
    assert error.value.status_code == 409 and row == before


def test_manual_records_do_not_have_a_source_completion_date():
    row = imported(); del row['importInfo']
    assert not complete_from_source_date(row, quality)


def test_planned_date_becomes_processing_and_preserves_quantities_and_evidence():
    row = imported(''); row['importInfo']['originalPlanned'] = '2026-10-19'
    assert apply_source_schedule(row, quality)
    assert row['status'] == 'processing' and row['plannedDate'] == row['week'] == '2026-10-19'
    assert row['actualDate'] == '' and row['quantityVerified'] is False
    assert row['moldReady'] is False and not row['planSteps']
    after = copy.deepcopy(row)
    assert not apply_source_schedule(row, quality) and row == after
    # A later human return is never revived by rerunning the import adjustment.
    row['status'] = 'pending_confirmation'; row['paused'] = True
    row['plannedDate'] = ''; row['week'] = ''
    assert not apply_source_schedule(row, quality) and row['status'] == 'pending_confirmation'


def test_completion_takes_priority_and_closed_records_receive_only_the_plan_date():
    row = imported(); row['importInfo']['originalPlanned'] = '2026-10-14'
    complete_from_source_date(row, quality)
    assert apply_source_schedule(row, quality)
    assert row['status'] == 'closed' and row['actualDate'] == '2026-10-12'
    assert row['plannedDate'] == '2026-10-14' and row['week'] == '2026-10-12'
    assert 'importedProgress' not in row


@pytest.mark.parametrize('planned', ['', '已完成', '9.24已经开始返工', '返工后入库', '2026-02-30'])
def test_non_dates_do_not_assign_processing(planned):
    row = imported(''); row['importInfo']['originalPlanned'] = planned
    before = copy.deepcopy(row)
    assert not apply_source_schedule(row, quality) and row == before


def test_schedule_does_not_replace_a_human_plan():
    row = imported(''); row['importInfo']['originalPlanned'] = '2026-10-19'
    row['plannedDate'] = '2026-10-26'; row['week'] = '2026-10-26'
    before = copy.deepcopy(row)
    assert not apply_source_schedule(row, quality) and row == before


@pytest.mark.parametrize('action,payload', [('finish_step', {'stepId': 'one', 'note': '完成'}), ('submit', {'result': {'good': 3000, 'note': '完成'}})])
def test_status_migration_does_not_bypass_required_plan_confirmation(action, payload):
    row = imported(''); row['importInfo']['originalPlanned'] = '2026-10-19'
    apply_source_schedule(row, quality)
    with pytest.raises(HTTPException) as error:
        apply_action(row, action, payload, quality)
    assert '完善并确认处理方案' in error.value.detail
