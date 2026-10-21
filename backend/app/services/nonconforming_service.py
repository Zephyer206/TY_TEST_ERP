import base64
import copy
import re
from uuid import uuid4
from sqlalchemy import func, select, text
from app.models.nonconforming import NonconformingRecord, NonconformingReworkMold, NonconformingImportBatch
from app.services.nonconforming_workflow import (actor_info, apply_action, empty_draft, fail, has_rework_history, history, new_record, now, require_action, string)
from app.services.nonconforming_import_completion import apply_source_schedule, complete_from_source_date

def record_output(model):
    return copy.deepcopy(model.payload) | {'revision': model.revision}

def record_model(payload):
    return NonconformingRecord(id=payload['id'], company=payload['company'], record_no=payload['no'],
        part_no=payload['partNo'], status=payload['status'], quantity=payload['quantity'],
        quantity_verified=payload['quantityVerified'], priority=payload['priority'], revision=1, payload=payload)

def save_record(model, payload):
    model.payload = payload
    model.part_no = payload['partNo']; model.status = payload['status']; model.quantity = payload['quantity']
    model.quantity_verified = payload['quantityVerified']; model.priority = payload['priority']; model.revision += 1

async def lock_company(db, company):
    await db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:scope))'), {'scope': f'nonconforming:{company}'})

async def workspace(db, company, actor, created_id=None):
    models = list((await db.execute(select(NonconformingRecord).where(NonconformingRecord.company == company).order_by(NonconformingRecord.priority, NonconformingRecord.id))).scalars())
    molds = list((await db.execute(select(NonconformingReworkMold).where(NonconformingReworkMold.company == company).order_by(NonconformingReworkMold.part_no, NonconformingReworkMold.id))).scalars())
    batch_ids = {row.payload['importInfo']['batchId'] for row in models if row.payload.get('importInfo')}
    batch = (await db.execute(select(NonconformingImportBatch).where(NonconformingImportBatch.id.in_(batch_ids)).order_by(NonconformingImportBatch.created_at.desc()))).scalars().first() if batch_ids else None
    return {'records': [record_output(row) for row in models], 'molds': [record_output(row) for row in molds],
            'workbook': copy.deepcopy(batch.metadata_json) if batch else None, 'actor': actor_info(actor), 'serverTime': now(), 'createdId': created_id}

async def get_record(db, company, identity, revision):
    model = (await db.execute(select(NonconformingRecord).where(NonconformingRecord.company == company, NonconformingRecord.id == identity).with_for_update())).scalar_one_or_none()
    if not model:
        fail('记录不存在或不属于当前公司', 404)
    if model.revision != revision:
        fail('记录已被其他人更新，请刷新页面核对后再操作；本次未保存', 409)
    return model

async def create_record(db, company, draft, actor):
    await lock_company(db, company)
    priority = (await db.execute(select(func.max(NonconformingRecord.priority)).where(NonconformingRecord.company == company))).scalar() or 0
    row = new_record(draft, actor, company, priority + 1)
    db.add(record_model(row)); await db.flush()
    return await workspace(db, company, actor, row['id'])

async def execute_action(db, company, identity, command, actor):
    await lock_company(db, company)
    model = await get_record(db, company, identity, command.revision)
    if command.action == 'move':
        require_action(actor, 'priority')
        target_id = string(command.payload.get('targetId'), '目标记录', 120)
        if type(command.payload.get('targetRevision')) is not int or target_id == identity:
            fail('目标记录版本或顺序无效')
        target = await get_record(db, company, target_id, command.payload['targetRevision'])
        if model.status != 'pending_confirmation' or target.status != 'pending_confirmation':
            fail('已确认的处理顺序已锁定')
        left, right = copy.deepcopy(model.payload), copy.deepcopy(target.payload)
        left['priority'], right['priority'] = right['priority'], left['priority']
        for entity, payload in [(model, left), (target, right)]:
            history(payload, actor, '调整处理顺序', f"当前顺序 {payload['priority']}")
            save_record(entity, payload)
    else:
        save_record(model, apply_action(model.payload, command.action, command.payload, actor))
    await db.flush()
    return await workspace(db, company, actor)

async def save_mold(db, company, draft, actor):
    require_action(actor, 'mold')
    if company != draft.company or not draft.partNo.strip():
        fail('请填写当前公司的零件号')
    await lock_company(db, company)
    part_no = draft.partNo.strip()
    if len(set(draft.defectIds)) != len(draft.defectIds):
        fail('关联不良记录不能重复')
    linked = list((await db.execute(select(NonconformingRecord).where(NonconformingRecord.company == company, NonconformingRecord.id.in_(draft.defectIds)))).scalars())
    if len(linked) != len(draft.defectIds) or any(row.part_no != part_no or not has_rework_history(row.payload) for row in linked):
        fail('只能关联同一零件号且当前或历史方案含返工的记录')
    for photo in draft.photos:
        if len(photo) > 700000 or not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=\r\n]+', photo):
            fail('照片须为不超过500KB的 PNG、JPEG 或 WebP')
        try:
            if len(base64.b64decode(photo.split(',', 1)[1].replace('\r', '').replace('\n', ''), validate=True)) > 500 * 1024:
                fail('照片不能超过500KB')
        except ValueError:
            fail('照片数据格式不正确')
    payload = draft.model_dump(exclude={'revision'})
    payload.update(id=draft.id or str(uuid4()), partNo=part_no, location=draft.location.strip())
    if draft.id:
        model = (await db.execute(select(NonconformingReworkMold).where(NonconformingReworkMold.company == company, NonconformingReworkMold.id == draft.id).with_for_update())).scalar_one_or_none()
        if not model:
            fail('返工模不存在或不属于当前公司', 404)
        if draft.revision != model.revision:
            fail('返工模已被其他人更新，请刷新页面核对后再操作；本次未保存', 409)
        model.payload = payload; model.part_no = part_no; model.revision += 1
    else:
        db.add(NonconformingReworkMold(id=payload['id'], company=company, part_no=part_no, revision=1, payload=payload))
    await db.flush()
    return await workspace(db, company, actor)

async def import_workbook(db, bundle, actor):
    require_action(actor, 'create')
    await lock_company(db, 'tianyue')
    batch = await db.get(NonconformingImportBatch, bundle['batchId'])
    if batch and batch.source_hash != bundle['sha256']:
        fail('导入批次与源文件摘要不匹配，未修改数据', 409)
    if not batch:
        metadata = {key: value for key, value in bundle.items() if key != 'records'}
        metadata['importedBy'] = actor.id
        db.add(NonconformingImportBatch(id=bundle['batchId'], source_hash=bundle['sha256'], file_name=bundle['fileName'], metadata_json=metadata))
    existing = set((await db.execute(select(NonconformingRecord.id).where(NonconformingRecord.id.in_([row['id'] for row in bundle['records']])))).scalars())
    priority = (await db.execute(select(func.max(NonconformingRecord.priority)).where(NonconformingRecord.company == 'tianyue'))).scalar() or 0
    for original in bundle['records']:
        if original['id'] in existing:
            continue
        priority += 1
        row = empty_draft() | copy.deepcopy(original) | {'company': 'tianyue', 'priority': priority, 'status': 'pending_confirmation',
            'moldReady': False, 'paused': False, 'acceptedQty': 0, 'scrappedQty': 0, 'otherQty': 0,
            'submission': None, 'actualDate': '', 'createdAt': now(), 'history': []}
        row['importInfo']['reviewNotes'] = [note.replace('暂放天越预览', '暂归天越、公司权属待核对') for note in row['importInfo']['reviewNotes']]
        row['importInfo']['reviewed'] = False
        history(row, actor, 'Excel 导入数据库', '保留全部原表字段及来源行；等待品质核对确认，未生成验收结果。')
        complete_from_source_date(row, actor)
        apply_source_schedule(row, actor)
        db.add(record_model(row))
    await db.flush()
    return {'sourceRows': bundle['sourceRows'], 'expectedRecords': len(bundle['records']), 'inserted': len(bundle['records']) - len(existing), 'alreadyPresent': len(existing)}
