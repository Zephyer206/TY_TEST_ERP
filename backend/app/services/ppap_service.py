"""Company-scoped PPAP commands, quality permissions and immutable snapshots."""
import copy
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from fastapi.encoders import jsonable_encoder
from app.core.config import settings
from app.models.ppap import PpapArchive, PpapFolder, PpapDocument, PpapFileVersion, PpapSubmission, PpapAuditLog
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.tooling import Tooling, ToolingPart
from app.models.gaibo import GaiboCustomerWorkspace, GaiboCustomerRequirement, GaiboInstallationPackage, GaiboPackageItem, GaiboSinglePart


def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)


def uid():
    return uuid4().hex


def actor_name(actor):
    return actor.real_name or actor.username


def can_write(actor):
    # Formal permissions depend on department, never on seniority alone.
    return actor.dept.strip().lower() in {'quality', 'qc', '品质', '品质部', '质量', '质量部', '质量部门'} or (settings.AUTH_DISABLED and actor.role_level == 4)


def require_quality(actor):
    if not can_write(actor):
        fail('仅质量部门可以维护PPAP资料', 403)


def safe_name(value, limit=200):
    value = value.strip()
    if not value or len(value) > limit or value in {'.', '..'} or re.search(r'[\\/:*?"<>|\x00-\x1f]', value) or value.endswith(('.', ' ')):
        fail('名称不可为空或包含路径分隔符及特殊字符')
    return value


def row_data(row):
    return jsonable_encoder({c.name: getattr(row, c.name) for c in row.__table__.columns})


async def get_archive(db, company, archive_id, revision=None):
    query = select(PpapArchive).where(PpapArchive.id == archive_id, PpapArchive.company == company)
    if revision is not None:
        query = query.with_for_update()
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        fail('PPAP档案不存在或不属于当前公司', 404)
    if revision is not None and row.revision != revision:
        fail('资料已被更新，请重新加载后再操作', 409)
    return row


async def audit(db, archive, actor, action, detail=None):
    archive.revision += 1
    archive.updated_at = datetime.utcnow()
    db.add(PpapAuditLog(id=uid(), archive_id=archive.id, action=action, detail=jsonable_encoder(detail or {}), actor_id=actor.id, actor_name=actor_name(actor)))
    await db.flush()


async def customer(db, company, key):
    try:
        prefix, raw_id = key.split(':')
        target_id = int(raw_id)
    except (ValueError, AttributeError):
        fail('请选择当前公司的有效客户')
    if company == 'tianyue' and prefix == 'customer':
        name = (await db.execute(select(Customer.name).where(Customer.id == target_id, Customer.is_active.is_(True)))).scalar_one_or_none()
    elif company == 'gaibo' and prefix == 'workspace':
        name = (await db.execute(select(GaiboCustomerWorkspace.display_name).where(GaiboCustomerWorkspace.id == target_id, GaiboCustomerWorkspace.is_active.is_(True)))).scalar_one_or_none()
    else:
        fail('客户不属于当前公司')
    if not name:
        fail('客户不存在或已停用')
    return target_id, name


async def resolve_link(db, company, customer_id, key):
    try:
        kind, raw_id = key.split(':')
        target_id = int(raw_id)
    except (ValueError, AttributeError):
        fail('关联对象格式不正确')
    result = dict(key=key, source_id=target_id, kind=kind, part_no='', name='', tooling_no='', mold_type='', drawing_version='', composition=[])
    if company == 'tianyue' and kind == 'part':
        p = (await db.execute(select(Part.id, Part.customer_id, Part.customer_part_no, Part.internal_name, Part.version).where(Part.id == target_id, Part.is_deleted.is_(False)))).first()
        alias = (await db.execute(select(PartCustomerAlias.customer_part_no, PartCustomerAlias.customer_part_name, PartCustomerAlias.revision).where(PartCustomerAlias.part_id == target_id, PartCustomerAlias.customer_id == customer_id, PartCustomerAlias.is_active.is_(True)).order_by(PartCustomerAlias.id))).first()
        if not p or (p.customer_id != customer_id and not alias):
            fail('关联零件不属于所选客户')
        toolings = (await db.execute(select(Tooling.tooling_number, Tooling.mold_type).join(ToolingPart, ToolingPart.tooling_id == Tooling.id).where(ToolingPart.part_id == target_id, Tooling.is_deleted.is_(False)))).all()
        result.update(part_no=(alias.customer_part_no if alias else p.customer_part_no) or '', name=(alias.customer_part_name if alias else p.internal_name) or p.internal_name or '', drawing_version=(alias.revision if alias else p.version) or '', tooling_no=' / '.join(dict.fromkeys(t.tooling_number for t in toolings)), mold_type=' / '.join(dict.fromkeys(t.mold_type for t in toolings)))
    elif company == 'gaibo' and kind == 'requirement':
        p = (await db.execute(select(GaiboCustomerRequirement.customer_part_number, GaiboSinglePart.name).join(GaiboSinglePart, GaiboSinglePart.id == GaiboCustomerRequirement.single_part_id).where(GaiboCustomerRequirement.id == target_id, GaiboCustomerRequirement.workspace_id == customer_id, GaiboCustomerRequirement.is_active.is_(True)))).first()
        if not p:
            fail('关联单件不属于所选盖博客户')
        result.update(part_no=p.customer_part_number, name=p.name or p.customer_part_number)
    elif company == 'gaibo' and kind == 'package':
        p = (await db.execute(select(GaiboInstallationPackage.package_number, GaiboInstallationPackage.name).where(GaiboInstallationPackage.id == target_id, GaiboInstallationPackage.workspace_id == customer_id, GaiboInstallationPackage.is_active.is_(True)))).first()
        if not p:
            fail('关联安装包不属于所选盖博客户')
        composition = (await db.execute(select(GaiboPackageItem.sequence, GaiboPackageItem.requirement_id, GaiboPackageItem.unlinked_customer_part_number, GaiboPackageItem.tianyue_internal_composition, GaiboPackageItem.quantity).where(GaiboPackageItem.package_id == target_id).order_by(GaiboPackageItem.sequence))).mappings().all()
        result.update(part_no=p.package_number, name=p.name or p.package_number, composition=jsonable_encoder([dict(c) for c in composition]))
    else:
        fail('关联对象不属于当前公司')
    return result


async def resolve_links(db, company, customer_id, inputs):
    keys = [i.key for i in inputs]
    if len(set(keys)) != len(keys):
        fail('同一对象不能重复关联')
    output = []
    for item in inputs:
        link = await resolve_link(db, company, customer_id, item.key)
        for field in ('drawing_version', 'tooling_no', 'mold_type'):
            if getattr(item, field):
                link[field] = getattr(item, field)
        output.append(link)
    return output


async def options(db, company, customer_key=None, search=''):
    if company == 'tianyue':
        customers = (await db.execute(select(Customer.id, Customer.name).where(Customer.is_active.is_(True)).order_by(Customer.name))).all()
        customer_options = [dict(key=f'customer:{r.id}', name=r.name) for r in customers]
    else:
        customers = (await db.execute(select(GaiboCustomerWorkspace.id, GaiboCustomerWorkspace.display_name).where(GaiboCustomerWorkspace.is_active.is_(True)).order_by(GaiboCustomerWorkspace.display_name))).all()
        customer_options = [dict(key=f'workspace:{r.id}', name=r.display_name) for r in customers]
    refs = []
    if customer_key:
        cid, _ = await customer(db, company, customer_key)
        pattern = '%' + search.strip().replace('%', r'\%').replace('_', r'\_') + '%'
        if company == 'tianyue':
            aliases = select(PartCustomerAlias.part_id).where(PartCustomerAlias.customer_id == cid, PartCustomerAlias.is_active.is_(True))
            q = select(Part.id, Part.customer_part_no, Part.internal_name).where(Part.is_deleted.is_(False), or_(Part.customer_id == cid, Part.id.in_(aliases)))
            if search:
                alias_search = select(PartCustomerAlias.part_id).where(PartCustomerAlias.customer_id == cid, PartCustomerAlias.is_active.is_(True), PartCustomerAlias.customer_part_no.ilike(pattern))
                q = q.where(or_(Part.internal_name.ilike(pattern), Part.customer_part_no.ilike(pattern), Part.id.in_(alias_search)))
            rows = (await db.execute(q.order_by(Part.id).limit(100))).all()
            ids = [r.id for r in rows]
            alias_rows = (await db.execute(select(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no, PartCustomerAlias.customer_part_name, PartCustomerAlias.revision).where(PartCustomerAlias.part_id.in_(ids), PartCustomerAlias.customer_id == cid, PartCustomerAlias.is_active.is_(True)).order_by(PartCustomerAlias.id))).all()
            alias_map = {}
            for a in alias_rows:
                alias_map.setdefault(a.part_id, a)
            tooling_rows = (await db.execute(select(ToolingPart.part_id, Tooling.tooling_number, Tooling.mold_type).join(Tooling, Tooling.id == ToolingPart.tooling_id).where(ToolingPart.part_id.in_(ids), Tooling.is_deleted.is_(False)))).all()
            for r in rows:
                alias = alias_map.get(r.id)
                tools = [t for t in tooling_rows if t.part_id == r.id]
                refs.append(dict(key=f'part:{r.id}', kind='part', part_no=(alias.customer_part_no if alias else r.customer_part_no) or '', name=(alias.customer_part_name if alias else r.internal_name) or r.internal_name or '', drawing_version=alias.revision if alias else '', tooling_no=' / '.join(dict.fromkeys(t.tooling_number for t in tools)), mold_type=' / '.join(dict.fromkeys(t.mold_type for t in tools))))
        else:
            for model, kind, number in [(GaiboCustomerRequirement, 'requirement', GaiboCustomerRequirement.customer_part_number), (GaiboInstallationPackage, 'package', GaiboInstallationPackage.package_number)]:
                if kind == 'requirement':
                    q = select(model.id, number.label('number'), GaiboSinglePart.name.label('name')).join(GaiboSinglePart, GaiboSinglePart.id == model.single_part_id)
                    name_column = GaiboSinglePart.name
                else:
                    q = select(model.id, number.label('number'), model.name)
                    name_column = model.name
                q = q.where(model.workspace_id == cid, model.is_active.is_(True))
                if search:
                    q = q.where(or_(number.ilike(pattern), name_column.ilike(pattern)))
                refs += [dict(key=f'{kind}:{r.id}', kind=kind, part_no=r.number, name=r.name or r.number) for r in (await db.execute(q.order_by(model.id).limit(100))).all()]
    return dict(customers=customer_options, references=refs)


async def create_archive(db, company, payload, actor):
    require_quality(actor)
    cid, cname = await customer(db, company, payload.customer_key)
    identity = uid()
    business_now = datetime.now(timezone(timedelta(hours=8)))
    row = PpapArchive(id=identity, company=company, record_no=f"PPAP-{'TY' if company == 'tianyue' else 'GB'}-{business_now:%Y%m%d}-{identity[:12].upper()}", name=payload.name, customer_key=payload.customer_key, customer_name=cname, owner=payload.owner, planned_date=payload.planned_date, remark=payload.remark, links=await resolve_links(db, company, cid, payload.links), revision=0)
    db.add(row)
    await db.flush()
    await audit(db, row, actor, '建立档案', dict(name=row.name))
    return row


async def update_archive(db, row, payload, actor):
    require_quality(actor)
    cid, cname = await customer(db, row.company, payload.customer_key)
    linked = await resolve_links(db, row.company, cid, payload.links)
    attached_keys = set((await db.execute(select(PpapDocument.linked_key).where(PpapDocument.archive_id == row.id, PpapDocument.linked_key.is_not(None)))).scalars().all())
    if not attached_keys.issubset({r['key'] for r in linked}):
        fail('已有文件关联到被移除的对象，请保留该关联明细')
    if payload.customer_key != row.customer_key and (await db.execute(select(PpapSubmission.id).where(PpapSubmission.archive_id == row.id).limit(1))).first():
        fail('已有客户提交记录的档案不能更换客户，请另建档案')
    before = row_data(row)
    for field in ('name', 'customer_key', 'owner', 'planned_date', 'remark'):
        setattr(row, field, getattr(payload, field))
    row.customer_name, row.links = cname, linked
    await audit(db, row, actor, '更新档案', dict(before=before, after=row_data(row)))


async def detail(db, row, actor):
    folders = (await db.execute(select(PpapFolder).where(PpapFolder.archive_id == row.id).order_by(PpapFolder.name))).scalars().all()
    docs = (await db.execute(select(PpapDocument).where(PpapDocument.archive_id == row.id).order_by(PpapDocument.name))).scalars().all()
    versions = (await db.execute(select(PpapFileVersion).join(PpapDocument).where(PpapDocument.archive_id == row.id).order_by(PpapFileVersion.version.desc()))).scalars().all()
    submissions = (await db.execute(select(PpapSubmission).where(PpapSubmission.archive_id == row.id).order_by(PpapSubmission.round_no.desc()))).scalars().all()
    logs = (await db.execute(select(PpapAuditLog).where(PpapAuditLog.archive_id == row.id).order_by(PpapAuditLog.created_at.desc()).limit(200))).scalars().all()
    documents = []
    for doc in docs:
        documents.append(row_data(doc) | dict(versions=[{k: v for k, v in row_data(version).items() if k != 'storage_key'} for version in versions if version.document_id == doc.id]))
    return row_data(row) | dict(status=submissions[0].status if submissions else 'preparing', can_write=can_write(actor), acceptance_mode=settings.AUTH_DISABLED, folders=[row_data(f) for f in folders], documents=documents, submissions=[row_data(s) for s in submissions], audit=[row_data(l) for l in logs])


async def ensure_folder(db, archive_id, folder_id):
    if folder_id and not (await db.execute(select(PpapFolder.id).where(PpapFolder.id == folder_id, PpapFolder.archive_id == archive_id))).scalar_one_or_none():
        fail('文件夹不存在或不属于当前档案', 404)


async def save_folder(db, row, payload, actor, folder_id=None):
    require_quality(actor)
    name = safe_name(payload.name)
    if folder_id:
        folder = (await db.execute(select(PpapFolder).where(PpapFolder.id == folder_id, PpapFolder.archive_id == row.id))).scalar_one_or_none()
        if not folder:
            fail('文件夹不存在', 404)
        parent_id = folder.parent_id
    else:
        parent_id = payload.parent_id
        await ensure_folder(db, row.id, parent_id)
        folder = PpapFolder(id=uid(), archive_id=row.id, parent_id=parent_id, name=name)
    collision = (await db.execute(select(PpapFolder.id).where(PpapFolder.archive_id == row.id, PpapFolder.parent_id == parent_id, func.lower(PpapFolder.name) == name.lower(), PpapFolder.id != folder.id))).first()
    if collision:
        fail('当前目录已有同名文件夹', 409)
    previous = folder.name
    folder.name = name
    db.add(folder)
    await audit(db, row, actor, '重命名文件夹' if folder_id else '新建文件夹', dict(folder_id=folder.id, before=previous, name=name, parent_id=parent_id))


async def get_version(db, archive_id, version_id):
    result = (await db.execute(select(PpapFileVersion, PpapDocument).join(PpapDocument).where(PpapFileVersion.id == version_id, PpapDocument.archive_id == archive_id))).first()
    if not result:
        fail('文件版本不存在或不属于当前档案', 404)
    return result


async def prepare_document(db, row, name, folder_id, linked_key, mode):
    await ensure_folder(db, row.id, folder_id)
    if linked_key and linked_key not in {r['key'] for r in row.links}:
        fail('文件关联对象不属于当前档案')
    doc = (await db.execute(select(PpapDocument).where(PpapDocument.archive_id == row.id, PpapDocument.folder_id == folder_id, func.lower(PpapDocument.name) == name.lower()))).scalar_one_or_none()
    if doc:
        if mode != 'version':
            fail('当前目录存在同名文件，请明确选择更新版本或修改文件名', 409)
        if doc.linked_key != linked_key:
            fail('新版本须保留原文件关联对象')
        doc.current_version += 1
    else:
        if mode == 'version':
            fail('当前目录没有对应文件，请选择新增文件或核对文件名', 404)
        doc = PpapDocument(id=uid(), archive_id=row.id, folder_id=folder_id, name=name, linked_key=linked_key, current_version=1)
        db.add(doc)
        await db.flush()
    return doc


async def submit(db, row, payload, actor):
    require_quality(actor)
    current = await detail(db, row, actor)
    if not row.links:
        fail('请先关联零件或安装包')
    if not current['documents']:
        fail('请先上传本次提交资料')
    # Re-resolve composition now, so the submission records the actual package
    # contents at this moment, rather than the original archive creation date.
    cid, _ = await customer(db, row.company, row.customer_key)
    links = []
    for original in row.links:
        fresh = await resolve_link(db, row.company, cid, original['key'])
        links.append(fresh | {k: original[k] for k in ('tooling_no', 'mold_type', 'drawing_version')})
    documents = []
    for d in current['documents']:
        latest = next(v for v in d['versions'] if v['version'] == d['current_version'])
        documents.append({k: d[k] for k in ('id', 'name', 'folder_id', 'linked_key')} | dict(version=latest))
    snapshot = dict(name=row.name, customer_name=row.customer_name, links=copy.deepcopy(links), folders=copy.deepcopy(current['folders']), documents=documents, remark=payload.remark)
    number = max([s['round_no'] for s in current['submissions']], default=0) + 1
    db.add(PpapSubmission(id=uid(), archive_id=row.id, round_no=number, submitted_date=payload.submitted_date, status='submitted', feedback='', conditions='', snapshot=snapshot, updated_by=actor_name(actor)))
    await audit(db, row, actor, '登记客户提交', dict(round_no=number, submitted_date=payload.submitted_date, file_count=len(documents)))


async def feedback(db, row, submission_id, payload, actor):
    require_quality(actor)
    sub = (await db.execute(select(PpapSubmission).where(PpapSubmission.id == submission_id, PpapSubmission.archive_id == row.id))).scalar_one_or_none()
    if not sub:
        fail('提交记录不存在', 404)
    if payload.status not in {'temporary', 'approved'} and (payload.approved_date or payload.valid_until or payload.conditions):
        fail('仅批准或临时批准时可填写批准信息')
    if payload.status == 'temporary' and not payload.conditions:
        fail('请填写临时批准条件')
    if payload.status != 'temporary' and payload.valid_until:
        fail('仅临时批准可填写有效截止日期')
    if payload.approved_date and sub.submitted_date and payload.approved_date < sub.submitted_date:
        fail('批准日期不能早于提交日期')
    if payload.valid_until and payload.approved_date and payload.valid_until < payload.approved_date:
        fail('有效截止日期不能早于批准日期')
    if payload.evidence_version_id:
        await get_version(db, row.id, payload.evidence_version_id)
    before = row_data(sub)
    for field in ('status', 'feedback', 'approved_date', 'valid_until', 'conditions', 'evidence_version_id'):
        setattr(sub, field, getattr(payload, field))
    sub.updated_by, sub.updated_at = actor_name(actor), datetime.utcnow()
    await audit(db, row, actor, '登记客户反馈', dict(round_no=sub.round_no, before=before, after=row_data(sub)))
