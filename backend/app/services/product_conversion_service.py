"""Explicit B/C conversion; pending/cancelled records do not change physical facts."""
from datetime import timedelta

from sqlalchemy import func, or_, select, update

from app.models import product_box as m
from app.models.part import Part
from app.models.customer import Customer
from app.models.production import ProductionPlan, PlanMachineAssignment
from app.models.machine import Machine
from app.models.warehouse import ScanOperation
from app.services import product_box_service as boxes, product_production_service as production
from app.services import qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, lock_rows, transactional_write, write_audit
from app.models.audit import AuditAction


async def current_quantity(db, box):
    return await db.scalar(select(m.BoxProcessQuantity).join(m.MachineOrderProcessState,
        m.MachineOrderProcessState.id == m.BoxProcessQuantity.state_id).where(
        m.BoxProcessQuantity.box_id == box.id, m.MachineOrderProcessState.order_product_id == box.order_product_id,
        m.MachineOrderProcessState.route_revision_id == box.route_revision_id,
        m.MachineOrderProcessState.process_code == box.current_process_code)
        .order_by(m.BoxProcessQuantity.updated_at.desc(), m.BoxProcessQuantity.id.desc()).limit(1)
        .execution_options(populate_existing=True))


async def quantity_locked(db, box_id, quantity_id):
    return await db.scalar(select(m.ProductFlowEvent.id).where(m.ProductFlowEvent.product_box_id == box_id,
        m.ProductFlowEvent.event_type == 'conversion', or_(
            m.ProductFlowEvent.before_snapshot['quantity_id'].astext == str(quantity_id),
            m.ProductFlowEvent.after_snapshot['entry_quantity_id'].astext == str(quantity_id))).limit(1)) is not None


async def configuration(db, product, route_id=None):
    """Converted targets may run, but cannot be directly bound or create demand."""
    if product.binding_allowed:
        return await boxes.binding_configuration(db, product)
    source = await db.get(m.ProductOrderProduct, product.conversion_source_id) if product.conversion_source_id else None
    plan = await db.get(ProductionPlan, product.order_id)
    route = await db.get(m.ProductRouteRevision, route_id or product.route_revision_id)
    part = await db.get(Part, product.part_id)
    owner = await db.scalar(select(m.ProductOrderContext.business_owner_id).where(m.ProductOrderContext.order_id == product.order_id))
    from app.models.user import User
    user = await db.get(User, owner) if owner else None
    codes = [step.get('code') for step in route.steps_json] if route else []
    if (not source or not source.binding_allowed or source.order_id != product.order_id
            or source.product_code == product.product_code or product.target_qty != 0
            or not plan or str(plan.status).lower() in {'completed','closed','cancelled'}
            or not route or not route.is_published or route.product_code != product.product_code
            or not codes or len(set(codes)) != len(codes) or route.first_output_process_code not in codes
            or not part or part.is_deleted or not user or user.dept != 'sales' or user.role_level < 2):
        production.conflict('转换目标的订单、负责人、件号或路线配置不完整')
    customer = await db.scalar(select(Customer.name).where(Customer.id == part.customer_id)) if part.customer_id else None
    return route, part, customer


async def source_facts(db, box):
    value = await current_quantity(db, box)
    plan = await db.get(ProductionPlan, box.order_id)
    if (box.lifecycle_status != 'active' or box.current_qty <= 0 or not value
            or value.current_qty != box.current_qty or not value.source_quantity_id
            or not plan or str(plan.status).lower() in {'completed','closed','cancelled'}):
        production.conflict('请先核对该框当前工艺的有效实物数量与产出来源')
    state = await db.get(m.MachineOrderProcessState, value.state_id)
    if await production.paused(db, state.id):
        production.conflict('来源工艺已暂停，不能进行产品转换')
    allocation = await db.scalar(select(m.ProductOutputAllocation).where(
        m.ProductOutputAllocation.source_quantity_id == value.source_quantity_id))
    if not allocation or allocation.available_qty < box.current_qty:
        production.conflict('来源用途余额不足，不能进行产品转换')
    return value, state, allocation


async def pair(db, box, target):
    source = await db.get(m.ProductOrderProduct, box.order_product_id)
    if (not target or target.id == source.id or target.order_id != box.order_id
            or target.product_code == source.product_code
            or not (target.conversion_source_id == source.id or source.conversion_source_id == target.id)):
        production.conflict('转换目标须为本订单明确关联的另一B/C产品配置')
    route, part, customer = await configuration(db, target)
    source_route = await db.get(m.ProductRouteRevision, box.route_revision_id)
    if not source_route or not source_route.is_published:
        production.conflict('来源固定路线不可用')
    consumed = [s['code'] for s in source_route.steps_json]
    if box.current_process_code not in consumed:
        production.conflict('来源工艺不在固定路线中')
    consumed = consumed[:consumed.index(box.current_process_code)+1]
    target_codes = [s['code'] for s in route.steps_json]
    common = [c for c in consumed if c in target_codes]
    if not common or common != target_codes[:len(common)]:
        production.conflict('双方工艺历史不能衔接，不能跳过目标前置工艺')
    return source, route, part, customer, common[-1], common


async def allowed(db, actor, action, order_id, **extra):
    try:
        await permissions.require_action(db, actor, action, order_id=order_id, **extra)
        return True
    except QrError:
        return False


async def record_info(db, actor, item):
    pending = item.confirmation_status == 'pending_operator_confirmation'
    manage = pending and await allowed(db, actor, 'supervise', item.order_id)
    child_id = await db.scalar(select(m.ProductBoxRelation.child_box_id).where(m.ProductBoxRelation.id == item.relation_id)) if item.relation_id else None
    return dict(id=str(item.id), product_box_id=str(item.product_box_id), order_id=item.order_id,
        source_order_product_id=str(item.source_order_product_id), target_order_product_id=str(item.target_order_product_id),
        source_product_code=item.source_product_code, target_product_code=item.target_product_code,
        source_process_code=item.source_process_code, target_process_code=item.target_process_code,
        proposed_qty=item.proposed_qty, actual_qty=item.actual_qty, trigger_type=item.trigger_type,
        confirmation_status=item.confirmation_status, version=item.version, created_by=item.created_by,
        confirmed_by=item.confirmed_by, confirmed_at=boxes.iso(item.confirmed_at), cancelled_by=item.cancelled_by,
        cancelled_at=boxes.iso(item.cancelled_at), cancel_reason=item.cancel_reason,
        relation_id=str(item.relation_id) if item.relation_id else None, child_box_id=str(child_id) if child_id else None,
        remark=item.remark, created_at=boxes.iso(item.created_at), can_cancel=manage)


async def options(db, actor, box):
    pending = (await db.scalars(select(m.ProductConversionRecord).where(m.ProductConversionRecord.product_box_id == box.id,
        m.ProductConversionRecord.confirmation_status == 'pending_operator_confirmation').order_by(m.ProductConversionRecord.id))).all()
    result = dict(can_create=False, reason=None, targets=[], pending=[await record_info(db, actor, i) for i in pending])
    if not await allowed(db, actor, 'supervise', box.order_id):
        return result
    try:
        await source_facts(db, box)
    except QrError as error:
        result['reason'] = error.message
        return result
    candidates = (await db.scalars(select(m.ProductOrderProduct).where(m.ProductOrderProduct.order_id == box.order_id,
        m.ProductOrderProduct.product_code != box.product_code).order_by(m.ProductOrderProduct.id))).all()
    for target in candidates:
        try:
            _, route, part, _, entry, _ = await pair(db, box, target)
            result['targets'].append(dict(order_product_id=str(target.id),product_code=target.product_code,
                product_name=part.internal_name,customer_part_no=part.customer_part_no,target_process_code=entry,
                route_code=route.route_code,route_revision=route.revision))
        except QrError:
            continue
    result['can_create'] = bool(result['targets']) and not pending
    return result


async def new_pending(db, actor, box, target, proposed_qty=None, *, trigger_type='manual', target_process=None):
    await source_facts(db, box)
    _, _, _, _, entry, _ = await pair(db, box, target)
    pending = await db.scalar(select(m.ProductConversionRecord).where(m.ProductConversionRecord.product_box_id == box.id,
        m.ProductConversionRecord.confirmation_status == 'pending_operator_confirmation'))
    if pending:
        if pending.target_order_product_id != target.id:
            production.conflict('当前框已有另一项待确认转换，请先处理或取消')
        return pending
    if proposed_qty is None:
        proposed_qty = box.current_qty
    production.quantity(proposed_qty)
    if not 0 < proposed_qty <= box.current_qty:
        production.conflict('建议数量须为正整数且不超过当前实物数量')
    item=m.ProductConversionRecord(product_box_id=box.id,order_id=box.order_id,
        source_order_product_id=box.order_product_id,target_order_product_id=target.id,
        source_product_code=box.product_code,target_product_code=target.product_code,
        source_process_code=box.current_process_code,target_process_code=target_process or entry,
        proposed_qty=proposed_qty,trigger_type=trigger_type,created_by=actor.id)
    db.add(item);await db.flush()
    await write_audit(db,actor.id,AuditAction.CREATE,f'conversion:{item.id}:pending',after=await record_info(db,actor,item))
    return item


async def create_conversion(db,actor,*,box_id,target_order_product_id,expected_version,idempotency_key,proposed_qty=None):
    await permissions.require_action(db,actor,'pool_read',lock=True)
    box=await db.get(m.ProductBox,box_id)
    if not box:raise QrError(404,'ENTITY_NOT_FOUND','产品框不存在')
    await permissions.require_action(db,actor,'supervise',order_id=box.order_id)
    target=await db.get(m.ProductOrderProduct,target_order_product_id)
    if not target:raise QrError(404,'ENTITY_NOT_FOUND','转换目标不存在')
    async def operation():
        await lock_rows(db,order_products=[box.order_product_id,target.id])
        value,source_state,_=await source_facts(db,box)
        current=(await lock_rows(db,states=[source_state.id],boxes=[box.id]))['boxes'][box.id]
        check_version(current.version,expected_version)
        item=await new_pending(db,actor,current,target,proposed_qty)
        return await record_info(db,actor,item)
    return await transactional_write(db,actor.id,'conversion-create',f'box:{box.id}',idempotency_key,
        dict(target_order_product_id=str(target_order_product_id),expected_version=expected_version,proposed_qty=proposed_qty),operation,http_status=201)


async def scan_trigger(db,actor,box,context_id):
    context,state,target,assignment=await production.live_scope(db,actor,context_id)
    await permissions.require_action(db,actor,'conversion_confirm',order_id=target.order_id,
        order_product_id=target.id,context_id=context_id)
    if box.order_id != target.order_id:
        raise QrError(400,'ORDER_MISMATCH','该框与所选订单不一致')
    if box.order_product_id == target.id:
        return
    await lock_rows(db,order_products=[box.order_product_id,target.id])
    _,source_state,_=await source_facts(db,box)
    await lock_rows(db,states=[source_state.id,state.id],boxes=[box.id])
    source,route,_,_,_,common=await pair(db,box,target)
    existing=await db.scalar(select(m.ProductConversionRecord).where(m.ProductConversionRecord.product_box_id==box.id,
        m.ProductConversionRecord.confirmation_status=='pending_operator_confirmation',m.ProductConversionRecord.target_order_product_id==target.id))
    if existing:
        if existing.target_process_code!=state.process_code:
            production.conflict('请选择该待确认转换指定的目标工艺')
        return
    codes=[s['code'] for s in route.steps_json]
    authorizations=source.conversion_authorization.get('targets',[]) if isinstance(source.conversion_authorization,dict) else []
    source_route=await db.get(m.ProductRouteRevision,box.route_revision_id)
    difference=[s['code'] for s in route.steps_json if s['code'] not in [x['code'] for x in source_route.steps_json]]
    authorized=any(a.get('target_order_product_id')==str(target.id) and a.get('source_route_revision_id')==str(box.route_revision_id)
        and a.get('target_route_revision_id')==str(route.id) and a.get('difference_process_codes')==difference
        and a.get('authorized_by') and a.get('authorized_at') for a in authorizations)
    if (not authorized or state.process_code not in difference or len(common)>=len(codes)
            or codes[len(common)]!=state.process_code or await production.paused(db,state.id)):
        production.conflict('此差异工艺未获当前路线预授权，或前置工艺尚未完成；请负责人发起转换')
    await new_pending(db,actor,box,target,trigger_type='pre_authorized',target_process=state.process_code)


async def confirm_conversion(db,actor,*,conversion_id,context_id,actual_qty,confirm,expected_version,conversion_version,
        idempotency_key,child_qr_payload=None):
    production.quantity(actual_qty)
    if confirm is not True or actual_qty<=0:
        production.conflict('请明确确认本次实际完成的正整数数量')
    await permissions.require_action(db,actor,'pool_read',lock=True)
    item=await db.get(m.ProductConversionRecord,conversion_id)
    if not item:raise QrError(404,'ENTITY_NOT_FOUND','转换记录不存在')
    context,target_state,target,assignment=await production.live_scope(db,actor,context_id)
    await permissions.require_action(db,actor,'conversion_confirm',order_id=item.order_id,
        order_product_id=item.target_order_product_id,context_id=context_id)
    async def operation():
        box=await db.get(m.ProductBox,item.product_box_id,populate_existing=True)
        initial=await current_quantity(db,box)
        source_ids=[initial.state_id] if initial else []
        allocation=await db.scalar(select(m.ProductOutputAllocation).where(m.ProductOutputAllocation.source_quantity_id==initial.source_quantity_id)) if initial else None
        await lock_rows(db,order_products=[item.source_order_product_id,item.target_order_product_id]+([allocation.order_product_id] if allocation else []))
        locked=await lock_rows(db,states=source_ids+[target_state.id],boxes=[box.id])
        box=locked['boxes'][box.id]
        record=await db.scalar(select(m.ProductConversionRecord).where(m.ProductConversionRecord.id==item.id)
            .with_for_update().execution_options(populate_existing=True))
        check_version(record.version,conversion_version,code='STATE_CONFLICT');check_version(box.version,expected_version)
        if (record.confirmation_status!='pending_operator_confirmation' or box.order_product_id!=record.source_order_product_id
                or box.current_process_code!=record.source_process_code or actual_qty>box.current_qty):
            production.conflict('转换或来源事实已变化，请重新核对')
        fresh,state,product,active_assignment=await production.live_scope(db,actor,context_id)
        source,route,part,customer,entry,common=await pair(db,box,product)
        codes=[s['code'] for s in route.steps_json]
        if (state.id!=target_state.id or product.id!=record.target_order_product_id
                or state.route_revision_id!=route.id or state.process_code!=record.target_process_code
                or await production.paused(db,state.id)):
            production.conflict('所选目标工艺与转换记录不匹配或已暂停')
        if record.trigger_type=='manual' and state.process_code!=entry:
            production.conflict('转换目标前置工艺不匹配')
        if record.trigger_type=='pre_authorized':
            # Recheck current authorization, including route versions, immediately before committing.
            auth=source.conversion_authorization.get('targets',[])
            if not any(a.get('target_order_product_id')==str(product.id) and a.get('source_route_revision_id')==str(box.route_revision_id)
                and a.get('target_route_revision_id')==str(route.id) and state.process_code in a.get('difference_process_codes',[])
                and a.get('authorized_by') and a.get('authorized_at') for a in auth):
                production.conflict('转换预授权已变化，请重新核对')
            if codes.index(state.process_code)!=len(common):production.conflict('目标前置工艺不完整')
        step=next(s for s in route.steps_json if s['code']==state.process_code)
        machine=await db.get(Machine,active_assignment.machine_id)
        if not machine or machine.is_deleted or (machine.id not in step.get('machine_ids',[]) and machine.machine_type not in step.get('machine_types',[])):
            production.conflict('目标机台不能执行该工艺')
        value,source_state,allocation=await source_facts(db,box)
        from app.services.coil_exception_service import ensure_material_decision
        await ensure_material_decision(db,state,box.order_id,value.material_batch_id)
        partial=actual_qty<box.current_qty
        if not partial and child_qr_payload:production.conflict('全量转换沿用原标签，请勿提供子标签')
        pool=await boxes.resolve_pool(db,child_qr_payload) if partial and child_qr_payload else None
        if partial and not pool:production.conflict('部分转换须核对池内未绑定子标签')
        more=await lock_rows(db,pool=[pool.id] if pool else [],allocations=[allocation.id])
        allocation=more['allocations'][allocation.id]
        if pool:
            pool=more['pool'][pool.id]
            if pool.pool_status!='unused':raise QrError(409,'QR_ALREADY_BOUND','子标签已被使用')
        now=await db.scalar(select(func.clock_timestamp()))
        snapshot=dict(box_no=box.box_no,order_id=box.order_id,order_product_id=str(box.order_product_id),
            product_name=box.product_name_snapshot,product_code=box.product_code,route_revision_id=str(box.route_revision_id),
            process_code=box.current_process_code,current_qty=box.current_qty,quantity_id=str(value.id),
            state_id=str(source_state.id),source_quantity_id=str(value.source_quantity_id),material_batch_id=value.material_batch_id,
            allocation_id=str(allocation.id),order_qty=allocation.order_qty,stock_qty=allocation.stock_qty)
        result_box=box
        if partial:
            result_box=m.ProductBox(qr_pool_item_id=pool.id,box_no=pool.public_code,order_id=box.order_id,
                order_product_id=product.id,part_id=product.part_id,product_code=product.product_code,
                product_name_snapshot=part.internal_name or '',customer_id=part.customer_id,customer_name_snapshot=customer,
                customer_part_no=part.customer_part_no,route_revision_id=route.id,current_qty=actual_qty,
                current_process_code=state.process_code,next_process_code=None,bound_by=actor.id,bound_at=now,updated_at=now)
            db.add(result_box);await db.flush()
            box.current_qty-=actual_qty;box.version+=1;box.updated_at=now
            value.current_qty=box.current_qty;value.version+=1;value.updated_by=actor.id;value.updated_at=now
            pool.pool_status='bound';pool.updated_at=now
        else:
            # The source row is a current balance, not another physical box.
            # Its original quantity remains in the immutable conversion snapshot.
            value.current_qty=0;value.version+=1;value.updated_by=actor.id;value.updated_at=now
            box.order_product_id=product.id;box.part_id=product.part_id;box.product_code=product.product_code
            box.product_name_snapshot=part.internal_name or '';box.customer_id=part.customer_id
            box.customer_name_snapshot=customer;box.customer_part_no=part.customer_part_no
            box.route_revision_id=route.id;box.version+=1;box.updated_at=now
        result_box.current_process_code=state.process_code
        position=codes.index(state.process_code)
        result_box.next_process_code=codes[position+1] if position+1<len(codes) else None
        entry_value=await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.box_id==result_box.id,
            m.BoxProcessQuantity.state_id==state.id))
        if entry_value is None:
            entry_value=m.BoxProcessQuantity(box_id=result_box.id,state_id=state.id,input_qty=actual_qty,current_qty=actual_qty,
                material_batch_id=value.material_batch_id,source_quantity_id=value.source_quantity_id if not partial else None,
                updated_by=actor.id,updated_at=now)
            db.add(entry_value);await db.flush()
        else:
            entry_value.current_qty=actual_qty;entry_value.updated_by=actor.id;entry_value.updated_at=now;entry_value.version+=1
        relation=None
        if partial:
            entry_value.source_quantity_id=entry_value.id
            order_qty=min(actual_qty,allocation.order_qty);stock_qty=actual_qty-order_qty
            allocation.available_qty-=actual_qty;allocation.order_qty-=order_qty;allocation.stock_qty-=stock_qty
            allocation.version+=1;allocation.manually_adjusted=True;allocation.assigned_by=actor.id;allocation.assigned_at=now
            db.add(m.ProductOutputAllocation(source_quantity_id=entry_value.id,box_id=result_box.id,order_id=box.order_id,
                order_product_id=allocation.order_product_id,origin_allocation_id=allocation.id,available_qty=actual_qty,
                order_qty=order_qty,stock_qty=stock_qty,remaining_order_qty_snapshot=allocation.remaining_order_qty_snapshot,
                manually_adjusted=True,assigned_by=actor.id,assigned_at=now))
            relation=m.ProductBoxRelation(parent_box_id=box.id,child_box_id=result_box.id,relation_type='partial_conversion',
                quantity=actual_qty,source_product_code=record.source_product_code,target_product_code=record.target_product_code,
                source_order_id=box.order_id,target_order_id=box.order_id,source_order_product_id=record.source_order_product_id,
                target_order_product_id=record.target_order_product_id,source_snapshot=snapshot,
                order_qty=order_qty,stock_qty=stock_qty,created_by=actor.id,created_at=now)
            db.add(relation);await db.flush();record.relation_id=relation.id
            await boxes.record_scan(db,actor.id,pool,ScanOperation.BIND)
        record.actual_qty=actual_qty;record.confirmed_by=actor.id;record.confirmed_at=now
        record.confirmation_status='confirmed';record.version+=1
        for changed in {source_state.id:source_state,state.id:state}.values():changed.version+=1
        state.production_status='in_progress'
        await db.execute(update(m.MachineProductionContext).where(m.MachineProductionContext.state_id.in_([source_state.id,state.id]),
            m.MachineProductionContext.closed_at.is_(None)).values(completion_scan_at=None))
        fresh.last_activity_at=now;fresh.expires_at=now+timedelta(minutes=30)
        for affected in {box.id:box,result_box.id:result_box}.values():
            db.add(m.ProductFlowEvent(product_box_id=affected.id,event_type='conversion',process_code=affected.current_process_code,
                order_id=box.order_id,order_product_id=affected.order_product_id,state_id=state.id,context_id=context_id,
                machine_id=assignment.machine_id,material_batch_id=value.material_batch_id,operator_id=actor.id,
                before_qty=snapshot['current_qty'] if affected.id==box.id else 0,after_qty=affected.current_qty,
                box_version=affected.version,before_snapshot=snapshot,
                after_snapshot=dict(conversion_id=str(record.id),entry_quantity_id=str(entry_value.id),actual_qty=actual_qty,
                    product_code=affected.product_code,source_product_code=record.source_product_code,target_product_code=record.target_product_code,
                    source_box_id=str(box.id),converted_box_id=str(result_box.id),relation_id=str(relation.id) if relation else None),occurred_at=now))
        await boxes.record_scan(db,actor.id,await db.get(m.ProductQrPoolItem,box.qr_pool_item_id),ScanOperation.CONVERSION)
        await db.flush()
        from app.services.product_split_service import relation_info
        result=dict(conversion=await record_info(db,actor,record),source_box=boxes.box_info(box,await db.get(m.ProductQrPoolItem,box.qr_pool_item_id)),
            converted_box=boxes.box_info(result_box,await db.get(m.ProductQrPoolItem,result_box.qr_pool_item_id)),
            relation=relation_info(relation,box,result_box) if relation else None)
        await write_audit(db,actor.id,AuditAction.UPDATE,f'conversion:{record.id}:confirmed',before=snapshot,after=result)
        return result
    return await transactional_write(db,actor.id,'conversion-confirm',f'conversion:{item.id}',idempotency_key,
        dict(context_id=str(context_id),actual_qty=actual_qty,confirm=confirm,child_qr_payload=child_qr_payload,
            expected_version=expected_version,conversion_version=conversion_version),operation)


async def cancel_conversion(db,actor,*,conversion_id,conversion_version,idempotency_key,context_id=None,reason=None):
    await permissions.require_action(db,actor,'pool_read',lock=True)
    item=await db.get(m.ProductConversionRecord,conversion_id)
    if not item:raise QrError(404,'ENTITY_NOT_FOUND','转换记录不存在')
    manager=await allowed(db,actor,'supervise',item.order_id)
    if not manager:
        await permissions.require_action(db,actor,'conversion_confirm',order_id=item.order_id,
            order_product_id=item.target_order_product_id,context_id=context_id)
    if reason is not None and (not isinstance(reason,str) or len(reason)>500):production.conflict('取消原因无效')
    async def operation():
        await lock_rows(db,order_products=[item.source_order_product_id,item.target_order_product_id],boxes=[item.product_box_id])
        record=await db.scalar(select(m.ProductConversionRecord).where(m.ProductConversionRecord.id==item.id)
            .with_for_update().execution_options(populate_existing=True))
        check_version(record.version,conversion_version,code='STATE_CONFLICT')
        if record.confirmation_status!='pending_operator_confirmation':production.conflict('仅待确认转换可取消')
        record.confirmation_status='cancelled';record.cancelled_by=actor.id
        record.cancelled_at=await db.scalar(select(func.clock_timestamp()));record.cancel_reason=reason;record.version+=1
        await db.flush();result=await record_info(db,actor,record)
        await write_audit(db,actor.id,AuditAction.UPDATE,f'conversion:{record.id}:cancelled',after=result)
        return result
    return await transactional_write(db,actor.id,'conversion-cancel',f'conversion:{item.id}',idempotency_key,
        dict(context_id=str(context_id) if context_id else None,conversion_version=conversion_version,reason=reason),operation)
