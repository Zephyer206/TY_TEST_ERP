"""Fixed-route handoff and scoped, paginated production trace."""
from datetime import timedelta

from sqlalchemy import func, or_, select, text, tuple_

from app.models import product_box as m
from app.models.audit import AuditAction
from app.models.machine import Machine
from app.models.production import PlanMachineAssignment
from app.models.user import User
from app.services import product_box_service as boxes, product_production_service as production
from app.services import qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, lock_rows, transactional_write, write_audit


async def scoped_box(db, actor, box_id):
    box = await db.get(m.ProductBox, box_id, populate_existing=True)
    if box is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "产品框不存在")
    await permissions.require_action(db, actor, "trace", order_id=box.order_id)
    return box


async def advance(db, actor, *, box_id, context_id, expected_version, state_version, idempotency_key):
    await permissions.require_action(db, actor, "pool_read", lock=True)
    context, target, product, assignment = await production.live_scope(db, actor, context_id)
    await permissions.require_action(db, actor, "advance", order_id=product.order_id,
        order_product_id=product.id, context_id=context_id)

    async def operation():
        # Product demand lock serializes all quantities/handoffs before state/box locks.
        await lock_rows(db, order_products=[product.id])
        previous = await db.scalar(select(m.BoxProcessQuantity).where(m.BoxProcessQuantity.box_id == box_id)
            .order_by(m.BoxProcessQuantity.id.desc()).limit(1))
        state_ids = [target.id] + ([previous.state_id] if previous else [])
        locked = await lock_rows(db, states=state_ids, boxes=[box_id])
        box, state = locked["boxes"][box_id], locked["states"][target.id]
        fresh, _, _, _ = await production.live_scope(db, actor, context_id)
        check_version(box.version, expected_version)
        check_version(state.version, state_version, code="STATE_CONFLICT")
        if (box.order_product_id != product.id or box.route_revision_id != state.route_revision_id
                or box.order_id != product.order_id):
            raise QrError(400, "ORDER_MISMATCH", "该框与目标订单产品或固定路线不一致")
        route = await db.get(m.ProductRouteRevision, box.route_revision_id)
        codes = [step["code"] for step in route.steps_json] if route and route.is_published else []
        if (not previous or box.current_process_code not in codes or box.current_qty <= 0
                or box.lifecycle_status != "active"):
            production.conflict("请先保存当前工艺的有效数量，再流转")
        index = codes.index(box.current_process_code)
        if index + 1 >= len(codes) or codes[index + 1] != state.process_code:
            production.conflict("只能进入固定路线的下一道工艺")
        source_state = locked["states"][previous.state_id]
        if (source_state.process_code != box.current_process_code or source_state.route_revision_id != box.route_revision_id
                or previous.current_qty != box.current_qty or await production.paused(db, source_state.id)
                or await production.paused(db, state.id)):
            production.conflict("当前工艺数量或暂停状态已变化，请重新核对")
        machine = await db.get(Machine, assignment.machine_id)
        step = route.steps_json[index + 1]
        if (not machine or machine.is_deleted or (machine.id not in step.get("machine_ids", [])
                and machine.machine_type not in step.get("machine_types", []))):
            production.conflict("所选机台不能执行目标工艺")
        if await db.scalar(select(m.BoxProcessQuantity.id).where(m.BoxProcessQuantity.box_id == box_id,
                m.BoxProcessQuantity.state_id == state.id)):
            production.conflict("目标工艺已有数量，不允许重复流转或回流")
        now = await db.scalar(select(func.clock_timestamp()))
        value = m.BoxProcessQuantity(state_id=state.id, box_id=box_id, input_qty=box.current_qty,
            current_qty=box.current_qty, material_batch_id=previous.material_batch_id,
            source_quantity_id=previous.source_quantity_id, updated_by=actor.id, updated_at=now)
        db.add(value)
        old_code = box.current_process_code
        box.current_process_code = state.process_code
        box.next_process_code = codes[index + 2] if index + 2 < len(codes) else None
        box.version, box.updated_at = box.version + 1, now
        state.production_status, state.version = "in_progress", state.version + 1
        fresh.last_activity_at, fresh.expires_at, fresh.completion_scan_at = now, now + timedelta(minutes=30), None
        db.add(m.ProductFlowEvent(product_box_id=box_id, event_type="process_start", process_code=state.process_code,
            machine_id=assignment.machine_id, order_id=product.order_id, order_product_id=product.id,
            state_id=state.id, context_id=context_id, material_batch_id=previous.material_batch_id,
            operator_id=actor.id, before_qty=box.current_qty, after_qty=box.current_qty, box_version=box.version,
            before_snapshot={"process_code": old_code, "state_id": str(previous.state_id), "output_qty": box.current_qty},
            after_snapshot={"process_code": state.process_code, "state_id": str(state.id), "input_qty": value.input_qty,
                "source_quantity_id": str(value.source_quantity_id) if value.source_quantity_id else None}, occurred_at=now))
        await db.flush()
        result = await production.quantity_result(db, actor, fresh, state, product, assignment, box, value)
        await write_audit(db, actor.id, AuditAction.UPDATE, f"process-advance:{box_id}", after=result)
        return result

    return await transactional_write(db, actor.id, "process-advance", f"box:{box_id}", idempotency_key,
        dict(context_id=str(context_id), expected_version=expected_version, state_version=state_version), operation)


def event_info(event, username=None, machine_no=None):
    return {"id": str(event.id), "event_type": event.event_type, "process_code": event.process_code,
        "state_id": str(event.state_id) if event.state_id else None, "operator_id": event.operator_id,
        "operator_name": username, "machine_id": event.machine_id, "machine_no": machine_no,
        "material_batch_id": event.material_batch_id, "before_qty": event.before_qty, "after_qty": event.after_qty,
        "before_snapshot": event.before_snapshot, "after_snapshot": event.after_snapshot,
        "remark": event.remark, "occurred_at": boxes.iso(event.occurred_at)}


def event_query(box_id):
    return select(m.ProductFlowEvent, User.username, Machine.machine_no).outerjoin(User,
        User.id == m.ProductFlowEvent.operator_id).outerjoin(Machine, Machine.id == m.ProductFlowEvent.machine_id
        ).where(m.ProductFlowEvent.product_box_id == box_id)


async def latest_event(db, box_id):
    row = (await db.execute(event_query(box_id).where(m.ProductFlowEvent.event_type != "scan")
        .order_by(m.ProductFlowEvent.occurred_at.desc(), m.ProductFlowEvent.id.desc()).limit(1))).first()
    return event_info(*row) if row else None


async def events(db, actor, *, box_id, page_size=50, before_id=None):
    await scoped_box(db, actor, box_id)
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise QrError(400, "INVALID_PAGE", "每页记录数须为1至100")
    query = event_query(box_id)
    if before_id is not None:
        cursor = await db.get(m.ProductFlowEvent, before_id)
        if not cursor or cursor.product_box_id != box_id:
            raise QrError(400, "INVALID_PAGE", "追溯游标无效，请重新读取")
        query = query.where(tuple_(m.ProductFlowEvent.occurred_at, m.ProductFlowEvent.id) <
            tuple_(cursor.occurred_at, cursor.id))
    rows = (await db.execute(query.order_by(m.ProductFlowEvent.occurred_at.desc(),
        m.ProductFlowEvent.id.desc()).limit(page_size + 1))).all()
    return {"items": [event_info(*row) for row in rows[:page_size]],
        "next_cursor": str(rows[page_size - 1][0].id) if len(rows) > page_size else None,
        "total": await db.scalar(select(func.count()).select_from(m.ProductFlowEvent).where(m.ProductFlowEvent.product_box_id == box_id))}


async def material_lineage(db, ids):
    if not ids:
        return [], False
    # Cycle-safe native traversal; no ORM lazy IO, no unbounded recursive Python.
    rows = (await db.execute(text("""WITH RECURSIVE lineage AS (
        SELECT id,parent_batch_id,ARRAY[id] path,0 depth FROM material_batches WHERE id=ANY(CAST(:ids AS integer[]))
        UNION ALL SELECT b.id,b.parent_batch_id,l.path||b.id,l.depth+1 FROM material_batches b
        JOIN lineage l ON b.id=l.parent_batch_id WHERE NOT b.id=ANY(l.path) AND l.depth<99
    ) SELECT b.id,coalesce(b.batch_no,b.qr_uid) batch_no,b.parent_batch_id,b.qr_code,b.current_weight,b.thickness,b.width,
        b.status::text status,b.iqc_result::text iqc_result,coalesce(mat.name,b.material_name) material_name,mat.grade,
        min(l.depth) depth, bool_or(b.parent_batch_id=ANY(l.path) OR l.depth=99) incomplete
        FROM lineage l JOIN material_batches b ON b.id=l.id LEFT JOIN materials mat ON mat.id=b.material_id
        GROUP BY b.id,mat.name,mat.grade ORDER BY min(l.depth),b.id"""), {"ids": ids})).mappings().all()
    result = []
    for row in rows:
        entry = dict(row)
        for key in ("current_weight", "thickness", "width"):
            entry[key] = float(entry[key]) if entry[key] is not None else None
        entry.pop("incomplete")
        result.append(entry)
    resolved = {row["id"] for row in rows}
    incomplete = any(row["incomplete"] or (row["parent_batch_id"] is not None
        and row["parent_batch_id"] not in resolved) for row in rows)
    return result, incomplete


async def trace_box(db, actor, *, box_id, page=1, page_size=50):
    from app.services.product_split_service import split_options
    box = await scoped_box(db, actor, box_id)
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
        raise QrError(400, "INVALID_PAGE", "追溯分页参数无效")
    pool = await db.get(m.ProductQrPoolItem, box.qr_pool_item_id)
    route = await db.get(m.ProductRouteRevision, box.route_revision_id)
    owner = await db.scalar(select(m.ProductOrderContext.business_owner_id).where(m.ProductOrderContext.order_id == box.order_id))
    quantity_query = select(m.BoxProcessQuantity, m.MachineOrderProcessState.process_code,
        PlanMachineAssignment.machine_id, Machine.machine_no, User.username).join(m.MachineOrderProcessState,
        m.MachineOrderProcessState.id == m.BoxProcessQuantity.state_id).join(PlanMachineAssignment,
        PlanMachineAssignment.id == m.MachineOrderProcessState.assignment_id).join(Machine,
        Machine.id == PlanMachineAssignment.machine_id).outerjoin(User, User.id == m.BoxProcessQuantity.updated_by
        ).where(m.BoxProcessQuantity.box_id == box_id).order_by(m.BoxProcessQuantity.id)
    values = (await db.execute(quantity_query.offset((page - 1) * page_size).limit(page_size))).all()
    quantities = [{**production.quantity_info(value), "process_code": code, "machine_id": machine,
        "machine_no": machine_no, "operator_name": username} for value, code, machine, machine_no, username in values]
    material_ids = list((await db.scalars(select(m.BoxProcessQuantity.material_batch_id).where(
        m.BoxProcessQuantity.box_id == box_id, m.BoxProcessQuantity.material_batch_id.is_not(None)).distinct())).all())
    materials, incomplete = await material_lineage(db, material_ids)
    scoped_relations = await permissions.visible_order_clause(db, actor, m.ProductBoxRelation.source_order_id)
    scoped_targets = await permissions.visible_order_clause(db, actor, m.ProductBoxRelation.target_order_id)
    relation_filter = or_(m.ProductBoxRelation.parent_box_id == box_id, m.ProductBoxRelation.child_box_id == box_id)
    # Cross-order relation snapshots must not leak a hidden order through a visible box.
    relation_filter = relation_filter & scoped_relations & scoped_targets
    collections = {}
    for name, model, predicate, columns in (
        ("relations", m.ProductBoxRelation, relation_filter,
         ("relation_type", "parent_box_id", "child_box_id", "source_order_id", "target_order_id", "quantity", "order_qty", "stock_qty", "created_by", "source_snapshot")),
        ("exceptions", m.CoilSpecException, (m.CoilSpecException.product_box_id == box_id) | m.CoilSpecException.state_id.in_(
            select(m.BoxProcessQuantity.state_id).where(m.BoxProcessQuantity.box_id == box_id)),
         ("status", "resolution", "material_batch_id", "created_by", "confirmed_by", "remark")),
        ("conversions", m.ProductConversionRecord, m.ProductConversionRecord.product_box_id == box_id,
         ("source_product_code", "target_product_code", "confirmation_status", "actual_qty", "created_by", "confirmed_by", "remark")),
    ):
        rows = (await db.scalars(select(model).where(predicate).order_by(model.id)
            .offset((page - 1) * page_size).limit(page_size))).all()
        collections[name] = [{"id": str(row.id), **{key: (str(getattr(row, key)) if key in {"parent_box_id", "child_box_id"}
            else getattr(row, key)) for key in columns}, "created_at": boxes.iso(row.created_at)} for row in rows]
        collections[name + "_total"] = await db.scalar(select(func.count()).select_from(model).where(predicate))
    related_ids = {int(row[key]) for row in collections["relations"] for key in ("parent_box_id", "child_box_id")}
    related_boxes = {str(row.id): row for row in (await db.scalars(select(m.ProductBox).where(m.ProductBox.id.in_(related_ids)))).all()} if related_ids else {}
    for relation in collections["relations"]:
        for side in ("parent", "child"):
            related = related_boxes[relation[side + "_box_id"]]
            relation[side + "_box_no"], relation[side + "_current_qty"] = related.box_no, related.current_qty
    return {"box": boxes.box_info(box, pool), "order": {"id": box.order_id, "plan_no": f"PP-{box.order_id:06d}", "business_owner_id": owner},
        "route": {"route_code": route.route_code, "revision": route.revision, "steps": route.steps_json,
            "first_output_process_code": route.first_output_process_code},
        "quantities": quantities, "quantities_total": await db.scalar(select(func.count()).select_from(m.BoxProcessQuantity).where(m.BoxProcessQuantity.box_id == box_id)),
        "materials": materials, "missing_material_source": not material_ids, "material_lineage_incomplete": incomplete,
        "latest_event": await latest_event(db, box_id), "events": await events(db, actor, box_id=box_id, page_size=5),
        "page": page, "page_size": page_size, "split": await split_options(db, actor, box, page=page, page_size=page_size), **collections}
