"""Stable product QR identities and one-time binding to configured orders."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, or_, select, text

from app.core.config import settings
from app.models.audit import AuditAction
from app.models.customer import Customer
from app.models.part import Part
from app.models.production import PlanMachineAssignment, ProductionPlan
from app.models.user import User
from app.models.warehouse import QRScanLog, ScanOperation, ScanType
from app.models import product_box as m
from app.services import qr_permission_service as permissions
from app.services.qr_transaction_service import QrError, check_version, lock_rows, transactional_write, write_audit

_PAYLOAD = re.compile(r"PFB:v1:([1-9][0-9]{0,18}):(PFB-([0-9]{8})-([0-9]{6,19}))\Z")


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds") if value else None


def parse_payload(payload: str) -> tuple[int, str]:
    match = _PAYLOAD.fullmatch(payload) if isinstance(payload, str) and len(payload) <= 200 else None
    if not match:
        raise QrError(400, "INVALID_QR", "二维码格式或版本无效")
    identity = int(match[1])
    try:
        datetime.strptime(match[3], "%Y%m%d")
    except ValueError:
        raise QrError(400, "INVALID_QR", "二维码身份无效") from None
    if identity > 9_223_372_036_854_775_807 or match[4] != str(identity).zfill(6):
        raise QrError(400, "INVALID_QR", "二维码身份无效")
    return identity, match[2]


def pool_info(item: m.ProductQrPoolItem, bound_box_id=None):
    return {"id": str(item.id), "public_code": item.public_code, "qr_payload": item.qr_payload,
            "payload_version": item.payload_version, "pool_status": item.pool_status,
            "print_batch_no": item.print_batch_no, "print_count": item.print_count,
            "printed_at": iso(item.printed_at), "created_at": iso(item.created_at),
            "bound_box_id": str(bound_box_id) if bound_box_id is not None else None}


def box_info(box: m.ProductBox, item: m.ProductQrPoolItem):
    return {"id": str(box.id), "qr_pool_item_id": str(box.qr_pool_item_id), "box_no": box.box_no,
            "order_id": box.order_id, "order_product_id": str(box.order_product_id),
            "part_id": box.part_id, "product_code": box.product_code,
            "product_name_snapshot": box.product_name_snapshot, "customer_id": box.customer_id,
            "customer_name_snapshot": box.customer_name_snapshot, "customer_part_no": box.customer_part_no,
            "route_revision_id": str(box.route_revision_id), "current_process_code": box.current_process_code,
            "next_process_code": box.next_process_code, "current_qty": box.current_qty,
            "version": box.version, "lifecycle_status": box.lifecycle_status,
            "bound_by": box.bound_by, "bound_at": iso(box.bound_at),
            "public_code": item.public_code, "qr_payload": item.qr_payload}


async def resolve_pool(db, payload):
    identity, public_code = parse_payload(payload)
    item = await db.get(m.ProductQrPoolItem, identity, populate_existing=True)
    if item is None:
        raise QrError(404, "QR_NOT_IN_POOL", "二维码不在系统池中")
    if item.qr_payload != payload or item.public_code != public_code or item.payload_version != "v1":
        raise QrError(400, "INVALID_QR", "二维码完整身份不匹配")
    if item.pool_status == "void":
        raise QrError(409, "STATE_CONFLICT", "二维码当前不可使用")
    return item


async def generate_batch(db, actor, *, count, idempotency_key, print_batch_no=None):
    await permissions.require_action(db, actor, "generate", lock=True)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= settings.PRODUCT_QR_BATCH_LIMIT:
        raise QrError(400, "INVALID_QUANTITY", "批量数量超出系统允许范围",
                      {"maximum": settings.PRODUCT_QR_BATCH_LIMIT})

    async def operation():
        now = await db.scalar(select(func.clock_timestamp()))
        date = now.astimezone(ZoneInfo("Asia/Hong_Kong")).strftime("%Y%m%d")
        batch_no = print_batch_no or f"PFBG-{date}-{uuid4().hex[:12]}"
        identifiers = (await db.execute(text("SELECT nextval(pg_get_serial_sequence('product_qr_pool_items','id')) "
                                               "FROM generate_series(1, :count)"), {"count": count})).scalars().all()
        items = []
        for identity in identifiers:
            code = f"PFB-{date}-{identity:06}"
            item = m.ProductQrPoolItem(id=identity, public_code=code, qr_payload=f"PFB:v1:{identity}:{code}",
                payload_version="v1", pool_status="unused", print_batch_no=batch_no, print_count=0,
                created_by=actor.id, created_at=now, updated_at=now)
            db.add(item)
            items.append(item)
        await db.flush()
        await write_audit(db, actor.id, AuditAction.CREATE, f"qr-batch:{batch_no}",
                          after={"count": count, "item_ids": [str(i.id) for i in items]})
        return {"print_batch_no": batch_no, "count": count, "items": [pool_info(i) for i in items]}

    return await transactional_write(db, actor.id, "generate", "pool", idempotency_key,
        {"count": count, "print_batch_no": print_batch_no}, operation, http_status=201)


async def pool_scope(db, actor):
    await permissions.require_action(db, actor, "pool_read")
    visible = await permissions.visible_order_clause(db, actor, m.ProductBox.order_id)
    visible_bound = exists(select(m.ProductBox.id).where(
        m.ProductBox.qr_pool_item_id == m.ProductQrPoolItem.id, visible).correlate(m.ProductQrPoolItem))
    # Unused labels have no order owner. Sales can see only bound labels belonging
    # to their explicit orders; operational users may query the unused pool.
    return visible_bound if actor.dept == "sales" and actor.role_level < 3 else or_(
        m.ProductQrPoolItem.pool_status == "unused", visible_bound)


async def list_pool(db, actor, *, pool_status=None, print_batch_no=None, page=1, page_size=50):
    clause = await pool_scope(db, actor)
    filters = [clause]
    if pool_status:
        filters.append(m.ProductQrPoolItem.pool_status == pool_status)
    if print_batch_no:
        filters.append(m.ProductQrPoolItem.print_batch_no == print_batch_no)
    total = await db.scalar(select(func.count()).select_from(m.ProductQrPoolItem).where(*filters))
    rows = (await db.execute(select(m.ProductQrPoolItem, m.ProductBox.id)
        .outerjoin(m.ProductBox, m.ProductBox.qr_pool_item_id == m.ProductQrPoolItem.id)
        .where(*filters).order_by(m.ProductQrPoolItem.id.desc())
        .offset((page - 1) * page_size).limit(page_size))).all()
    return {"items": [pool_info(item, box_id) for item, box_id in rows], "total": total,
            "page": page, "page_size": page_size,
            "actor": {"id": actor.id, "dept": actor.dept, "role_level": actor.role_level},
            "capabilities": sorted(await permissions.capabilities(db, actor)),
            "batch_limit": settings.PRODUCT_QR_BATCH_LIMIT}


async def order_qr_context(db, actor, *, order_id):
    """Expose persisted order configuration without inventing legacy defaults."""
    await permissions.require_action(db, actor, "pool_read")
    plan = await db.get(ProductionPlan, order_id)
    if plan is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "订单不存在")
    if not await permissions.can_view_order(db, actor, order_id):
        raise QrError(403, "FORBIDDEN", "当前账号无此订单的查看权限")
    context = await db.scalar(select(m.ProductOrderContext).where(m.ProductOrderContext.order_id == order_id))
    valid_owner = await db.scalar(select(User.id).where(
        User.id == context.business_owner_id, User.dept == "sales", User.role_level >= 2)) if context else None
    missing = [] if valid_owner is not None else ["business_owner"]
    if plan.part_id is None:
        missing.append("part")
    if plan.is_left_right_pair and plan.paired_part_id is None:
        missing.append("paired_part")
    products = (await db.scalars(select(m.ProductOrderProduct).where(
        m.ProductOrderProduct.order_id == order_id).order_by(m.ProductOrderProduct.id))).all()
    if not any(product.binding_allowed for product in products):
        missing.append("products")
    results = []
    for product in products:
        route = await db.get(m.ProductRouteRevision, product.route_revision_id)
        part = (await db.execute(select(Part.internal_name, Part.customer_part_no, Part.is_deleted)
            .where(Part.id == product.part_id))).one_or_none()
        states = (await db.execute(select(m.MachineOrderProcessState, PlanMachineAssignment)
            .join(PlanMachineAssignment, PlanMachineAssignment.id == m.MachineOrderProcessState.assignment_id)
            .where(m.MachineOrderProcessState.order_product_id == product.id)
            .order_by(m.MachineOrderProcessState.id))).all()
        product_missing = []
        if part is None or part.is_deleted:
            product_missing.append("part")
        if product.binding_allowed:
            try:
                await binding_configuration(db, product)
            except QrError as error:
                if error.details and "missing_configuration" in error.details:
                    product_missing.extend(error.details["missing_configuration"])
                elif error.code == "ORDER_MISMATCH":
                    product_missing.append("order_part")
                elif error.code == "INVALID_PRODUCT":
                    product_missing.append("part")
                elif error.code == "STATE_CONFLICT":
                    product_missing.append("order_status")
                else:
                    raise
        elif route is None or not route.is_published:
            product_missing.append("route")
        product_missing = list(dict.fromkeys(product_missing))
        if product.binding_allowed:
            missing.extend(f"products.{product.id}.{field}" for field in product_missing)
        results.append({"id": str(product.id), "part_id": product.part_id,
            "product_code": product.product_code, "target_qty": product.target_qty,
            "route_revision_id": str(product.route_revision_id), "binding_allowed": product.binding_allowed,
            "conversion_source_id": str(product.conversion_source_id) if product.conversion_source_id is not None else None,
            "version": product.version, "part_name": part.internal_name if part else None,
            "customer_part_no": part.customer_part_no if part else None,
            "route": {"id": str(route.id), "route_code": route.route_code, "revision": route.revision,
                "product_code": route.product_code, "steps": route.steps_json,
                "first_output_process_code": route.first_output_process_code,
                "is_published": route.is_published} if route else None,
            "machine_process_targets": [{"state_id": str(state.id), "assignment_id": assignment.id,
                "machine_id": assignment.machine_id, "process_code": state.process_code,
                "target_qty": state.target_qty, "production_status": state.production_status,
                "version": state.version, "is_active": assignment.is_active} for state, assignment in states],
            "missing_configuration": product_missing,
            "can_bind": product.binding_allowed and not product_missing})
    return {"order_id": plan.id, "part_id": plan.part_id, "paired_part_id": plan.paired_part_id,
        "is_left_right_pair": plan.is_left_right_pair, "status": plan.status, "total_qty": plan.total_qty,
        "business_owner_id": context.business_owner_id if context else None,
        "version": context.version if context else 0, "missing_configuration": list(dict.fromkeys(missing)),
        "products": results}


_METADATA_LIMITS = {"customer_name_snapshot": 200, "customer_part_no": 150, "next_process_code": 50}


async def edit_metadata(db, actor, *, box_id, changes, expected_version, idempotency_key):
    # The service whitelist also protects internal callers; HTTP schema rejects
    # extra identity/order/product fields before this function is reached.
    if not isinstance(changes, dict) or not changes or set(changes) - set(_METADATA_LIMITS):
        raise QrError(400, "STATE_CONFLICT", "仅允许编辑客户名称、客户件号和后续工艺快照")
    for field, value in changes.items():
        if value is not None and (not isinstance(value, str) or len(value) > _METADATA_LIMITS[field]
                                   or (field == "next_process_code" and not value.strip())):
            raise QrError(400, "STATE_CONFLICT", "标签快照字段格式无效")
    await permissions.require_action(db, actor, "pool_read", lock=True)
    box = await db.get(m.ProductBox, box_id, populate_existing=True)
    if box is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "产品框不存在")
    await permissions.require_action(db, actor, "metadata", order_id=box.order_id)
    if box.lifecycle_status not in {"active", "empty"}:
        raise QrError(409, "STATE_CONFLICT", "该产品框当前不可编辑标签快照")

    async def operation():
        current = (await lock_rows(db, boxes=[box.id]))["boxes"][box.id]
        await permissions.require_action(db, actor, "metadata", order_id=current.order_id)
        if current.lifecycle_status not in {"active", "empty"}:
            raise QrError(409, "STATE_CONFLICT", "该产品框当前不可编辑标签快照")
        check_version(current.version, expected_version)
        if "next_process_code" in changes and changes["next_process_code"] is not None:
            route = await db.get(m.ProductRouteRevision, current.route_revision_id)
            steps = route.steps_json if route and route.is_published and route.product_code == current.product_code else []
            codes = [step.get("code") if isinstance(step, dict) else None for step in steps]
            if (not codes or any(not isinstance(code, str) or not code.strip() for code in codes)
                    or len(set(codes)) != len(codes)
                    or (current.current_process_code is not None and current.current_process_code not in codes)):
                raise QrError(409, "STATE_CONFLICT", "产品框绑定路线无效，请重新读取配置")
            index = codes.index(current.current_process_code) + 1 if current.current_process_code is not None else 0
            if changes["next_process_code"] not in codes[index:]:
                raise QrError(400, "STATE_CONFLICT", "后续工艺必须属于本框路线的后续步骤")
        before = {field: getattr(current, field) for field in _METADATA_LIMITS}
        for field, value in changes.items():
            setattr(current, field, value)
        now = await db.scalar(select(func.clock_timestamp()))
        current.version += 1
        current.updated_at = now
        after = {field: getattr(current, field) for field in _METADATA_LIMITS}
        db.add(m.ProductFlowEvent(product_box_id=current.id, event_type="metadata_edit",
            order_id=current.order_id, order_product_id=current.order_product_id, operator_id=actor.id,
            before_qty=current.current_qty, after_qty=current.current_qty, box_version=current.version,
            before_snapshot=before, after_snapshot=after, occurred_at=now))
        await write_audit(db, actor.id, AuditAction.UPDATE, f"box:{current.id}:metadata", before=before, after=after)
        item = await db.get(m.ProductQrPoolItem, current.qr_pool_item_id)
        return box_info(current, item)

    return await transactional_write(db, actor.id, "metadata", f"box:{box.id}", idempotency_key,
        {"changes": changes, "expected_version": expected_version}, operation)


async def binding_configuration(db, product):
    plan = (await db.execute(select(ProductionPlan.id, ProductionPlan.part_id, ProductionPlan.paired_part_id,
        ProductionPlan.is_left_right_pair, ProductionPlan.status).where(ProductionPlan.id == product.order_id))).one_or_none()
    if not plan:
        raise QrError(404, "ENTITY_NOT_FOUND", "订单不存在")
    if not product.binding_allowed or product.product_code not in ("B", "C"):
        raise QrError(400, "INVALID_PRODUCT", "该配置不能直接绑定产品框")
    allowed_parts = {plan.part_id}
    if plan.is_left_right_pair:
        allowed_parts.add(plan.paired_part_id)
    if product.part_id not in allowed_parts:
        raise QrError(400, "ORDER_MISMATCH", "实际产品不属于该订单的主件或配对件")
    if str(plan.status or "").lower() in {"completed", "cancelled", "closed"}:
        raise QrError(409, "STATE_CONFLICT", "该订单当前不能绑定新产品框")
    missing = []
    context = (await db.execute(select(m.ProductOrderContext).where(
        m.ProductOrderContext.order_id == product.order_id))).scalar_one_or_none()
    owner = (await db.execute(select(User.id).where(
        User.id == context.business_owner_id, User.dept == "sales", User.role_level >= 2))).scalar_one_or_none() if context else None
    if owner is None:
        missing.append("business_owner")
    route = await db.get(m.ProductRouteRevision, product.route_revision_id)
    codes = [step.get("code") for step in route.steps_json if isinstance(step, dict)] if route else []
    if (route is None or route.product_code != product.product_code or not route.is_published
            or not codes or len(codes) != len(route.steps_json) or len(set(codes)) != len(codes)
            or any(not isinstance(code, str) or not code.strip() for code in codes)
            or route.first_output_process_code not in codes):
        missing.append("route")
    states = (await db.execute(select(m.MachineOrderProcessState, PlanMachineAssignment)
        .join(PlanMachineAssignment, PlanMachineAssignment.id == m.MachineOrderProcessState.assignment_id)
        .where(m.MachineOrderProcessState.order_product_id == product.id,
               m.MachineOrderProcessState.route_revision_id == product.route_revision_id,
               PlanMachineAssignment.plan_id == product.order_id, PlanMachineAssignment.is_active.is_(True)))).all()
    if not states or any(state.process_code not in codes for state, _ in states):
        missing.append("machine_process_targets")
    if product.target_qty <= 0:
        missing.append("target_qty")
    part = (await db.execute(select(Part.id, Part.internal_name, Part.customer_part_no, Part.customer_id)
        .where(Part.id == product.part_id, Part.is_deleted.is_(False)))).one_or_none()
    if part is None:
        raise QrError(400, "INVALID_PRODUCT", "实际件号不存在或已停用")
    customer_name = await db.scalar(select(Customer.name).where(Customer.id == part.customer_id)) if part.customer_id else None
    if missing:
        raise QrError(409, "STATE_CONFLICT", "订单二维码配置尚未完整", {"missing_configuration": missing})
    return route, part, customer_name


async def bind_box(db, actor, *, qr_payload, order_product_id, idempotency_key, context_id=None):
    await permissions.require_action(db, actor, "pool_read", lock=True)
    item = await resolve_pool(db, qr_payload)
    product = await db.get(m.ProductOrderProduct, order_product_id)
    if product is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "订单产品配置不存在")
    action = "warehouse_bind" if actor.dept == "warehouse" else "production_bind"
    await permissions.require_action(db, actor, action, order_id=product.order_id,
                                     order_product_id=product.id, context_id=context_id)

    async def operation():
        locked = await lock_rows(db, order_products=[product.id])
        current_product = locked["order_products"][product.id]
        # Check binding before configuration errors, preserving the explicit
        # immutable-identity response for a second binding or second order.
        existing = await db.scalar(select(m.ProductBox.id).where(m.ProductBox.qr_pool_item_id == item.id))
        if existing:
            raise QrError(409, "QR_ALREADY_BOUND", "二维码已经绑定，请查询当前框")
        route, part, customer_name = await binding_configuration(db, current_product)
        state = None
        if action == "production_bind":
            context, state = await permissions.require_context(db, actor, context_id, product.order_id, product.id)
            if state.route_revision_id != route.id:
                raise QrError(409, "STATE_CONFLICT", "旧路线只可用于既有产品框，请选择当前版本后绑定新框")
            await lock_rows(db, states=[state.id])
            context, state = await permissions.require_context(db, actor, context_id, product.order_id, product.id)
        locked_pool = (await lock_rows(db, pool=[item.id]))["pool"][item.id]
        if locked_pool.pool_status != "unused":
            raise QrError(409, "QR_ALREADY_BOUND", "二维码已经绑定，请查询当前框")
        now = await db.scalar(select(func.clock_timestamp()))
        box = m.ProductBox(qr_pool_item_id=item.id, box_no=item.public_code,
            order_id=product.order_id, order_product_id=product.id, part_id=part.id,
            product_code=product.product_code, product_name_snapshot=part.internal_name or "",
            customer_id=part.customer_id, customer_name_snapshot=customer_name, customer_part_no=part.customer_part_no,
            route_revision_id=route.id, current_process_code=None, next_process_code=route.steps_json[0]["code"],
            current_qty=0, version=1, lifecycle_status="active", bound_by=actor.id, bound_at=now,
            created_at=now, updated_at=now)
        db.add(box)
        await db.flush()
        locked_pool.pool_status, locked_pool.updated_at = "bound", now
        db.add(m.ProductFlowEvent(product_box_id=box.id, event_type="bind", order_id=box.order_id,
            order_product_id=box.order_product_id, state_id=state.id if state else None,
            context_id=context_id, operator_id=actor.id, before_qty=0, after_qty=0, box_version=1,
            after_snapshot={"order_id": box.order_id, "part_id": box.part_id}, occurred_at=now))
        await record_scan(db, actor.id, item, ScanOperation.BIND)
        if action == "production_bind":
            context.last_activity_at, context.expires_at = now, now + timedelta(minutes=30)
        response = {"pool_item": pool_info(locked_pool, box.id), "box": box_info(box, locked_pool),
                    "allowed_actions": ["trace"]}
        await write_audit(db, actor.id, AuditAction.CREATE, f"box:{box.id}", after=response["box"])
        return response

    return await transactional_write(db, actor.id, "bind", f"pool:{item.id}", idempotency_key,
        {"qr_payload": qr_payload, "order_product_id": str(order_product_id),
         "context_id": str(context_id) if context_id is not None else None}, operation, http_status=201)


async def record_scan(db, actor_id, item, operation):
    db.add(QRScanLog(scan_type=ScanType.PFB, entity_id=item.id, entity_no=item.public_code,
                    operator_id=actor_id, operation=operation,
                    scanned_at=func.timezone("UTC", func.clock_timestamp())))
    await db.flush()


async def scan_box(db, actor, *, qr_payload, split_parent_id=None, context_id=None):
    from app.services.product_process_service import latest_event
    await permissions.require_action(db, actor, "pool_read", lock=True)
    if split_parent_id is not None:
        if context_id is not None:
            raise QrError(400, "STATE_CONFLICT", "子标签核对不能同时提交生产上下文")
        from app.services.product_split_service import permitted, source_partition
        parent = await db.get(m.ProductBox, split_parent_id, populate_existing=True)
        if parent is None:
            raise QrError(404, "ENTITY_NOT_FOUND", "来源产品框不存在")
        if not (await permitted(db, actor, "split", parent.order_id) or await permitted(db, actor, "supervise", parent.order_id)):
            raise QrError(403, "FORBIDDEN", "当前账号不能为该来源框核对子标签")
        await source_partition(db, parent)
        child = await resolve_pool(db, qr_payload)
        if child.pool_status != "unused":
            raise QrError(409, "QR_ALREADY_BOUND", "子框二维码已被使用，请更换未绑定标签")
        await record_scan(db, actor.id, child, ScanOperation.QUERY)
        return {"pool_item": pool_info(child), "box": None, "allowed_actions": [], "latest_event": None}
    item = await resolve_pool(db, qr_payload)
    box = (await db.execute(select(m.ProductBox).where(m.ProductBox.qr_pool_item_id == item.id))).scalar_one_or_none()
    if box:
        await permissions.require_action(db, actor, "trace", order_id=box.order_id)
        if context_id is not None:
            from app.services.product_conversion_service import scan_trigger
            await scan_trigger(db, actor, box, context_id)
        db.add(m.ProductFlowEvent(product_box_id=box.id, event_type="scan", order_id=box.order_id,
            order_product_id=box.order_product_id, operator_id=actor.id,
            before_qty=box.current_qty, after_qty=box.current_qty, box_version=box.version))
        actions = ["trace"]
    else:
        if actor.dept == "sales" and actor.role_level < 3:
            raise QrError(403, "FORBIDDEN", "未绑定二维码尚无订单归属")
        caps = await permissions.capabilities(db, actor)
        actions = ["bind"] if ((actor.dept == "warehouse" and "qr.bind" in caps)
                               or (actor.dept == "prod" and "qr.production" in caps)) else []
    await record_scan(db, actor.id, item, ScanOperation.QUERY)
    from app.services.product_conversion_service import options as conversion_options
    return {"pool_item": pool_info(item, box.id if box else None),
            "box": box_info(box, item) if box else None, "allowed_actions": actions,
            "conversion": await conversion_options(db, actor, box) if box else None,
            "latest_event": await latest_event(db, box.id) if box else None}
