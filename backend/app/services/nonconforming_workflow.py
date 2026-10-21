"""Server-authoritative workflow. Clients can submit commands, never accepted totals/history."""
import copy
import json
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.nonconforming import DefectDraft

LABELS = {'rework': '返工', 'sorting': '挑选', 'scrap': '报废', 'other': '其他', 'postprocess': '后处理'}
SOURCES = ['生产过程', '厂内检验', '库存排查', '出货检验', '客户反馈', '客户退回']
QUALITY = {'quality', 'qc', '品质'}
DEVELOPMENT = {'engineering', 'design', 'development', 'tech', '开发'}
PRODUCTION = {'prod', 'production', '生产'}
SALES = {'sales', '业务'}
ROLES = {'create': QUALITY, 'edit': QUALITY, 'confirm': QUALITY, 'inspect': QUALITY,
         'priority': SALES, 'prepare': DEVELOPMENT, 'mold': DEVELOPMENT,
         'start': PRODUCTION | QUALITY, 'submit': PRODUCTION | QUALITY,
         'finish_step': PRODUCTION | QUALITY, 'return': QUALITY | DEVELOPMENT | SALES}

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def today():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()

def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)

def require_action(actor, action):
    if actor.role_level < 4 and actor.dept not in ROLES[action]:
        fail('当前岗位没有此操作权限', 403)

def actor_info(actor):
    return {'name': actor.real_name or actor.username, 'dept': actor.dept, 'role_level': actor.role_level}

def string(value, label, limit=6000):
    if not isinstance(value, str) or len(value) > limit:
        fail(f'{label}格式不正确或过长')
    return value.strip()

def integer(value, label, minimum=0):
    if type(value) is not int or not minimum <= value <= 1000000000:
        fail(f'{label}须为不超过10亿的整数，且不能小于{minimum}')
    return value

def remaining(row):
    if row['status'] == 'closed' and (row.get('historicalCompletion') or {}).get('basis') == 'source_actual_date':
        return 0
    return row['quantity'] - row['acceptedQty'] - row['scrappedQty'] - row.get('otherQty', 0)

def snapshot(row, **extra):
    return json.dumps({k: v for k, v in row.items() if k != 'history'} | extra, ensure_ascii=False)

def history(row, actor, action, detail, previous=None):
    row.setdefault('history', []).insert(0, {'id': str(uuid4()), 'at': now(), 'actor': actor_info(actor)['name'], 'action': action, 'detail': detail, **({'snapshot': previous} if previous else {})})

def empty_draft():
    return {'customer': '', 'partNo': '', 'partName': '', 'batchNo': '', 'source': '', 'quantity': 1, 'quantityVerified': True,
        'description': '', 'disposition': '', 'treatment': '', 'assignee': '', 'plannedDate': '', 'week': '',
        'trace': {'productState': '', 'marking': '', 'stockForm': '', 'returnBatch': '', 'expectedReturnQty': 0, 'quantityBasis': '', 'isolationLocation': '', 'containerNo': '', 'relatedRecordNo': ''},
        'quantityLots': [], 'planSteps': [], 'inspectionItems': [],
        'release': {'mode': 'standard', 'basis': '', 'approvedBy': '', 'outputPartNo': '', 'destination': '', 'labeling': '', 'packing': '', 'batchRequirement': ''}}

def draft_data(payload, resolved=0):
    try:
        draft = DefectDraft.model_validate(payload).model_dump()
    except ValidationError:
        fail('不良信息字段或数量格式不正确，请核对必填内容', 422)
    for key in ['customer', 'partNo', 'partName', 'description']:
        if not draft[key].strip():
            fail('请填写客户、零件号、零件名称和异常描述')
    if draft['source'] not in SOURCES:
        fail('请选择发现来源')
    if not draft['quantityVerified']:
        fail('请先核实原表实际数量，并勾选数量核对确认')
    if draft['quantity'] < resolved:
        fail('不良数量不能少于已经验收的数量')
    defaults = empty_draft()
    for group in ['trace', 'release']:
        incoming = draft[group]
        draft[group] = {key: incoming.get(key, value) for key, value in defaults[group].items()}
        for key, value in draft[group].items():
            if key != 'expectedReturnQty':
                draft[group][key] = string(value, key)
    integer(draft['trace']['expectedReturnQty'], '预计退货数量')
    if draft['trace']['stockForm'] not in ['', 'single', 'finished']:
        fail('请选择有效产品形态')
    if draft['release']['mode'] not in ['standard', 'concession']:
        fail('请选择有效放行方式')
    for key in ['plannedDate', 'week']:
        if draft[key]:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', draft[key]):
                    raise ValueError()
                date.fromisoformat(draft[key])
            except ValueError:
                fail('计划日期无效')
    if draft['plannedDate']:
        day = date.fromisoformat(draft['plannedDate'])
        week = (day - timedelta(days=day.weekday())).isoformat()
        if draft['week'] and draft['week'] != week:
            fail('计划完成日期须在所选任务周内')
        draft['week'] = week
    elif draft['week'] and date.fromisoformat(draft['week']).weekday() != 0:
        fail('任务周必须从周一开始')
    for key in ['quantityLots', 'planSteps', 'inspectionItems']:
        identifiers = [string(item.get('id'), '明细标识', 150) for item in draft[key]]
        if len(set(identifiers)) != len(identifiers) or any(not x for x in identifiers):
            fail('明细标识重复或缺失')
    lots = []
    for item in draft['quantityLots']:
        lot = {key: string(item.get(key, ''), key) for key in ['id', 'batch', 'container', 'note']}
        lot['quantity'] = integer(item.get('quantity'), '分项数量', 1)
        if not lot['batch']:
            fail('数量分项须填写批次或来源')
        lots.append(lot)
    draft['quantityLots'] = lots
    if lots and sum(item['quantity'] for item in lots) != draft['quantity']:
        fail('数量分项合计必须等于本条实际不良数量；预计退货不得加入分项')
    steps = []
    for item in draft['planSteps']:
        if item.get('kind') not in LABELS:
            fail('处理步骤类型无效')
        steps.append({'id': item['id'], 'kind': item['kind'], 'requirement': string(item.get('requirement', ''), '本步要求'), 'completedAt': '', 'completedBy': '', 'result': ''})
    draft['planSteps'] = steps
    draft['inspectionItems'] = [{'id': item['id'], 'name': string(item.get('name', ''), '验收项目'), 'standard': string(item.get('standard', ''), '验收标准')} for item in draft['inspectionItems']]
    return draft

def new_record(draft, actor, company, priority):
    require_action(actor, 'create')
    identity = str(uuid4())
    row = draft_data(draft) | {'id': identity, 'no': f"NC-{today().replace('-', '')}-{identity[:8].upper()}", 'company': company,
        'priority': priority, 'status': 'pending_confirmation', 'moldReady': False, 'paused': False,
        'acceptedQty': 0, 'scrappedQty': 0, 'otherQty': 0, 'submission': None, 'actualDate': '', 'createdAt': now(), 'history': []}
    history(row, actor, '品质新增', f"不良 {row['quantity']} 件，进入待确认")
    return row

def has_rework(row):
    return any(step['kind'] == 'rework' for step in row.get('planSteps', [])) or (not row.get('planSteps') and row.get('disposition') == 'rework')

def has_rework_history(row):
    if has_rework(row):
        return True
    for entry in row.get('history', []):
        try:
            if entry.get('snapshot') and has_rework(json.loads(entry['snapshot'])):
                return True
        except (ValueError, KeyError, TypeError):
            continue
    return False

def active_step(row):
    return next((step for step in row['planSteps'] if not step['completedAt']), None)

def reset_steps(row):
    for step in row['planSteps']:
        step.update(completedAt='', completedBy='', result='')

def apply_action(record, action, payload, actor):
    require_action(actor, action)
    row = copy.deepcopy(record)
    status = row['status']
    if action in ['finish_step', 'submit'] and row.get('importedProgress') and not (row.get('importInfo') or {}).get('reviewed'):
        fail('请先退回待确认，完善并确认处理方案后再执行')
    if action == 'edit':
        if status != 'pending_confirmation':
            fail('已确认内容已锁定，请先填写原因并退回待确认')
        previous = snapshot(row)
        row.update(draft_data(payload.get('draft'), row['quantity'] - remaining(row)))
        history(row, actor, '更新待确认内容', '保存不良信息与待讨论方案', previous)
    elif action == 'confirm':
        if status != 'pending_confirmation':
            fail('只有待确认记录可以确认')
        editable = {key: row[key] for key in empty_draft()}
        checked = draft_data(editable, row['quantity'] - remaining(row))
        if not all([row['disposition'], row['treatment'].strip(), row['assignee'].strip(), row['plannedDate']]):
            fail('确认前请填写处置方式、处理要求、执行负责人和计划完成时间')
        steps = checked['planSteps']
        if not steps or any(not step['requirement'] for step in steps):
            fail('确认前请填写每个处理步骤的要求')
        if not any(step['kind'] == row['disposition'] for step in steps):
            fail('处理步骤须包含所选处置方式')
        if any(step['kind'] == 'scrap' for step in steps) and (row['disposition'] != 'scrap' or any(step['kind'] != 'scrap' for step in steps)):
            fail('报废须作为单独方案确认；部分产品报废时先退回讨论剩余数量')
        if not checked['inspectionItems'] or any(not item['name'] or not item['standard'] for item in checked['inspectionItems']):
            fail('确认前至少填写一个验收项目及标准')
        release = checked['release']
        if release['mode'] == 'concession' and (not release['basis'] or not release['approvedBy']):
            fail('让步放行须记录批准依据及批准人')
        if remaining(row) <= 0:
            fail('全部数量已验收，请由品质核对历史结果')
        previous = snapshot(row)
        row.update(checked, status='pending', paused=False)
        if row.get('importInfo'):
            row['importInfo']['reviewed'] = True
        history(row, actor, '确认处理方案', f"整条 {row['quantity']} 件；本轮剩余 {remaining(row)} 件；计划 {row['plannedDate']}；顺序 {row['priority']}", previous)
    elif action == 'return':
        if status not in ['pending', 'processing', 'inspection']:
            fail('只有未关闭的已确认记录可以退回')
        reason = string(payload.get('reason'), '退回原因', 1000)
        if not reason:
            fail('请填写退回原因')
        previous = snapshot(row)
        row.update(status='pending_confirmation', paused=True, submission=None)
        history(row, actor, '退回待确认', f'原因：{reason}。原任务暂停，已验收数量及模具就绪情况保留。', previous)
    elif action == 'prepare':
        if not has_rework(row) or status not in ['pending', 'processing']:
            fail('仅待处理或处理中的返工任务可更新模具就绪情况')
        rework_steps = [step for step in row['planSteps'] if step['kind'] == 'rework']
        if rework_steps and all(step['completedAt'] for step in rework_steps):
            fail('本轮返工步骤已完成，不能再修改模具就绪情况')
        if type(payload.get('ready')) is not bool:
            fail('模具就绪状态无效')
        row['moldReady'] = payload['ready']
        history(row, actor, '更新模具就绪', '返工模具已就绪' if row['moldReady'] else '返工模具尚未就绪')
    elif action == 'start':
        if status != 'pending':
            fail('只有待处理任务可以开工')
        step = active_step(row)
        if (step['kind'] if step else row['disposition']) == 'rework' and not row['moldReady']:
            fail('返工模具尚未就绪')
        row['status'] = 'processing'
        history(row, actor, '开始处理', f"{row['assignee']} 开始按已确认方案处理")
    elif action == 'finish_step':
        if status != 'processing':
            fail('只有处理中的任务可以记录步骤完成')
        step = active_step(row)
        if not step or step['id'] != payload.get('stepId'):
            fail('请按已确认顺序完成当前步骤')
        if step['kind'] == 'rework' and not row['moldReady']:
            fail('返工模具尚未就绪')
        note = string(payload.get('note'), '本步实际处理情况', 2000)
        if not note:
            fail('请填写本步实际处理情况')
        step.update(completedAt=now(), completedBy=actor_info(actor)['name'], result=note)
        history(row, actor, '完成处理步骤', f"{LABELS[step['kind']]}；{note}。数量以本轮提交及品质验收为准。")
    elif action == 'submit':
        if status != 'processing':
            fail('只有处理中的任务可以提交验收')
        if active_step(row):
            fail('请先按顺序完成本轮全部处理步骤，再提交品质验收')
        result = payload.get('result')
        if not isinstance(result, dict):
            fail('处理结果格式不正确')
        result = {key: integer(result.get(key, 0), '本次结果数量') for key in ['good', 'scrap', 'other']} | {'note': string(result.get('note'), '处理结果说明', 2000)}
        total = sum(result[key] for key in ['good', 'scrap', 'other'])
        if not 0 < total <= remaining(row):
            fail('本次结果数量须大于零，且不能超过剩余待处理数量')
        kind = row['disposition']
        if kind == 'scrap' and result['good']:
            fail('报废方案只能提交报废数量')
        if kind != 'scrap' and result['scrap']:
            fail('需要报废剩余产品时，请退回待确认后确认报废方案')
        if kind == 'other' and (result['good'] or result['scrap']):
            fail('其他处置请填写按方案完成的数量')
        if kind != 'other' and result['other']:
            fail('其他处置数量只能用于其他方案')
        if not result['note']:
            fail('请填写处理结果说明')
        row.update(submission=result, status='inspection')
        history(row, actor, '提交品质验收', f"本次合格 {result['good']} 件，报废 {result['scrap']} 件，其他处置 {result['other']} 件；{result['note']}")
    elif action == 'inspect':
        if status != 'inspection' or not row['submission']:
            fail('没有待验收的处理结果')
        passed = payload.get('passed')
        if type(passed) is not bool:
            fail('请选择验收结论')
        note = string(payload.get('note'), '品质验收意见', 2000)
        if not note:
            fail('请填写品质验收意见')
        evidence = payload.get('evidence') or {}
        if not isinstance(evidence, dict):
            fail('验收明细格式不正确')
        checks = evidence.get('checks', [])
        if not isinstance(checks, list) or len(checks) > 30 or any(not isinstance(check, dict) for check in checks):
            fail('验收明细格式不正确')
        clean_checks = [{'id': string(check.get('id'), '验收项目标识', 150), 'actual': string(check.get('actual', ''), '实测结果', 2000), 'passed': check.get('passed') if type(check.get('passed')) is bool else None} for check in checks]
        evidence = {'checks': clean_checks, 'quantityChecked': evidence.get('quantityChecked') is True, 'releaseChecked': evidence.get('releaseChecked') is True}
        if passed:
            if not evidence['quantityChecked']:
                fail('验收通过前须核对本次实物数量')
            expected = row['inspectionItems']
            if not expected or len(checks) != len(expected) or any(len(found := [check for check in clean_checks if check['id'] == item['id']]) != 1 or not found[0]['actual'] or found[0]['passed'] is not True for item in expected):
                fail('验收通过前，每个项目须填写实测或核实结果并判定通过')
            release = row['release']
            if (release['mode'] == 'concession' or any(value for key, value in release.items() if key != 'mode')) and not evidence['releaseChecked']:
                fail('验收通过前须核对放行及发货要求')
        result = row['submission']
        if not 0 < sum(result.get(key, 0) for key in ['good', 'scrap', 'other']) <= remaining(row):
            fail('待验收数量与剩余数量不符，请退回待确认核对')
        previous = snapshot(row, inspection=evidence | {'passed': passed, 'note': note})
        if passed:
            for result_key, record_key in [('good', 'acceptedQty'), ('scrap', 'scrappedQty'), ('other', 'otherQty')]:
                row[record_key] = row.get(record_key, 0) + result.get(result_key, 0)
        closed = passed and remaining(row) == 0
        row.update(submission=None, status='closed' if closed else 'processing')
        if closed:
            row['actualDate'] = today()
        else:
            reset_steps(row)
        history(row, actor, ('验收通过并关闭' if closed else '部分验收通过') if passed else '验收不通过', f"{note}；本次合格 {result['good']}、报废 {result['scrap']}、其他处置 {result.get('other', 0)}；剩余 {remaining(row)} 件。" + ('' if passed else '本次结果未计入已验收数量。'), previous)
    else:
        fail('无效的处理操作')
    return row
