"""Simple costing workflow: candidates, tasks, previews, immutable versions and exports."""
import csv
import io
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, func, or_
from app.api.deps import CurrentUser, DbSession, require_role
from app.models.costing import CostingTask, CostingItem, CostingRevision
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.part_tooling_spec import PartToolingSpec
from app.models.tooling import Tooling, ToolingPart
from app.models.material_dict import MaterialDict
from app.models.price import TreatmentDict
from app.schemas.costing import TaskCreate, ItemCreate, CostingInput, RevisionCreate, MaterialCalculation, QuotationPreview, SimpleCalculation, TreatmentCharge
from app.services.costing_service import resolve_identity, context_for, resolve_calculation, eligibility, encode, digest
from app.services.costing_calculator import quotation_material, calculate_simple

router = APIRouter(prefix='/costing', tags=['Simple Costing'])


async def item_identity(db, item):
    task = await db.get(CostingTask, item.task_id)
    return await resolve_identity(db, item.alias_id, item.part_id, item.tooling_id, item.spec_id, task.customer_id)


@router.get('/catalog')
async def catalog(db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    materials = (await db.execute(select(MaterialDict).where(MaterialDict.is_active == True).order_by(MaterialDict.name))).scalars().all()
    rules = (await db.execute(select(TreatmentDict).where(TreatmentDict.is_active == True).order_by(TreatmentDict.sort_order))).scalars().all()
    return encode(dict(materials=[dict(id=m.id, name=m.name, code=m.code, density=m.density,
        material_price=m.default_price, scrap_price=m.scrap_price) for m in materials],
        treatments=[dict(id=r.id, name=r.name, rate=r.default_rate, unit=r.unit, calc_mode=r.calc_mode) for r in rules]))


@router.post('/material-preview')
async def material_preview(payload: MaterialCalculation, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    return quotation_material(payload)


@router.post('/quotation-preview')
async def quotation_preview(payload: QuotationPreview, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    material = payload.material.model_copy(deep=True)
    weights = quotation_material(material)
    if weights['gross_weight_g'] is not None:
        material.quoted_gross_weight_g = Decimal(weights['gross_weight_g'])
    snapshot = payload.surface_rule_snapshot.model_dump(mode='json') if payload.surface_rule_snapshot else None
    if payload.surface_rule_id and (not snapshot or snapshot.get('id') != payload.surface_rule_id):
        rule = await db.get(TreatmentDict,payload.surface_rule_id)
        if not rule or not rule.is_active or (rule.calc_mode,rule.unit) not in {('manual','元/件'),('net_weight','元/kg')}:
            raise HTTPException(422,'收费规则不可用')
        snapshot = encode(dict(id=rule.id,name=rule.name,rate=rule.default_rate,
            method='net_kg' if rule.calc_mode=='net_weight' else 'piece',unit=rule.unit,updated_at=rule.updated_at))
    rate = snapshot.get('rate') if snapshot else payload.surface_fee
    charge = TreatmentCharge(item_key='quotation-surface',name='表面处理',
        method=snapshot.get('method','piece') if snapshot else 'piece', rate=rate,
        source=f"共用收费规则：{snapshot['name']}" if snapshot else '本次报价按件费用')
    result = calculate_simple(SimpleCalculation(material=material,treatment_status='required',treatments=[charge]))
    return dict(**result,surface_rule_snapshot=snapshot)


async def candidate_rows(db, customer_id, keyword='', limit=100, offset=0):
    query = select(Part, PartCustomerAlias, Tooling, PartToolingSpec).join(PartCustomerAlias, PartCustomerAlias.part_id == Part.id)
    query = query.join(ToolingPart, ToolingPart.part_id == Part.id).join(Tooling, Tooling.id == ToolingPart.tooling_id)
    query = query.outerjoin(PartToolingSpec, (PartToolingSpec.part_id == Part.id) & (PartToolingSpec.tooling_id == Tooling.id))
    query = query.where(PartCustomerAlias.customer_id == customer_id, PartCustomerAlias.is_active == True,
        PartCustomerAlias.data_quality_status == 'approved', Part.is_deleted == False, Tooling.is_deleted == False)
    if keyword:
        query = query.where(or_(PartCustomerAlias.customer_part_no.ilike(f'%{keyword}%'),
            Part.internal_name.ilike(f'%{keyword}%'), Tooling.tooling_number.ilike(f'%{keyword}%')))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(PartCustomerAlias.customer_part_no, Tooling.tooling_number, PartToolingSpec.id).offset(offset).limit(limit))).all()
    return total, [dict(alias_id=a.id, part_id=p.id, tooling_id=t.id, spec_id=s.id if s else None,
        customer_part_no=a.customer_part_no, part_name=p.internal_name, material_name=p.material_name,
        tooling_number=t.tooling_number, mold_type=t.mold_type, spec_twph=s.spec_twph if s else p.spec_twph,
        eligibility=eligibility(t)[0], reason=eligibility(t)[1]) for p,a,t,s in rows]


@router.get('/candidates')
async def candidates(db: DbSession, current_user: CurrentUser, customer_id: int, keyword: str = '',
    limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
    require_role(current_user, min_level=2)
    total, rows = await candidate_rows(db, customer_id, keyword, limit, offset)
    return dict(total=total, items=rows)


@router.post('/tasks')
async def create_task(payload: TaskCreate, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    if not payload.name.strip() or not await db.get(Customer, payload.customer_id):
        raise HTTPException(422, '请填写任务名称并选择有效客户')
    task = CostingTask(name=payload.name.strip(), customer_id=payload.customer_id, created_by=current_user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return encode(task)


@router.get('/tasks')
async def list_tasks(db: DbSession, current_user: CurrentUser, customer_id: int | None = None):
    require_role(current_user, min_level=2)
    query = select(CostingTask, Customer.name).join(Customer, CostingTask.customer_id == Customer.id)
    if customer_id:
        query = query.where(CostingTask.customer_id == customer_id)
    rows = (await db.execute(query.order_by(CostingTask.id.desc()).limit(200))).all()
    return [encode(dict(id=t.id, name=t.name, customer_id=t.customer_id, customer=n, created_at=t.created_at)) for t,n in rows]


@router.get('/tasks/{task_id}')
async def task_detail(task_id: int, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    task = await db.get(CostingTask, task_id)
    if not task:
        raise HTTPException(404, '核算任务不存在')
    rows = (await db.execute(select(CostingItem,PartCustomerAlias.customer_part_no,Part.internal_name,Tooling.tooling_number,CostingRevision)
        .join(PartCustomerAlias,PartCustomerAlias.id==CostingItem.alias_id).join(Part,Part.id==CostingItem.part_id)
        .join(Tooling,Tooling.id==CostingItem.tooling_id).outerjoin(CostingRevision,
            (CostingRevision.item_id==CostingItem.id)&(CostingRevision.revision_no==CostingItem.version))
        .where(CostingItem.task_id==task.id).order_by(CostingItem.id))).all()
    result = []
    for item,part_no,part_name,tooling_no,latest in rows:
        result.append(dict(id=item.id, version=item.version, part_id=item.part_id, alias_id=item.alias_id,
            tooling_id=item.tooling_id, spec_id=item.spec_id, customer_part_no=part_no,
            part_name=part_name, tooling_number=tooling_no,
            latest_revision_id=latest.id if latest else None, result=latest.result if latest else None))
    return encode(dict(id=task.id, name=task.name, customer_id=task.customer_id, items=result))


@router.post('/tasks/{task_id}/items')
async def add_item(task_id: int, payload: ItemCreate, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    task = (await db.execute(select(CostingTask).where(CostingTask.id == task_id).with_for_update())).scalar_one_or_none()
    if not task:
        raise HTTPException(404, '任务不存在')
    await resolve_identity(db, payload.alias_id, payload.part_id, payload.tooling_id, payload.spec_id, task.customer_id)
    key = str(payload.spec_id or 'part-spec')
    existing = (await db.execute(select(CostingItem).where(CostingItem.task_id==task.id,
        CostingItem.alias_id==payload.alias_id, CostingItem.tooling_id==payload.tooling_id, CostingItem.scheme_key==key))).scalar_one_or_none()
    if existing:
        return encode(existing)
    item = CostingItem(task_id=task.id, **payload.model_dump(), scheme_key=key, version=0)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return encode(item)


@router.get('/items/{item_id}/context')
async def item_context(item_id: int, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    item = await db.get(CostingItem,item_id)
    if not item:
        raise HTTPException(404, '核算明细不存在')
    context=await context_for(db, await item_identity(db,item))
    context['import_source']=item.source_reference
    return context


@router.post('/items/{item_id}/preview')
async def preview(item_id: int, payload: CostingInput, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    item = await db.get(CostingItem,item_id)
    if not item:
        raise HTTPException(404,'核算明细不存在')
    return await resolve_calculation(db, await item_identity(db,item), payload,item.source_reference)


@router.post('/items/{item_id}/revisions')
async def save_revision(item_id: int, payload: RevisionCreate, db: DbSession, current_user: CurrentUser):
    require_role(current_user, min_level=2)
    item = (await db.execute(select(CostingItem).where(CostingItem.id == item_id).with_for_update())).scalar_one_or_none()
    if not item:
        raise HTTPException(404,'核算明细不存在')
    hashed = digest(payload.model_dump(exclude={'request_id'}))
    previous = (await db.execute(select(CostingRevision).where(CostingRevision.item_id==item.id,
        CostingRevision.request_id==payload.request_id))).scalar_one_or_none()
    if previous:
        if previous.payload_hash != hashed:
            raise HTTPException(409,'重复请求标识与内容不同')
        return encode(previous)
    if item.version != payload.expected_version:
        raise HTTPException(409,'核算明细已有新版本，请刷新核对')
    if not payload.expected_source_token:
        raise HTTPException(422,'请先试算并核对来源，再保存')
    resolved = await resolve_calculation(db, await item_identity(db,item), payload,item.source_reference)
    item.version += 1
    revision = CostingRevision(item_id=item.id, revision_no=item.version, request_id=payload.request_id,
        payload_hash=hashed, inputs=resolved['calculation'], result=resolved['result'], context=resolved['context'],
        reason=payload.reason, created_by=current_user.id)
    db.add(revision)
    await db.commit()
    await db.refresh(revision)
    return encode(revision)


@router.get('/items/{item_id}/revisions')
async def revisions(item_id: int, db: DbSession, current_user: CurrentUser):
    require_role(current_user,min_level=2)
    return encode((await db.execute(select(CostingRevision).where(CostingRevision.item_id==item_id)
        .order_by(CostingRevision.revision_no.desc()).limit(100))).scalars().all())


def csv_text(value):
    value = '' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value


@router.get('/tasks/{task_id}/export')
async def export_task(task_id: int, db: DbSession, current_user: CurrentUser):
    require_role(current_user,min_level=2)
    if not await db.get(CostingTask,task_id):
        raise HTTPException(404,'任务不存在')
    # One query freezes the set of saved revisions; no live recalculation on export.
    rows = (await db.execute(select(CostingRevision).join(CostingItem,CostingItem.id==CostingRevision.item_id)
        .where(CostingItem.task_id==task_id).order_by(CostingRevision.item_id,CostingRevision.revision_no))).scalars().all()
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['客户','客户件号','零件','模具','规格','版本','材料','表面处理','特殊成本','模摊','已知小计','完整合计','状态','缺项','单位','价格来源','重量依据','时间'])
    for r in rows:
        c,v=r.context,r.result
        optional=v['optional_costs']
        selected_special=[x for x in optional if x['category']=='special_cost' and x['selected']]
        special=(sum((Decimal(x['amount']) for x in selected_special if x['amount'] is not None),Decimal(0))
            if selected_special and all(x['amount'] is not None for x in selected_special) else ('待完善' if selected_special else '未选用'))
        mold=next((x['amount'] if x['selected'] else '未选用' for x in optional if x['category']=='tooling_amortization'),None)
        writer.writerow([csv_text(x) for x in [c['customer'],c['customer_part_no'],c['part_name'],c['tooling_number'],c['spec_twph'],
            r.revision_no,v['material']['amount'],v['surface_amount'],special,mold,v['known_subtotal'],v['total'],
            v['completeness'],'；'.join(v['issues']),'元/件',str(c['sources']),v['material']['net_weight_basis'],r.created_at]])
    return Response(('\ufeff'+output.getvalue()).encode('utf-8'),media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="costing-{task_id}.csv"'})


@router.post('/imports/preview')
async def import_preview(db: DbSession, current_user: CurrentUser, customer_id: int, file: UploadFile = File(...)):
    require_role(current_user,min_level=2)
    content=await file.read(5*1024*1024+1)
    if len(content)>5*1024*1024:
        raise HTTPException(413,'参考文件请控制在 5MB 内')
    try:
        from openpyxl import load_workbook
        from zipfile import ZipFile
        with ZipFile(io.BytesIO(content)) as z:
            if sum(x.file_size for x in z.infolist())>30*1024*1024:
                raise ValueError('expanded file too large')
        workbook=load_workbook(io.BytesIO(content),read_only=False,data_only=True)
        sheet=workbook.worksheets[0]
        if sheet.max_row>1001 or sheet.max_column>80:
            raise ValueError('too many rows')
        values=[list(row) for row in sheet.iter_rows(values_only=True)]
        for merged in sheet.merged_cells.ranges:
            value=sheet.cell(merged.min_row,merged.min_col).value
            for rr in range(merged.min_row,merged.max_row+1):
                for cc in range(merged.min_col,merged.max_col+1):
                    values[rr-1][cc-1]=value
        workbook.close()
    except Exception:
        raise HTTPException(422,'无法读取参考表：请使用 1000 行、80 列以内的有效 xlsx')
    headers=[str(x or '').strip() for x in values[0]] if values else []
    def column(names):
        return next((i for i,x in enumerate(headers) if x in names),None)
    no_idx=column({'原图产品编号','客户件号','规格型号'})
    mold_idx=column({'本厂产品编号','模具编号','模具号'})
    if no_idx is None:
        raise HTTPException(422,'未找到客户件号列（支持原图产品编号、客户件号、规格型号）')
    result=[]
    for i,row in enumerate(values[1:],2):
        no=str(row[no_idx] or '').strip()
        if not no:
            continue
        _,candidates=await candidate_rows(db,customer_id,no,200)
        exact=[x for x in candidates if x['customer_part_no']==no]
        mold=str(row[mold_idx] or '').strip() if mold_idx is not None else ''
        matched=[x for x in exact if not mold or x['tooling_number']==mold]
        def original(names):
            idx=column(names)
            return row[idx] if idx is not None else None
        source=dict(sheet=sheet.title,row=i,original_part_no=no,original_tooling=mold,
            values=dict(net_weight_g=original({'产品净重/g','净重','净重(g)'}),
                gross_weight_g=original({'单件毛重量(g)','毛重','毛重(g)'}),
                surface_treatment=original({'表面核算','表面处理'})))
        result.append(dict(row=i,customer_part_no=no,tooling_number=mold,candidates=matched or candidates,source_reference=source,
            status='exact' if len(matched)==1 and matched[0]['eligibility']=='eligible' else 'needs_review',
            reason='' if len(matched)==1 and matched[0]['eligibility']=='eligible' else '件号/模具/规格/类型需明确选择；未自动导入'))
    return dict(sheet=sheet.title,rows=result)
