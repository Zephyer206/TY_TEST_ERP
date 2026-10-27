"""Machine-scoped production, overwrite quantities and effective output allocation."""
from datetime import datetime, timedelta
from types import SimpleNamespace
import hashlib
import re
import secrets

from sqlalchemy import func, select

from app.models import product_box as m
from app.models.audit import AuditAction
from app.models.machine import Machine
from app.models.part import Part
from app.models.production import PlanMachineAssignment, ProductionPlan
from app.models.warehouse import MaterialBatch
from app.services import product_box_service as boxes, qr_permission_service as permissions
from app.services.qr_transaction_service import (
    QrError, check_version, lock_rows, transactional_write, write_audit,
)


def conflict(message, details=None):
    raise QrError(409, "STATE_CONFLICT", message, details)


def quantity(value):
    if type(value) is not int or not 0 <= value <= 2_147_483_647:
        raise QrError(400, "INVALID_QUANTITY", "数量须为非负整数")
    return value


def context_info(context, state=None, assignment=None, product=None):
    return {"id": str(context.id), "machine_id": context.machine_id,
        "state_id": str(context.state_id) if context.state_id else None,
        "order_id": product.order_id if product else None,
        "order_product_id": str(product.id) if product else None,
        "assignment_id": assignment.id if assignment else None,
        "process_code": state.process_code if state else None,
        "expires_at": boxes.iso(context.expires_at), "closed_at": boxes.iso(context.closed_at),
        "completion_scan_at": boxes.iso(context.completion_scan_at)}


async def state_entities(db, state):
    product = await db.get(m.ProductOrderProduct, state.order_product_id)
    assignment = await db.get(PlanMachineAssignment, state.assignment_id)
    plan = await db.get(ProductionPlan, product.order_id) if product else None
    if not product or not assignment or not plan or assignment.plan_id != product.order_id:
        conflict("机台工艺关联配置不完整")
    return product, assignment, plan


async def live_scope(db, actor, context_id, *, allow_completed=False):
    context = await db.get(m.MachineProductionContext, context_id, populate_existing=True)
    now = await db.scalar(select(func.clock_timestamp()))
    if not context or context.user_id != actor.id or not context.state_id or context.expires_at <= now:
        raise QrError(403, "FORBIDDEN", "当前选单上下文已失效或不属于本人")
    state = await db.get(m.MachineOrderProcessState, context.state_id, populate_existing=True)
    if state is None:
        conflict("机台工艺不存在")
    product, assignment, plan = await state_entities(db, state)
    await permissions.require_action(db, actor, "trace", order_id=product.order_id)
    if (not assignment.is_active or assignment.machine_id != context.machine_id
            or str(plan.status).lower() in {"closed", "completed", "cancelled"}):
        conflict("订单或机台分配已关闭，请重新选单")
    if not allow_completed and (context.closed_at or state.production_status == "completed"):
        conflict("该机台工艺已完成，不能继续登记数量")
    return context, state, product, assignment


async def paused(db, state_id):
    return await db.scalar(select(m.CoilSpecException.id).where(m.CoilSpecException.state_id == state_id,
        m.CoilSpecException.released_at.is_(None), m.CoilSpecException.status == "confirmed",
        m.CoilSpecException.resolution.in_(["pause", "reconfirm_coil"])).limit(1)) is not None


async def downstream(db, source_id):
    if await db.scalar(select(m.BoxProcessQuantity.id).where(
            m.BoxProcessQuantity.source_quantity_id == source_id, m.BoxProcessQuantity.id != source_id).limit(1)):
        return True
    source = await db.get(m.BoxProcessQuantity, source_id)
    if not source:
        return False
    return await db.scalar(select(m.ProductFlowEvent.id).where(m.ProductFlowEvent.product_box_id == source.box_id,
        m.ProductFlowEvent.event_type.in_(["split", "cross_order_split", "conversion"]),
        m.ProductFlowEvent.occurred_at >= source.created_at).limit(1)) is not None


async def partitioned(db, box_id):
    return await db.scalar(select(m.ProductFlowEvent.id).where(m.ProductFlowEvent.product_box_id == box_id,
        m.ProductFlowEvent.event_type.in_(["split", "cross_order_split"])).limit(1)) is not None


def quantity_info(value):
    return {"id": str(value.id), "state_id": str(value.state_id), "box_id": str(value.box_id),
        "current_qty": value.current_qty, "input_qty": value.input_qty,
        "source_quantity_id": str(value.source_quantity_id) if value.source_quantity_id else None,
        "material_batch_id": value.material_batch_id,
        "version": value.version, "updated_by": value.updated_by, "updated_at": boxes.iso(value.updated_at)}


async def allocation_info(db, actor, allocation):
    has_downstream = await downstream(db, allocation.source_quantity_id)
    allowed = False
    if not has_downstream:
        try:
            await permissions.require_action(db, actor, "supervise", order_id=allocation.order_id)
            allowed = True
        except QrError:
            pass
    return {"id": str(allocation.id), "source_quantity_id": str(allocation.source_quantity_id),
        "origin_allocation_id": str(allocation.origin_allocation_id) if allocation.origin_allocation_id else None,
        "box_id": str(allocation.box_id), "order_id": allocation.order_id,
        "order_product_id": str(allocation.order_product_id), "available_qty": allocation.available_qty,
        "order_qty": allocation.order_qty, "stock_qty": allocation.stock_qty,
        "remaining_order_qty_snapshot": allocation.remaining_order_qty_snapshot,
        "manually_adjusted": allocation.manually_adjusted, "version": allocation.version,
        "has_downstream": has_downstream, "allowed_actions": ["allocate"] if allowed else []}


async def state_info(db, actor, state):
    product, assignment, plan = await state_entities(db, state)
    machine = await db.get(Machine, assignment.machine_id)
    part = await db.get(Part, product.part_id)
    route = await db.get(m.ProductRouteRevision, state.route_revision_id)
    caps = await permissions.capabilities(db, actor)
    values = (await db.execute(select(m.BoxProcessQuantity, m.ProductBox).join(m.ProductBox,
        m.ProductBox.id == m.BoxProcessQuantity.box_id).where(m.BoxProcessQuantity.state_id == state.id)
        .order_by(m.BoxProcessQuantity.id))).all()
    total = sum(value.current_qty for value, _ in values)
    blocked = await paused(db, state.id)
    actions = []
    if actor.dept == "prod" and "qr.production" in caps and state.production_status != "completed" and not blocked:
        actions.extend(["quantity", "complete"])
        if state.route_revision_id == product.route_revision_id:
            actions.append("bind")
    if actor.dept == "prod" and actor.role_level >= 2 and "qr.supervise" in caps and state.production_status == "completed":
        actions.append("correct")
    entries = []
    for value, box in values:
        was_partitioned = await partitioned(db, box.id)
        allocation = await db.scalar(select(m.ProductOutputAllocation).where(
            m.ProductOutputAllocation.source_quantity_id == value.source_quantity_id)) if value.source_quantity_id else None
        entries.append({**quantity_info(value), "quantity_id": str(value.id), "box_no": box.box_no,
            "box_version": box.version, "product_name": box.product_name_snapshot,
            "customer_part_no": box.customer_part_no,
            "allocation": await allocation_info(db, actor, allocation) if allocation else None,
            "can_correct": "correct" in actions and not (was_partitioned and value.source_quantity_id == value.id),
            "quantity_locked": was_partitioned and value.source_quantity_id == value.id})
    return {"id": str(state.id), "assignment_id": assignment.id, "machine_id": assignment.machine_id,
        "machine_no": machine.machine_no if machine else "", "machine_name": machine.name if machine else "",
        "order_id": product.order_id, "plan_no": f"PP-{plan.id:06d}", "part_id": product.part_id,
        "part_name": part.internal_name if part else "", "customer_part_no": part.customer_part_no if part else None,
        "order_product_id": str(product.id), "product_code": product.product_code,
        "route_revision_id": str(state.route_revision_id), "route_code": route.route_code if route else "",
        "route_revision": route.revision if route else 0, "process_code": state.process_code,
        "target_qty": state.target_qty, "current_qty": total, "difference_qty": total - state.target_qty,
        "production_status": state.production_status, "version": state.version,
        "completed_at": boxes.iso(state.completed_at), "completed_by": state.completed_by,
        "blocked": blocked, "allowed_actions": actions, "boxes": entries}


async def scan_machine(db, actor, *, machine_qr, context_id=None):
    await permissions.require_action(db, actor, "pool_read", lock=True)
    match = re.fullmatch(r"MCN:([1-9][0-9]{0,9}):([0-9]{8}(?:[0-9]{6})?)(?::machine_no=([^:\r\n]+))?", machine_qr or "")
    try:
        if not match or int(match[1]) > 2_147_483_647:
            raise ValueError()
        datetime.strptime(match[2], "%Y%m%d%H%M%S" if len(match[2]) == 14 else "%Y%m%d")
    except ValueError:
        raise QrError(400, "INVALID_QR", "机台标签格式无效") from None
    machine = await db.get(Machine, int(match[1]))
    if machine is None or machine.is_deleted:
        raise QrError(404, "ENTITY_NOT_FOUND", "机台不存在或已停用")
    if match[3] and match[3] != machine.machine_no:
        raise QrError(400, "INVALID_QR", "机台编号与标签不一致")
    now = await db.scalar(select(func.clock_timestamp()))
    caps = sorted(await permissions.capabilities(db, actor))
    result = {"machine": {"id": machine.id, "machine_no": machine.machine_no, "name": machine.name},
        "actor": {"id": actor.id, "dept": actor.dept, "role_level": actor.role_level},
        "capabilities": caps, "scan_ticket": None, "context": None, "state": None,
        "assignments": [], "completion_intent": False}
    if context_id is not None:
        context, state, product, assignment = await live_scope(db, actor, context_id)
        if context.machine_id != machine.id:
            conflict("请扫描当前选单对应的机台")
        await permissions.require_action(db, actor, "complete", order_id=product.order_id,
            order_product_id=product.id, context_id=context.id)
        await lock_rows(db, order_products=[product.id], states=[state.id])
        if await paused(db, state.id):
            conflict("当前机台工艺已暂停")
        context.completion_scan_at = now
        result.update(context=context_info(context, state, assignment, product),
            state=await state_info(db, actor, state), completion_intent=True)
        await db.flush()
        return result
    scope = await permissions.visible_order_clause(db, actor, m.ProductOrderProduct.order_id)
    states = (await db.scalars(select(m.MachineOrderProcessState)
        .join(PlanMachineAssignment, PlanMachineAssignment.id == m.MachineOrderProcessState.assignment_id)
        .join(m.ProductOrderProduct, m.ProductOrderProduct.id == m.MachineOrderProcessState.order_product_id)
        .join(ProductionPlan, ProductionPlan.id == m.ProductOrderProduct.order_id)
        .where(PlanMachineAssignment.machine_id == machine.id, PlanMachineAssignment.is_active.is_(True),
            ProductionPlan.status.notin_(["closed", "cancelled", "completed"]), scope)
        .order_by(m.MachineOrderProcessState.id))).all()
    for state in states:
        result["assignments"].append(await state_info(db, actor, state))
    ticket = secrets.token_urlsafe(32)
    db.add(m.MachineProductionContext(user_id=actor.id, machine_id=machine.id,
        scan_ticket_digest=hashlib.sha256(ticket.encode()).hexdigest(), scanned_at=now,
        last_activity_at=now, expires_at=now + timedelta(minutes=30)))
    await db.flush()
    result["scan_ticket"] = ticket
    return result


async def select_production(db, actor, *, scan_ticket, assignment_id, order_product_id, process_code, idempotency_key, state_id=None):
    await permissions.require_action(db, actor, "pool_read", lock=True)
    if not isinstance(scan_ticket, str) or not 20 <= len(scan_ticket) <= 120:
        raise QrError(403, "FORBIDDEN", "请重新扫描机台")
    digest = hashlib.sha256(scan_ticket.encode()).hexdigest()
    context = await db.scalar(select(m.MachineProductionContext).where(m.MachineProductionContext.scan_ticket_digest == digest))
    if context is None or context.user_id != actor.id:
        raise QrError(403, "FORBIDDEN", "机台票据不属于当前账号")
    product = await db.get(m.ProductOrderProduct, order_product_id)
    if product is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "实际产品不存在")
    await permissions.require_action(db, actor, "trace", order_id=product.order_id)

    async def operation():
        await lock_rows(db, order_products=[product.id])
        current = await db.scalar(select(m.MachineProductionContext).where(m.MachineProductionContext.id == context.id).with_for_update())
        now = await db.scalar(select(func.clock_timestamp()))
        if current.closed_at or current.expires_at <= now or current.state_id is not None:
            conflict("机台票据已使用或过期，请重新扫描")
        state = await db.scalar(select(m.MachineOrderProcessState).where(
            m.MachineOrderProcessState.assignment_id == assignment_id,
            m.MachineOrderProcessState.order_product_id == product.id,
            m.MachineOrderProcessState.process_code == process_code,
            (m.MachineOrderProcessState.id == state_id if state_id is not None else
                m.MachineOrderProcessState.route_revision_id == product.route_revision_id)))
        if state is None:
            conflict("机台订单工艺未配置")
        _, assignment, plan = await state_entities(db, state)
        if (not assignment.is_active or assignment.machine_id != current.machine_id
                or str(plan.status).lower() in {"closed", "cancelled", "completed"}):
            conflict("机台分配或订单已关闭")
        # Validate the explicitly selected published revision. Publishing a new
        # route must not strand boxes already bound to the old route/state.
        configuration_product = product if state.route_revision_id == product.route_revision_id else SimpleNamespace(
            id=product.id, order_id=product.order_id, part_id=product.part_id,
            product_code=product.product_code, binding_allowed=product.binding_allowed,
            target_qty=product.target_qty, route_revision_id=state.route_revision_id)
        await boxes.binding_configuration(db, configuration_product)
        route = await db.get(m.ProductRouteRevision, state.route_revision_id)
        step = next((step for step in route.steps_json if step.get("code") == process_code), None) if route else None
        machine = await db.get(Machine, current.machine_id)
        if (not route or not route.is_published or route.product_code != product.product_code or not step
                or not machine or machine.is_deleted or (machine.id not in step.get("machine_ids", [])
                    and machine.machine_type not in step.get("machine_types", []))):
            conflict("所选机台不能执行该版本工艺")
        current.state_id = state.id
        current.last_activity_at, current.expires_at = now, now + timedelta(minutes=30)
        await db.flush()
        return {"context": context_info(current, state, assignment, product), "state": await state_info(db, actor, state)}

    return await transactional_write(db, actor.id, "production-select", f"ticket:{digest}", idempotency_key,
        {"assignment_id": assignment_id, "order_product_id": str(order_product_id), "process_code": process_code,
         "state_id": str(state_id) if state_id is not None else None}, operation)


async def effective_allocation(db, actor, source, product, qty, now):
    allocation = await db.scalar(select(m.ProductOutputAllocation).where(m.ProductOutputAllocation.source_quantity_id == source.id))
    if allocation and await downstream(db, source.id):
        return allocation
    other_used = await db.scalar(select(func.coalesce(func.sum(m.ProductOutputAllocation.order_qty), 0)).where(
        m.ProductOutputAllocation.order_product_id == product.id,
        m.ProductOutputAllocation.source_quantity_id != source.id))
    remaining = max(0, product.target_qty - other_used)
    if allocation and allocation.manually_adjusted:
        if allocation.order_qty + allocation.stock_qty != qty or allocation.order_qty > remaining:
            conflict("当前数量与人工用途分配不一致，请授权人员核对后调整")
        return allocation
    if allocation is None:
        allocation = m.ProductOutputAllocation(source_quantity_id=source.id, box_id=source.box_id,
            order_id=product.order_id, order_product_id=product.id, assigned_by=actor.id,
            available_qty=qty, order_qty=min(qty, remaining), stock_qty=max(0, qty - remaining),
            remaining_order_qty_snapshot=remaining, manually_adjusted=False, version=1, assigned_at=now)
        db.add(allocation)
    else:
        allocation.available_qty, allocation.remaining_order_qty_snapshot = qty, remaining
        allocation.order_qty, allocation.stock_qty = min(qty, remaining), max(0, qty - remaining)
        allocation.assigned_by, allocation.assigned_at, allocation.version = actor.id, now, allocation.version + 1
    await db.flush()
    return allocation


async def quantity_result(db, actor, context, state, product, assignment, box, value):
    pool = await db.get(m.ProductQrPoolItem, box.qr_pool_item_id)
    allocation = await db.scalar(select(m.ProductOutputAllocation).where(
        m.ProductOutputAllocation.source_quantity_id == value.source_quantity_id)) if value.source_quantity_id else None
    return {"context": context_info(context, state, assignment, product) if context else None,
        "state": await state_info(db, actor, state), "box": boxes.box_info(box, pool),
        "quantity": quantity_info(value), "allocation": await allocation_info(db, actor, allocation) if allocation else None}


async def save_quantity(db, actor, *, box_id, context_id, current_qty, expected_version, state_version, idempotency_key, material_batch_id=None):
    quantity(current_qty)
    await permissions.require_action(db, actor, "pool_read", lock=True)
    context, state, product, assignment = await live_scope(db, actor, context_id)
    await permissions.require_action(db, actor, "quantity", order_id=product.order_id,
        order_product_id=product.id, context_id=context_id)

    async def operation():
        locked = await lock_rows(db, order_products=[product.id], states=[state.id], boxes=[box_id])
        current_state, box = locked["states"][state.id], locked["boxes"][box_id]
        fresh_context, _, _, _ = await live_scope(db, actor, context_id)
        if (box.order_product_id != product.id or box.order_id != product.order_id
                or box.route_revision_id != current_state.route_revision_id):
            raise QrError(400, "ORDER_MISMATCH", "当前框不属于所选订单产品工艺")
        if box.lifecycle_status not in {"active", "empty"} or await paused(db, current_state.id):
            conflict("当前框或机台工艺不能登记数量")
        check_version(box.version, expected_version)
        check_version(current_state.version, state_version, code="STATE_CONFLICT")
        route = await db.get(m.ProductRouteRevision, box.route_revision_id)
        if not route or not route.is_published or (box.current_process_code or route.steps_json[0]["code"]) != state.process_code:
            conflict("请先按固定路线进入当前工艺")
        value = await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.state_id == state.id,
            m.BoxProcessQuantity.box_id == box.id))
        latest = await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.box_id == box.id)
            .order_by(m.BoxProcessQuantity.id.desc()).limit(1))
        if latest and latest.state_id != state.id:
            conflict("该框已属于其他机台工艺，请按固定路线流转后登记")
        if value and value.source_quantity_id == value.id and await partitioned(db, box.id):
            conflict("该来源已经拆分，不能重新登记拆分前数量；余量可继续流转或拆框")
        if material_batch_id is not None:
            if (type(material_batch_id) is not int or not 0 < material_batch_id <= 2_147_483_647
                    or await db.get(MaterialBatch, material_batch_id) is None):
                raise QrError(400, "INVALID_MATERIAL", "原材料批次不存在")
            if value and value.material_batch_id != material_batch_id:
                conflict("既有工艺材料来源不可替换，请核对实物及历史记录")
        now = await db.scalar(select(func.clock_timestamp()))
        before = box.current_qty
        if value is None:
            value = m.BoxProcessQuantity(state_id=state.id, box_id=box.id, input_qty=before,
                current_qty=current_qty, material_batch_id=material_batch_id, updated_by=actor.id, updated_at=now, version=1)
            db.add(value)
            await db.flush()
        else:
            value.current_qty, value.version, value.updated_by, value.updated_at = current_qty, value.version + 1, actor.id, now
        if state.process_code == route.first_output_process_code:
            value.source_quantity_id = value.id
            await effective_allocation(db, actor, value, locked["order_products"][product.id], current_qty, now)
        box.current_qty, box.current_process_code = current_qty, state.process_code
        codes = [step["code"] for step in route.steps_json]
        index = codes.index(state.process_code)
        box.next_process_code = codes[index + 1] if index + 1 < len(codes) else None
        box.version, box.updated_at = box.version + 1, now
        current_state.production_status, current_state.version = "in_progress", current_state.version + 1
        fresh_context.completion_scan_at = None
        fresh_context.last_activity_at, fresh_context.expires_at = now, now + timedelta(minutes=30)
        db.add(m.ProductFlowEvent(product_box_id=box.id, event_type="qty_save", process_code=state.process_code,
            machine_id=assignment.machine_id, order_id=product.order_id, order_product_id=product.id,
            state_id=state.id, context_id=context.id, operator_id=actor.id, before_qty=before,
            material_batch_id=value.material_batch_id,
            after_qty=current_qty, box_version=box.version, before_snapshot={"current_qty": before},
            after_snapshot={"current_qty": current_qty}, occurred_at=now))
        await db.flush()
        result = await quantity_result(db, actor, fresh_context, current_state, product, assignment, box, value)
        await write_audit(db, actor.id, AuditAction.UPDATE, f"quantity:{value.id}",
            before={"current_qty": before}, after=result)
        return result

    return await transactional_write(db, actor.id, "quantity", f"box:{box_id}", idempotency_key,
        dict(context_id=str(context_id), current_qty=current_qty, expected_version=expected_version, state_version=state_version,
            **({"material_batch_id": material_batch_id} if material_batch_id is not None else {})), operation)


async def complete_production(db, actor, *, machine_id, context_id, confirm_quantity_difference, expected_version, idempotency_key):
    await permissions.require_action(db, actor, "pool_read", lock=True)
    context, state, product, assignment = await live_scope(db, actor, context_id, allow_completed=True)
    caps = await permissions.capabilities(db, actor)
    if actor.dept != "prod" or "qr.production" not in caps:
        raise QrError(403, "FORBIDDEN", "当前账号不能确认生产完成")
    if assignment.machine_id != machine_id:
        conflict("机台与当前选单不一致")

    async def operation():
        locked = await lock_rows(db, order_products=[product.id], states=[state.id])
        current = locked["states"][state.id]
        fresh, _, _, _ = await live_scope(db, actor, context_id)
        check_version(current.version, expected_version, code="STATE_CONFLICT")
        if not fresh.completion_scan_at or fresh.completion_scan_at < fresh.last_activity_at or await paused(db, current.id):
            conflict("请重新扫描当前机台，再确认本次完成")
        summary = await state_info(db, actor, current)
        if summary["difference_qty"] != 0 and confirm_quantity_difference is not True:
            conflict("实际数量与本机台目标不同，请核对后明确确认", {"confirmation_required": True,
                "target_qty": summary["target_qty"], "current_qty": summary["current_qty"]})
        now = await db.scalar(select(func.clock_timestamp()))
        current.production_status, current.completed_by, current.completed_at = "completed", actor.id, now
        current.quantity_difference_confirmed, current.version = summary["difference_qty"] != 0, current.version + 1
        fresh.closed_at = now
        for row in summary["boxes"]:
            db.add(m.ProductFlowEvent(product_box_id=int(row["box_id"]), event_type="process_complete",
                process_code=current.process_code, machine_id=machine_id, order_id=product.order_id,
                order_product_id=product.id, state_id=current.id, context_id=context.id, operator_id=actor.id,
                before_qty=row["current_qty"], after_qty=row["current_qty"], box_version=row["box_version"],
                after_snapshot={"target_qty": current.target_qty, "actual_total": summary["current_qty"]}, occurred_at=now))
        await db.flush()
        result = {"context": context_info(fresh, current, assignment, product), "state": await state_info(db, actor, current)}
        await write_audit(db, actor.id, AuditAction.UPDATE, f"production-complete:{current.id}", after=result)
        return result

    return await transactional_write(db, actor.id, "production-complete", f"context:{context_id}", idempotency_key,
        dict(machine_id=machine_id, confirm_quantity_difference=confirm_quantity_difference, expected_version=expected_version), operation)


async def allocate_output(db, actor, *, source_quantity_id, order_qty, stock_qty, expected_version, idempotency_key):
    quantity(order_qty), quantity(stock_qty)
    await permissions.require_action(db, actor, "pool_read", lock=True)
    allocation = await db.scalar(select(m.ProductOutputAllocation).where(m.ProductOutputAllocation.source_quantity_id == source_quantity_id))
    if allocation is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "有效产出分配不存在")
    await permissions.require_action(db, actor, "supervise", order_id=allocation.order_id)

    async def operation():
        locked = await lock_rows(db, order_products=[allocation.order_product_id], allocations=[allocation.id])
        current = locked["allocations"][allocation.id]
        check_version(current.version, expected_version, code="STATE_CONFLICT")
        if await downstream(db, source_quantity_id):
            conflict("来源已有下游事实，不能直接改写用途")
        other_used = await db.scalar(select(func.coalesce(func.sum(m.ProductOutputAllocation.order_qty), 0)).where(
            m.ProductOutputAllocation.order_product_id == current.order_product_id, m.ProductOutputAllocation.id != current.id))
        remaining = max(0, locked["order_products"][current.order_product_id].target_qty - other_used)
        if order_qty + stock_qty != current.available_qty or order_qty > remaining:
            conflict("分配合计须等于有效数量，且订单量不能超过剩余需求")
        current.order_qty, current.stock_qty, current.manually_adjusted = order_qty, stock_qty, True
        current.assigned_by, current.assigned_at, current.version = actor.id, await db.scalar(select(func.clock_timestamp())), current.version + 1
        await db.flush()
        result = await allocation_info(db, actor, current)
        box = await db.get(m.ProductBox, current.box_id)
        db.add(m.ProductFlowEvent(product_box_id=box.id, event_type="allocation", order_id=current.order_id,
            order_product_id=current.order_product_id, operator_id=actor.id, before_qty=box.current_qty,
            after_qty=box.current_qty, box_version=box.version, after_snapshot=result))
        await write_audit(db, actor.id, AuditAction.UPDATE, f"output-allocation:{current.id}", after=result)
        return result

    return await transactional_write(db, actor.id, "allocate-output", f"source:{source_quantity_id}", idempotency_key,
        dict(order_qty=order_qty, stock_qty=stock_qty, expected_version=expected_version), operation)


async def correct_quantity(db, actor, *, box_id, state_id, current_qty, reason, expected_version, state_version, idempotency_key):
    quantity(current_qty)
    await permissions.require_action(db, actor, "pool_read", lock=True)
    if actor.dept != "prod" or actor.role_level < 2 or "qr.supervise" not in await permissions.capabilities(db, actor):
        raise QrError(403, "FORBIDDEN", "仅生产主管可更正已完成工艺数量")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        conflict("请填写有效更正原因")
    state = await db.get(m.MachineOrderProcessState, state_id)
    if state is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "历史工艺不存在")
    product, assignment, _ = await state_entities(db, state)
    await permissions.require_action(db, actor, "supervise", order_id=product.order_id)

    async def operation():
        locked = await lock_rows(db, order_products=[product.id], states=[state.id], boxes=[box_id])
        current, box = locked["states"][state.id], locked["boxes"][box_id]
        check_version(box.version, expected_version)
        check_version(current.version, state_version, code="STATE_CONFLICT")
        if current.production_status != "completed" or box.order_product_id != product.id or box.route_revision_id != current.route_revision_id:
            conflict("只可更正该框已完成的历史工艺")
        value = await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.state_id == state.id, m.BoxProcessQuantity.box_id == box.id))
        if value is None:
            conflict("该框没有对应工艺数量")
        if value.source_quantity_id == value.id and await partitioned(db, box.id):
            conflict("该框已拆分，不能直接更正拆分前数量；请保留既有余量与用途事实")
        before, now = value.current_qty, await db.scalar(select(func.clock_timestamp()))
        latest_quantity_id = await db.scalar(select(m.BoxProcessQuantity.id).where(m.BoxProcessQuantity.box_id == box.id)
            .order_by(m.BoxProcessQuantity.id.desc()).limit(1))
        has_downstream = latest_quantity_id != value.id
        value.current_qty, value.updated_by, value.updated_at, value.version = current_qty, actor.id, now, value.version + 1
        if not has_downstream:
            if value.source_quantity_id == value.id:
                await effective_allocation(db, actor, value, locked["order_products"][product.id], current_qty, now)
            if box.current_process_code == current.process_code:
                box.current_qty = current_qty
        box.version, box.updated_at, current.version = box.version + 1, now, current.version + 1
        db.add(m.ProductFlowEvent(product_box_id=box.id, event_type="quantity_correction", process_code=current.process_code,
            machine_id=assignment.machine_id, order_id=product.order_id, order_product_id=product.id,
            state_id=current.id, operator_id=actor.id, before_qty=before, after_qty=current_qty,
            box_version=box.version, before_snapshot={"quantity": before}, after_snapshot={"quantity": current_qty}, remark=reason.strip(), occurred_at=now))
        await db.flush()
        result = await quantity_result(db, actor, None, current, product, assignment, box, value)
        await write_audit(db, actor.id, AuditAction.UPDATE, f"quantity-correction:{value.id}", before={"current_qty": before}, after=result)
        return result

    return await transactional_write(db, actor.id, "quantity-correction", f"box:{box_id}", idempotency_key,
        dict(state_id=str(state_id), current_qty=current_qty, reason=reason, expected_version=expected_version, state_version=state_version), operation)
