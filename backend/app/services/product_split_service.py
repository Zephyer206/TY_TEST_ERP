"""Atomic partition of physical quantity, output uses and stable QR identities."""
from sqlalchemy import func, or_, select, update

from app.models import product_box as m
from app.models.audit import AuditAction
from app.models.machine import Machine
from app.models.part import Part
from app.models.production import ProductionPlan, PlanMachineAssignment
from app.models.warehouse import ScanOperation
from app.services import product_box_service as boxes, product_production_service as production
from app.services import qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, lock_rows, transactional_write, write_audit


async def source_partition(db, box):
    if box.lifecycle_status != "active" or box.current_qty <= 0:
        production.conflict("该框没有可拆分的有效余量")
    plan = await db.get(ProductionPlan, box.order_id)
    if not plan or str(plan.status).lower() in {"closed", "completed", "cancelled"}:
        production.conflict("来源订单已经关闭")
    quantity = await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.box_id == box.id)
        .order_by(m.BoxProcessQuantity.id.desc()).limit(1))
    if not quantity or quantity.source_quantity_id != quantity.id or quantity.current_qty != box.current_qty:
        production.conflict("来源尚未建立，或已进入下游工艺，不能直接拆分旧产出")
    state = await db.get(m.MachineOrderProcessState, quantity.state_id)
    route = await db.get(m.ProductRouteRevision, box.route_revision_id)
    if (not state or state.order_product_id != box.order_product_id or state.route_revision_id != box.route_revision_id
            or not route or not route.is_published or route.first_output_process_code != box.current_process_code
            or state.process_code != box.current_process_code or await production.paused(db, state.id)):
        production.conflict("当前来源工艺配置或暂停状态不允许拆框")
    if await db.scalar(select(m.BoxProcessQuantity.id).where(m.BoxProcessQuantity.source_quantity_id == quantity.id,
            m.BoxProcessQuantity.id != quantity.id).limit(1)):
        production.conflict("来源已有下游数量，不允许改写旧产出余额")
    if await db.scalar(select(m.ProductFlowEvent.id).where(m.ProductFlowEvent.product_box_id == box.id,
            m.ProductFlowEvent.event_type == "conversion").limit(1)):
        production.conflict("来源已有转换事实，不允许直接拆分旧产出")
    allocation = await db.scalar(select(m.ProductOutputAllocation).where(m.ProductOutputAllocation.source_quantity_id == quantity.id))
    if not allocation or allocation.available_qty != box.current_qty:
        production.conflict("来源数量与用途余额不一致，请先核对历史记录")
    return quantity, state, route, allocation


async def permitted(db, actor, action, order_id):
    try:
        await permissions.require_action(db, actor, action, order_id=order_id)
        return True
    except QrError:
        return False


async def split_options(db, actor, box, *, page=1, page_size=50):
    same = await permitted(db, actor, "split", box.order_id)
    cross = await permitted(db, actor, "supervise", box.order_id)
    result = {"allowed_actions": [], "reason": None, "available_qty": box.current_qty,
        "order_qty": 0, "stock_qty": 0, "allocation_version": None,
        "targets": [], "targets_total": 0, "page": page, "page_size": page_size}
    if not (same or cross):
        return result
    try:
        _, state, route, allocation = await source_partition(db, box)
    except QrError as error:
        result["reason"] = error.message
        return result
    result.update(allowed_actions=(["split"] if same else []) + (["cross_order_split"] if cross else []),
        order_qty=allocation.order_qty, stock_qty=allocation.stock_qty, allocation_version=allocation.version)
    if not cross:
        return result
    scope = await permissions.visible_order_clause(db, actor, m.ProductOrderProduct.order_id)
    used = select(m.ProductOutputAllocation.order_product_id.label("product_id"),
        func.sum(m.ProductOutputAllocation.order_qty).label("used")).group_by(m.ProductOutputAllocation.order_product_id).subquery()
    remaining = m.ProductOrderProduct.target_qty - func.coalesce(used.c.used, 0)
    query = select(m.ProductOrderProduct, m.MachineOrderProcessState, Machine.machine_no, remaining.label("remaining"))
    query = query.join(m.MachineOrderProcessState, m.MachineOrderProcessState.order_product_id == m.ProductOrderProduct.id
        ).join(PlanMachineAssignment, PlanMachineAssignment.id == m.MachineOrderProcessState.assignment_id
        ).join(Machine, Machine.id == PlanMachineAssignment.machine_id).join(ProductionPlan,
        ProductionPlan.id == m.ProductOrderProduct.order_id).join(m.ProductRouteRevision,
        m.ProductRouteRevision.id == m.ProductOrderProduct.route_revision_id).outerjoin(used, used.c.product_id == m.ProductOrderProduct.id
        ).where(scope, m.ProductOrderProduct.order_id != box.order_id, m.ProductOrderProduct.part_id == box.part_id,
            m.ProductOrderProduct.product_code == box.product_code, m.ProductOrderProduct.binding_allowed.is_(True),
            m.MachineOrderProcessState.route_revision_id == m.ProductOrderProduct.route_revision_id,
            m.MachineOrderProcessState.process_code == state.process_code,
            m.MachineOrderProcessState.production_status != "completed", PlanMachineAssignment.is_active.is_(True),
            PlanMachineAssignment.plan_id == m.ProductOrderProduct.order_id, Machine.is_deleted.is_(False),
            ProductionPlan.status.notin_(["closed", "completed", "cancelled"]), remaining > 0,
            m.ProductRouteRevision.is_published.is_(True), m.ProductRouteRevision.steps_json == route.steps_json,
            m.ProductRouteRevision.first_output_process_code == route.first_output_process_code)
    result["targets_total"] = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await db.execute(query.order_by(m.ProductOrderProduct.id, m.MachineOrderProcessState.id)
        .offset((page - 1) * page_size).limit(page_size))).all()
    part = (await db.execute(select(Part.internal_name, Part.customer_part_no).where(Part.id == box.part_id))).one()
    result["targets"] = [{"order_product_id": str(product.id), "state_id": str(target.id), "state_version": target.version,
        "order_id": product.order_id, "plan_no": f"PP-{product.order_id:06d}", "product_name": part.internal_name,
        "customer_part_no": part.customer_part_no, "process_code": target.process_code, "machine_no": machine,
        "remaining_qty": int(remaining)} for product, target, machine, remaining in rows]
    return result


def relation_info(relation, parent, child):
    return {"id": str(relation.id), "relation_type": relation.relation_type, "parent_box_id": str(parent.id),
        "child_box_id": str(child.id), "source_order_id": parent.order_id, "target_order_id": child.order_id,
        "quantity": relation.quantity, "order_qty": relation.order_qty, "stock_qty": relation.stock_qty,
        "created_by": relation.created_by, "created_at": boxes.iso(relation.created_at),
        "source_snapshot": relation.source_snapshot, "parent_box_no": parent.box_no, "child_box_no": child.box_no,
        "parent_current_qty": parent.current_qty, "child_current_qty": child.current_qty}


async def split_box(db, actor, *, parent_id, child_qr_payload, quantity, order_qty, stock_qty,
                    expected_version, allocation_version, idempotency_key, target_order_product_id=None,
                    target_state_id=None, target_state_version=None):
    if type(quantity) is not int or not 0 < quantity <= 2_147_483_647:
        raise QrError(400, "INVALID_QUANTITY", "拆出数量须为正整数")
    production.quantity(order_qty), production.quantity(stock_qty)
    await permissions.require_action(db, actor, "pool_read", lock=True)
    parent = await db.get(m.ProductBox, parent_id, populate_existing=True)
    if parent is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "来源产品框不存在")
    cross = target_order_product_id is not None and target_order_product_id != parent.order_product_id
    await permissions.require_action(db, actor, "supervise" if cross else "split", order_id=parent.order_id)
    target_id = target_order_product_id if cross else parent.order_product_id
    target_product = await db.get(m.ProductOrderProduct, target_id)
    if not target_product:
        raise QrError(404, "ENTITY_NOT_FOUND", "目标产品配置不存在")
    if cross:
        await permissions.require_action(db, actor, "trace", order_id=target_product.order_id)
        if target_product.order_id == parent.order_id or not target_state_id or target_state_version is None:
            production.conflict("跨单拆框须明确选择另一订单的接收工艺")
    elif target_state_id is not None or target_state_version is not None:
        production.conflict("同单拆框继承来源工艺，不能另选机台")

    async def operation():
        products = (await lock_rows(db, order_products=[parent.order_product_id, target_id]))["order_products"]
        source_quantity, source_state, source_route, source_allocation = await source_partition(db, parent)
        state_ids = [source_state.id] + ([target_state_id] if cross else [])
        locked = await lock_rows(db, states=state_ids, boxes=[parent_id])
        current = locked["boxes"][parent_id]
        check_version(current.version, expected_version)
        source_quantity, source_state, source_route, source_allocation = await source_partition(db, current)
        child_pool = await boxes.resolve_pool(db, child_qr_payload)
        locked_more = await lock_rows(db, pool=[child_pool.id], allocations=[source_allocation.id])
        child_pool, source_allocation = locked_more["pool"][child_pool.id], locked_more["allocations"][source_allocation.id]
        check_version(source_allocation.version, allocation_version, code="STATE_CONFLICT")
        if child_pool.pool_status != "unused" or child_pool.id == current.qr_pool_item_id:
            raise QrError(409, "QR_ALREADY_BOUND", "子框必须使用池内未绑定标签")
        if (quantity > current.current_qty or order_qty + stock_qty != quantity
                or order_qty > source_allocation.order_qty or stock_qty > source_allocation.stock_qty):
            production.conflict("拆出数量与用途须守恒，且不能超过父框对应余额")
        target = products[target_id]
        receiving_state, receiving_route = source_state, source_route
        label_part, label_customer = None, None
        if cross:
            receiving_route, label_part, label_customer = await boxes.binding_configuration(db, target)
            receiving_state = locked["states"][target_state_id]
            check_version(receiving_state.version, target_state_version, code="STATE_CONFLICT")
            assignment = await db.get(PlanMachineAssignment, receiving_state.assignment_id)
            machine = await db.get(Machine, assignment.machine_id) if assignment else None
            if (target.part_id != current.part_id or target.product_code != current.product_code
                    or receiving_route.steps_json != source_route.steps_json
                    or receiving_route.first_output_process_code != source_route.first_output_process_code
                    or receiving_state.order_product_id != target.id or receiving_state.route_revision_id != receiving_route.id
                    or receiving_state.process_code != current.current_process_code or receiving_state.production_status == "completed"
                    or not assignment or assignment.plan_id != target.order_id or not assignment.is_active
                    or not machine or machine.is_deleted or await production.paused(db, receiving_state.id)):
                production.conflict("目标订单产品、路线或接收机台工艺不兼容")
            step = next(step for step in receiving_route.steps_json if step["code"] == receiving_state.process_code)
            if machine.id not in step.get("machine_ids", []) and machine.machine_type not in step.get("machine_types", []):
                production.conflict("目标接收机台不在该工艺允许范围内")
            used = await db.scalar(select(func.coalesce(func.sum(m.ProductOutputAllocation.order_qty), 0)).where(
                m.ProductOutputAllocation.order_product_id == target.id))
            if quantity > max(0, target.target_qty - used):
                production.conflict("目标订单剩余需求不足，整笔拆分未保存")
        before, now = current.current_qty, await db.scalar(select(func.clock_timestamp()))
        source_snapshot = {"box_no": current.box_no, "order_id": current.order_id, "order_product_id": str(current.order_product_id),
            "product_name": current.product_name_snapshot, "current_qty": before, "process_code": current.current_process_code,
            "route_revision_id": str(current.route_revision_id), "source_quantity_id": str(source_quantity.id),
            "source_allocation_id": str(source_allocation.id), "material_batch_id": source_quantity.material_batch_id,
            "order_qty": source_allocation.order_qty, "stock_qty": source_allocation.stock_qty,
            "source_state_id": str(source_state.id), "receiving_state_id": str(receiving_state.id)}
        child = m.ProductBox(qr_pool_item_id=child_pool.id, box_no=child_pool.public_code,
            order_id=target.order_id, order_product_id=target.id, part_id=target.part_id, product_code=target.product_code,
            product_name_snapshot=(label_part.internal_name or "") if cross else current.product_name_snapshot,
            customer_id=label_part.customer_id if cross else current.customer_id,
            customer_name_snapshot=label_customer if cross else current.customer_name_snapshot,
            customer_part_no=label_part.customer_part_no if cross else current.customer_part_no,
            route_revision_id=receiving_route.id, current_process_code=current.current_process_code,
            next_process_code=current.next_process_code, current_qty=quantity, version=1, lifecycle_status="active",
            bound_by=actor.id, bound_at=now, created_at=now, updated_at=now)
        db.add(child)
        await db.flush()
        if cross:
            codes = [step["code"] for step in receiving_route.steps_json]
            position = codes.index(child.current_process_code)
            child.next_process_code = codes[position + 1] if position + 1 < len(codes) else None
        child_quantity = m.BoxProcessQuantity(state_id=receiving_state.id, box_id=child.id, input_qty=quantity,
            current_qty=quantity, material_batch_id=source_quantity.material_batch_id, updated_by=actor.id, updated_at=now)
        db.add(child_quantity)
        await db.flush()
        child_quantity.source_quantity_id = child_quantity.id
        current.current_qty, current.version, current.updated_at = before - quantity, current.version + 1, now
        current.lifecycle_status = "active" if current.current_qty else "empty"
        source_quantity.current_qty, source_quantity.version = current.current_qty, source_quantity.version + 1
        source_quantity.updated_by, source_quantity.updated_at = actor.id, now
        source_allocation.available_qty -= quantity
        source_allocation.order_qty -= order_qty
        source_allocation.stock_qty -= stock_qty
        source_allocation.version += 1
        source_allocation.manually_adjusted, source_allocation.assigned_by, source_allocation.assigned_at = True, actor.id, now
        child_allocation = m.ProductOutputAllocation(source_quantity_id=child_quantity.id, box_id=child.id,
            order_id=target.order_id, order_product_id=target.id, origin_allocation_id=source_allocation.id,
            available_qty=quantity, order_qty=quantity if cross else order_qty, stock_qty=0 if cross else stock_qty,
            remaining_order_qty_snapshot=0, manually_adjusted=True, assigned_by=actor.id, assigned_at=now)
        db.add(child_allocation)
        for state in {source_state.id: source_state, receiving_state.id: receiving_state}.values():
            state.version += 1
        if cross and receiving_state.production_status == "pending":
            receiving_state.production_status = "in_progress"
        await db.execute(update(m.MachineProductionContext).where(m.MachineProductionContext.state_id.in_(state_ids),
            m.MachineProductionContext.closed_at.is_(None)).values(completion_scan_at=None))
        child_pool.pool_status, child_pool.updated_at = "bound", now
        relation = m.ProductBoxRelation(parent_box_id=current.id, child_box_id=child.id,
            relation_type="cross_order_split" if cross else "split", quantity=quantity,
            source_product_code=current.product_code, target_product_code=child.product_code,
            source_order_id=current.order_id, target_order_id=child.order_id,
            source_order_product_id=current.order_product_id, target_order_product_id=child.order_product_id,
            source_snapshot=source_snapshot, order_qty=order_qty, stock_qty=stock_qty, created_by=actor.id, created_at=now)
        db.add(relation)
        await db.flush()
        for allocation in (source_allocation, child_allocation):
            other = await db.scalar(select(func.coalesce(func.sum(m.ProductOutputAllocation.order_qty), 0)).where(
                m.ProductOutputAllocation.order_product_id == allocation.order_product_id,
                m.ProductOutputAllocation.id != allocation.id))
            allocation.remaining_order_qty_snapshot = max(0, products[allocation.order_product_id].target_qty - other)
        source_assignment = await db.get(PlanMachineAssignment, source_state.assignment_id)
        event_type = relation.relation_type
        for box, old_qty, new_qty, state in ((current, before, current.current_qty, source_state), (child, 0, quantity, receiving_state)):
            db.add(m.ProductFlowEvent(product_box_id=box.id, event_type=event_type, process_code=box.current_process_code,
                machine_id=source_assignment.machine_id, order_id=box.order_id, order_product_id=box.order_product_id,
                state_id=state.id, material_batch_id=source_quantity.material_batch_id, operator_id=actor.id,
                before_qty=old_qty, after_qty=new_qty, box_version=box.version,
                before_snapshot=source_snapshot, after_snapshot={"relation_id": str(relation.id), "parent_box_id": str(current.id),
                    "child_box_id": str(child.id), "quantity": quantity, "order_qty": order_qty, "stock_qty": stock_qty,
                    "current_qty": new_qty, "origin_allocation_id": str(source_allocation.id)}, occurred_at=now))
        await boxes.record_scan(db, actor.id, child_pool, ScanOperation.BIND)
        await boxes.record_scan(db, actor.id, await db.get(m.ProductQrPoolItem, current.qr_pool_item_id), ScanOperation.SPLIT)
        await db.flush()
        result = {"parent": boxes.box_info(current, await db.get(m.ProductQrPoolItem, current.qr_pool_item_id)),
            "child": boxes.box_info(child, child_pool), "relation": relation_info(relation, current, child),
            "parent_allocation": await production.allocation_info(db, actor, source_allocation),
            "child_allocation": await production.allocation_info(db, actor, child_allocation)}
        await write_audit(db, actor.id, AuditAction.UPDATE, f"split:{parent_id}:{relation.id}", before=source_snapshot, after=result)
        return result

    return await transactional_write(db, actor.id, "split", f"parent:{parent_id}", idempotency_key,
        dict(child_qr_payload=child_qr_payload, quantity=quantity, order_qty=order_qty, stock_qty=stock_qty,
            expected_version=expected_version, allocation_version=allocation_version,
            target_order_product_id=str(target_id) if cross else None,
            target_state_id=str(target_state_id) if cross else None, target_state_version=target_state_version), operation, http_status=201)
