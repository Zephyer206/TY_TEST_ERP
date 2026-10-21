import copy
import json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services.nonconforming_workflow import (apply_action, draft_data, empty_draft, has_rework_history, new_record, remaining, today)
from app.services.nonconforming_service import get_record

quality = SimpleNamespace(id=1, username='quality', real_name='品质', dept='quality', role_level=2)
sales = SimpleNamespace(id=2, username='sales', real_name='业务', dept='sales', role_level=2)
development = SimpleNamespace(id=3, username='development', real_name='开发', dept='engineering', role_level=2)
production = SimpleNamespace(id=4, username='production', real_name='生产', dept='prod', role_level=1)

def step(kind='rework', identity='step-1'):
    return dict(id=identity, kind=kind, requirement='按图纸处理', completedAt='', completedBy='', result='')

def draft(kind='rework'):
    return empty_draft() | dict(customer='测试客户', partNo='TEST-NC', partName='弹簧片', source='厂内检验', quantity=12000,
        description='力值异常', disposition=kind, treatment='按图纸处理', assignee='生产', plannedDate='2026-10-19', week='2026-10-19',
        planSteps=[step(kind)], inspectionItems=[dict(id='check-1', name='力值', standard='12–16.5N')])

def record(kind='rework'):
    return new_record(draft(kind), quality, 'tianyue', 1)

def act(row, action, payload=None, actor=quality):
    return apply_action(row, action, payload or {}, actor)

def evidence(row):
    return dict(checks=[dict(id=item['id'], actual='实测符合标准', passed=True) for item in row['inspectionItems']], quantityChecked=True, releaseChecked=True)

def finish(row):
    for item in row['planSteps']:
        row = act(row, 'finish_step', dict(stepId=item['id'], note='本步执行完成'), production)
    return row

def processing(kind='sorting'):
    row = act(record(kind), 'confirm')
    if kind == 'rework':
        row = act(row, 'prepare', dict(ready=True), development)
    return act(row, 'start', actor=production)

def test_complete_partial_return_scrap_closure_retains_counts_and_history():
    row = finish(processing())
    row = act(row, 'submit', dict(result=dict(good=10000, scrap=0, note='挑选合格一万件')), production)
    assert row['acceptedQty'] == 0
    row = act(row, 'inspect', dict(passed=True, note='复核通过', evidence=evidence(row)))
    assert remaining(row) == 2000 and row['actualDate'] == '' and row['status'] == 'processing'
    row = act(row, 'return', dict(reason='剩余两千件改报废'), sales)
    changed = draft('scrap'); changed['treatment'] = '仅剩余两千件报废'
    row = act(row, 'edit', dict(draft=changed)); row = act(row, 'confirm'); row = act(row, 'start', actor=production)
    row = finish(row); row = act(row, 'submit', dict(result=dict(good=0, scrap=2000, note='已执行报废')), production)
    row = act(row, 'inspect', dict(passed=True, note='报废凭据通过', evidence=evidence(row)))
    assert row['status'] == 'closed' and row['quantity'] == 12000
    assert row['acceptedQty'] == 10000 and row['scrappedQty'] == 2000 and row['actualDate'] == today()
    assert any(entry['action'] == '部分验收通过' and json.loads(entry['snapshot'])['submission']['good'] == 10000 for entry in row['history'])
    with pytest.raises(HTTPException, match='') as closed:
        act(row, 'return', dict(reason='不能重开'), development)
    assert closed.value.status_code == 400

@pytest.mark.parametrize('actor', [quality, development, sales])
@pytest.mark.parametrize('status', ['pending', 'processing', 'inspection'])
def test_return_requires_reason_and_preserves_accepted_and_mold(actor, status):
    row = record(); row.update(status=status, acceptedQty=10000, moldReady=True, submission=dict(good=2000, scrap=0, note='已提交'))
    with pytest.raises(HTTPException):
        act(row, 'return', dict(reason=' '), actor)
    returned = act(row, 'return', dict(reason='重新讨论'), actor)
    assert returned['acceptedQty'] == 10000 and returned['moldReady'] is True and returned['submission'] is None and returned['paused'] is True
    assert json.loads(returned['history'][0]['snapshot'])['status'] == status

def test_combination_runs_in_order_and_only_rework_waits_for_mold():
    row = record(); row['planSteps'] = [step('sorting', '1'), step('rework', '2'), step('postprocess', '3')]
    row = act(row, 'confirm'); row = act(row, 'start', actor=production)
    with pytest.raises(HTTPException):
        act(row, 'finish_step', dict(stepId='2', note='跳步'), production)
    row = act(row, 'finish_step', dict(stepId='1', note='挑选完成'), production)
    with pytest.raises(HTTPException):
        act(row, 'finish_step', dict(stepId='2', note='无模具'), production)
    row = act(row, 'prepare', dict(ready=True), development)
    row = act(row, 'finish_step', dict(stepId='2', note='返工完成'), production)
    with pytest.raises(HTTPException):
        act(row, 'prepare', dict(ready=False), development)
    row = act(row, 'finish_step', dict(stepId='3', note='标识完成'), production)
    assert row['acceptedQty'] == 0 and row['quantity'] == 12000

def test_edit_cannot_inject_status_counts_or_history_and_confirmed_data_is_locked():
    row = record(); before = copy.deepcopy(row)
    forged = draft() | dict(status='closed', acceptedQty=12000, history=[])
    with pytest.raises(HTTPException):
        act(row, 'edit', dict(draft=forged))
    assert row == before
    row = act(row, 'confirm')
    with pytest.raises(HTTPException):
        act(row, 'edit', dict(draft=draft()))

@pytest.mark.parametrize('action, actor', [('create', sales), ('confirm', production), ('inspect', sales), ('prepare', quality), ('return', production)])
def test_server_role_boundaries(action, actor):
    with pytest.raises(HTTPException) as denied:
        if action == 'create':
            new_record(draft(), actor, 'tianyue', 1)
        else:
            act(record(), action, {}, actor)
    assert denied.value.status_code == 403

def test_inspection_requires_all_checks_quantity_and_release_and_preserves_evidence():
    row = processing(); row['release'].update(labeling='返工标签', destination='安吉')
    row['inspectionItems'].append(dict(id='check-2', name='开口', standard='7.7±0.2'))
    row = finish(row); row = act(row, 'submit', dict(result=dict(good=12000, scrap=0, note='本批完成')), production)
    valid = evidence(row)
    bad_cases = [valid | dict(quantityChecked=False), valid | dict(checks=valid['checks'][:1]), valid | dict(releaseChecked=False), valid | dict(checks=[valid['checks'][0], valid['checks'][0]])]
    for invalid in bad_cases:
        with pytest.raises(HTTPException):
            act(row, 'inspect', dict(passed=True, note='不能通过', evidence=invalid))
        assert row['acceptedQty'] == 0 and row['status'] == 'inspection'
    row = act(row, 'inspect', dict(passed=True, note='全部通过', evidence=valid))
    saved = json.loads(row['history'][0]['snapshot'])
    assert saved['inspection']['quantityChecked'] and len(saved['inspection']['checks']) == 2
    assert saved['release']['destination'] == '安吉' and saved['submission']['good'] == 12000

def test_failed_and_partial_inspection_never_double_count_and_restart_steps():
    row = finish(processing()); row = act(row, 'submit', dict(result=dict(good=10000, scrap=0, note='第一批')), production)
    row = act(row, 'inspect', dict(passed=True, note='一万件通过', evidence=evidence(row)))
    assert not row['planSteps'][0]['completedAt'] and row['acceptedQty'] == 10000
    row = finish(row); row = act(row, 'submit', dict(result=dict(good=2000, scrap=0, note='剩余两千')), production)
    row = act(row, 'inspect', dict(passed=False, note='复测不通过', evidence={}))
    assert row['acceptedQty'] == 10000 and remaining(row) == 2000 and row['submission'] is None
    assert not row['planSteps'][0]['completedAt']

@pytest.mark.parametrize('result', [dict(good=12001, scrap=0), dict(good=-1, scrap=1), dict(good=1.2, scrap=0), dict(good=True, scrap=0), dict(good=0, scrap=100)])
def test_bad_or_unapproved_quantities_reject_without_mutating_input(result):
    row = finish(processing()); original = copy.deepcopy(row)
    with pytest.raises(HTTPException):
        act(row, 'submit', dict(result=result | dict(note='非法数量')), production)
    assert row == original

def test_other_disposition_has_its_own_count_and_rework_history_survives_scrap_change():
    row = finish(processing('other')); row = act(row, 'submit', dict(result=dict(good=0, scrap=0, other=12000, note='按方案退回')), production)
    row = act(row, 'inspect', dict(passed=True, note='核实完成', evidence=evidence(row)))
    assert row['otherQty'] == 12000 and row['acceptedQty'] == 0 and row['status'] == 'closed'
    reworked = processing('rework'); reworked = act(reworked, 'return', dict(reason='剩余报废'), sales)
    reworked = act(reworked, 'edit', dict(draft=draft('scrap')))
    assert has_rework_history(reworked)

def test_forecast_and_quantity_split_and_concession_constraints():
    payload = draft(); payload['trace']['expectedReturnQty'] = 100000
    assert draft_data(payload)['quantity'] == 12000
    payload['quantityLots'] = [dict(id='lot-1', batch='库存', quantity=10000, container='', note='')]
    with pytest.raises(HTTPException):
        draft_data(payload)
    row = record(); row['release']['mode'] = 'concession'
    with pytest.raises(HTTPException):
        act(row, 'confirm')
    payload = draft(); payload['quantityVerified'] = False
    with pytest.raises(HTTPException):
        draft_data(payload)

@pytest.mark.asyncio
async def test_stale_revision_and_missing_company_record_reject():
    entity = SimpleNamespace(revision=3)
    db = SimpleNamespace()
    async def execute(_query):
        return SimpleNamespace(scalar_one_or_none=lambda: entity)
    db.execute = execute
    with pytest.raises(HTTPException) as conflict:
        await get_record(db, 'tianyue', 'one', 2)
    assert conflict.value.status_code == 409
    entity = None
    with pytest.raises(HTTPException) as missing:
        await get_record(db, 'gaibo', 'one', 3)
    assert missing.value.status_code == 404
