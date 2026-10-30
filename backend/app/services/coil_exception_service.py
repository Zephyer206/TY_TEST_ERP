"""Server-owned coil comparisons and independent, state-scoped decisions."""
from decimal import Decimal, InvalidOperation
import hashlib
import json

from sqlalchemy import func, select, update

from app.models import product_box as m
from app.models.audit import AuditAction
from app.models.part import Part
from app.models.production import ProductionPlan
from app.models.warehouse import Material, MaterialBatch
from app.services import product_box_service as boxes, product_production_service as production
from app.services import qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, lock_rows, transactional_write, write_audit


def dimension(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0:
            raise ValueError()
        whole, _, fraction = format(number.normalize(), "f").partition(".")
        return whole + "." + fraction.ljust(3, "0")
    except (ValueError, InvalidOperation):
        production.conflict("订单或实际卷料缺少有效厚度、宽度，请先补齐规格配置")


def snapshot_spec(value):
    value = value if isinstance(value, dict) else {}
    name = value.get("material_name")
    result = {"material_name": name.strip() if isinstance(name, str) and name.strip() else None}
    for key in ("thickness", "width"):
        try:
            result[key] = dimension(value.get(key))
        except QrError:
            result[key] = None
    return result


async def comparison(db, order_id, material_batch_id, *, expected=None):
    plan = await db.get(ProductionPlan, order_id, populate_existing=True)
    batch = await db.get(MaterialBatch, material_batch_id, populate_existing=True)
    material = await db.get(Material, batch.material_id) if batch else None
    if not plan or not batch or not material:
        raise QrError(404, "ENTITY_NOT_FOUND", "订单或原材料批次不存在")
    if expected is None:
        name = (plan.material_name_snapshot or "").strip()
        if not name:
            production.conflict("订单缺少用料名称快照，请先补齐规格配置")
        expected = {"material_name": name, "thickness": dimension(plan.twp_thickness), "width": dimension(plan.twp_width)}
    else:
        expected = snapshot_spec(expected)
        if any(value is None for value in expected.values()):
            production.conflict("原异常规格快照不完整，不能据此解除暂停")
    if not isinstance(material.name, str) or not material.name.strip():
        production.conflict("实际卷料缺少用料名称，不能判为规格匹配")
    actual = {"material_name": material.name.strip(), "thickness": dimension(batch.thickness), "width": dimension(batch.width)}
    matches = all(expected[key].strip().casefold() == actual[key].strip().casefold() for key in expected)
    return expected, actual, matches


def dedupe(state_id, batch_id, expected, actual):
    content = json.dumps([str(state_id), batch_id, expected, actual], sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()


async def can_decide(db, actor, order_id):
    try:
        await permissions.require_action(db, actor, "supervise", order_id=order_id)
        return True
    except QrError:
        return False


async def exception_info(db, actor, item):
    state = await db.get(m.MachineOrderProcessState, item.state_id)
    product = await db.get(m.ProductOrderProduct, state.order_product_id)
    part = await db.get(Part, product.part_id)
    batch = await db.get(MaterialBatch, item.material_batch_id)
    groups = (await db.scalars(select(m.ExceptionRecipientGroup).where(
        m.ExceptionRecipientGroup.exception_id == item.id).order_by(m.ExceptionRecipientGroup.id))).all()
    deliveries = (await db.scalars(select(m.NotificationOutbox).where(m.NotificationOutbox.exception_id == item.id))).all()
    allowed = []
    if await can_decide(db, actor, item.order_id):
        if item.status == "pending_confirmation":
            allowed.append("confirm")
        elif item.resolution in {"pause", "reconfirm_coil"} and item.released_at is None:
            allowed.append("resume")
    expected, actual = snapshot_spec(item.expected_spec), snapshot_spec(item.actual_spec)
    return {"id": str(item.id), "state_id": str(item.state_id), "order_id": item.order_id,
        "plan_no": f"PP-{item.order_id:06d}", "product_name": part.internal_name if part else None,
        "process_code": state.process_code, "product_box_id": str(item.product_box_id) if item.product_box_id else None,
        "material_batch_id": item.material_batch_id, "batch_no": batch.batch_no if batch else None,
        "expected_spec": expected, "actual_spec": actual, "spec_incomplete": any(value is None for value in [*expected.values(), *actual.values()]), "status": item.status,
        "resolution": item.resolution, "remark": item.remark, "version": item.version,
        "created_by": item.created_by, "created_at": boxes.iso(item.created_at),
        "confirmed_by": item.confirmed_by, "confirmed_at": boxes.iso(item.confirmed_at),
        "released_by": item.released_by, "released_at": boxes.iso(item.released_at),
        "resume_reason": item.resume_reason, "rechecked_material_batch_id": item.rechecked_material_batch_id,
        "blocked": item.status == "confirmed" and item.resolution in {"pause", "reconfirm_coil"} and item.released_at is None,
        "allowed_actions": allowed, "recipient_groups": [{"group_type": g.group_type,
            "resolution_status": g.resolution_status, "recipient_ids": g.recipient_ids, "missing_reason": g.missing_reason} for g in groups],
        "delivery_summary": {key: sum(row.status == key for row in deliveries) for key in ("pending", "sent", "failed")}}


async def state_exceptions(db, actor, state_id):
    rows = (await db.scalars(select(m.CoilSpecException).where(m.CoilSpecException.state_id == state_id)
        .order_by(m.CoilSpecException.id.desc()))).all()
    return [await exception_info(db, actor, row) for row in rows]


async def invalidate_completion(db, state):
    state.version += 1
    await db.execute(update(m.MachineProductionContext).where(m.MachineProductionContext.state_id == state.id,
        m.MachineProductionContext.closed_at.is_(None)).values(completion_scan_at=None))


async def event(db, actor, item, state, *, event_type, before, after, context_id=None):
    if item.product_box_id:
        box = await db.get(m.ProductBox, item.product_box_id)
        _, assignment, _ = await production.state_entities(db, state)
        db.add(m.ProductFlowEvent(product_box_id=box.id, event_type=event_type, state_id=state.id,
            order_id=item.order_id, order_product_id=state.order_product_id, process_code=state.process_code,
            machine_id=assignment.machine_id, context_id=context_id, material_batch_id=item.material_batch_id,
            operator_id=actor.id, before_qty=box.current_qty, after_qty=box.current_qty,
            box_version=box.version, before_snapshot=before, after_snapshot=after))
    await write_audit(db, actor.id, AuditAction.UPDATE, f"coil-{event_type}:{item.id}", before=before, after=after)


async def create_exception(db, actor, *, context_id, material_batch_id, continue_production,
                           idempotency_key, product_box_id=None):
    await permissions.require_action(db, actor, "pool_read", lock=True)
    _, state, product, _ = await production.live_scope(db, actor, context_id)
    await permissions.require_action(db, actor, "create_exception", order_id=product.order_id,
        order_product_id=product.id, context_id=context_id)
    if type(continue_production) is not bool:
        production.conflict("请明确确认是否记录规格差异后继续")

    async def operation():
        locked = await lock_rows(db, order_products=[product.id], states=[state.id],
            boxes=[product_box_id] if product_box_id else [])
        current = locked["states"][state.id]
        await production.live_scope(db, actor, context_id)
        if product_box_id:
            box = locked["boxes"][product_box_id]
            if box.order_product_id != product.id or box.route_revision_id != current.route_revision_id:
                raise QrError(400, "ORDER_MISMATCH", "产品框与当前选单不一致")
            source = await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.box_id == box.id)
                .order_by(m.BoxProcessQuantity.id.desc()).limit(1))
            if source and source.material_batch_id and source.material_batch_id != material_batch_id:
                production.conflict("该框已有不同材料来源，不可用异常核对替换历史来源")
        expected, actual, matches = await comparison(db, product.order_id, material_batch_id)
        key = dedupe(current.id, material_batch_id, expected, actual)
        item = await db.scalar(select(m.CoilSpecException).where(m.CoilSpecException.active_dedupe_key == key,
            m.CoilSpecException.released_at.is_(None)))
        if not matches and continue_production and item is None:
            item = m.CoilSpecException(order_id=product.order_id, product_box_id=product_box_id, state_id=current.id,
                material_batch_id=material_batch_id, expected_spec=expected, actual_spec=actual,
                active_dedupe_key=key, created_by=actor.id)
            db.add(item)
            await db.flush()
            from app.services.notification_service import resolve_recipient_groups
            await resolve_recipient_groups(db, item)
            await invalidate_completion(db, current)
            await event(db, actor, item, current, event_type="exception", before={},
                after={"exception_id": str(item.id), "status": item.status, "expected_spec": expected, "actual_spec": actual}, context_id=context_id)
        await db.flush()
        return {"matches": matches, "requires_confirmation": not matches and item is None,
            "production_allowed": not await production.paused(db, current.id) and (matches or item is not None),
            "expected_spec": expected, "actual_spec": actual,
            "exception": await exception_info(db, actor, item) if item else None,
            "state_version": current.version}

    return await transactional_write(db, actor.id, "coil-check", f"state:{state.id}", idempotency_key,
        dict(context_id=str(context_id), material_batch_id=material_batch_id,
             product_box_id=str(product_box_id) if product_box_id else None, continue_production=continue_production), operation)


async def scoped_exception(db, actor, exception_id):
    item = await db.get(m.CoilSpecException, exception_id, populate_existing=True)
    if item is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "规格异常不存在")
    await permissions.require_action(db, actor, "supervise", order_id=item.order_id, lock=True)
    state = await db.get(m.MachineOrderProcessState, item.state_id)
    return item, state


async def locked_exception(db, item, state):
    locked = await lock_rows(db, order_products=[state.order_product_id], states=[state.id],
        boxes=[item.product_box_id] if item.product_box_id else [])
    item = await db.scalar(select(m.CoilSpecException).where(m.CoilSpecException.id == item.id)
        .with_for_update().execution_options(populate_existing=True))
    return item, locked["states"][state.id]


async def confirm_exception(db, actor, *, exception_id, resolution, remark, expected_version, idempotency_key):
    item, state = await scoped_exception(db, actor, exception_id)
    if resolution not in {"accept_continue", "pause", "reconfirm_coil"}:
        production.conflict("请选择有效处理结果")

    async def operation():
        current, current_state = await locked_exception(db, item, state)
        check_version(current.version, expected_version, code="STATE_CONFLICT")
        if current.status != "pending_confirmation":
            production.conflict("该异常已经由负责人确认，请重新读取")
        now = await db.scalar(select(func.clock_timestamp()))
        before = {"status": current.status, "resolution": current.resolution}
        current.status, current.resolution, current.remark = "confirmed", resolution, remark
        current.confirmed_by, current.confirmed_at, current.version = actor.id, now, current.version + 1
        await invalidate_completion(db, current_state)
        await db.flush()
        result = await exception_info(db, actor, current)
        await event(db, actor, current, current_state, event_type="exception", before=before, after=result)
        return result
    return await transactional_write(db, actor.id, "coil-confirm", f"exception:{exception_id}", idempotency_key,
        dict(resolution=resolution, remark=remark, expected_version=expected_version), operation)


async def resume_exception(db, actor, *, exception_id, rechecked_material_batch_id, reason, expected_version, idempotency_key):
    item, state = await scoped_exception(db, actor, exception_id)
    if not isinstance(reason, str) or not reason.strip():
        production.conflict("恢复必须填写复核依据")

    async def operation():
        current, current_state = await locked_exception(db, item, state)
        check_version(current.version, expected_version, code="STATE_CONFLICT")
        if current.status != "confirmed" or current.resolution not in {"pause", "reconfirm_coil"} or current.released_at:
            production.conflict("该异常没有可解除的暂停状态")
        _, actual, matches = await comparison(db, current.order_id, rechecked_material_batch_id, expected=current.expected_spec)
        if not matches:
            production.conflict("复核卷料仍不符合原异常的订单规格，不能解除暂停")
        current.released_by, current.released_at = actor.id, await db.scalar(select(func.clock_timestamp()))
        current.resume_reason, current.rechecked_material_batch_id = reason.strip(), rechecked_material_batch_id
        current.version += 1
        await invalidate_completion(db, current_state)
        await db.flush()
        result = await exception_info(db, actor, current)
        await event(db, actor, current, current_state, event_type="resume", before={"released_at": None},
            after={**result, "rechecked_actual_spec": actual})
        return result
    return await transactional_write(db, actor.id, "coil-resume", f"exception:{exception_id}", idempotency_key,
        dict(rechecked_material_batch_id=rechecked_material_batch_id, reason=reason, expected_version=expected_version), operation)


async def ensure_material_decision(db, state, order_id, material_batch_id, *, historical=False):
    # Historical quantities without a recorded coil remain explicitly unknown.
    if material_batch_id is None:
        return
    expected, actual, matches = await comparison(db, order_id, material_batch_id)
    if not matches:
        query = select(m.CoilSpecException.id).where(
            m.CoilSpecException.active_dedupe_key == dedupe(state.id, material_batch_id, expected, actual))
        if not historical:
            query = query.where(m.CoilSpecException.released_at.is_(None))
        item = await db.scalar(query.limit(1))
        if item is None:
            production.conflict("卷料规格不匹配，请先核对并明确记录异常后继续生产")
