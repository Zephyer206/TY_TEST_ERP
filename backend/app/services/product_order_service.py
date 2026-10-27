"""Atomic QR order configuration; existing boxes retain their published route."""
from copy import deepcopy

from sqlalchemy import func, select

from app.models import product_box as m
from app.models.audit import AuditAction
from app.models.machine import Machine
from app.models.part import Part
from app.models.production import PlanMachineAssignment, ProductionPlan
from app.models.user import User
from app.services import qr_permission_service as permissions
from app.services.product_box_service import order_qr_context
from app.services.qr_transaction_service import (
    QrError, advisory_lock, check_version, lock_rows, transactional_write, write_audit,
)


def invalid(message="订单配置无效"):
    raise QrError(400, "INVALID_PRODUCT", message)


def integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 2_147_483_647:
        invalid("数量和既有实体编号必须为有效整数")
    return value


def new_id(value):
    if type(value) is int and 0 < value <= 9_223_372_036_854_775_807:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and value[0:1] != "0":
        parsed = int(value)
        if parsed <= 9_223_372_036_854_775_807:
            return parsed
    invalid("新记录编号格式无效")


def fields(data, allowed, required=()):
    if not isinstance(data, dict) or set(data) - set(allowed) or set(required) - set(data):
        invalid("配置字段不完整或包含不允许的内容")


def word(value, limit=50):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > limit:
        invalid("配置名称或代码无效")
    return value


async def save_order_qr_context(db, actor, *, order_id, business_owner_id, products,
                                machine_process_targets, expected_version, idempotency_key):
    await permissions.require_action(db, actor, "configure", order_id=order_id, lock=True)
    payload = dict(order_id=order_id, business_owner_id=business_owner_id, products=products,
                   machine_process_targets=machine_process_targets, expected_version=expected_version)

    async def operation():
        await advisory_lock(db, "qr-order-configuration", order_id)
        plan = await db.scalar(select(ProductionPlan).where(ProductionPlan.id == order_id).with_for_update())
        if plan is None:
            raise QrError(404, "ENTITY_NOT_FOUND", "订单不存在")
        if str(plan.status).lower() in {"closed", "cancelled", "completed"}:
            raise QrError(409, "STATE_CONFLICT", "订单已经关闭，不能更改生产配置")
        context = await db.scalar(select(m.ProductOrderContext).where(m.ProductOrderContext.order_id == order_id))
        check_version(context.version if context else 0, expected_version, code="STATE_CONFLICT")
        existing = list((await db.scalars(select(m.ProductOrderProduct).where(
            m.ProductOrderProduct.order_id == order_id).order_by(m.ProductOrderProduct.id))).all())
        if existing:
            existing = list((await lock_rows(db, order_products=[p.id for p in existing]))["order_products"].values())
        owner = await db.get(User, integer(business_owner_id, 1))
        if owner is None or owner.dept != "sales" or owner.role_level < 2:
            invalid("业务负责人须为有效业务部门LV2以上账号")
        if not isinstance(products, list) or not products or len(products) > 20:
            invalid("请配置实际产品")
        if not isinstance(machine_process_targets, list) or not machine_process_targets:
            invalid("请明确每道工艺的机台目标量")
        assignments = {a.id: a for a in (await db.scalars(select(PlanMachineAssignment).where(
            PlanMachineAssignment.plan_id == order_id, PlanMachineAssignment.is_active.is_(True)))).all()}
        machines = {machine.id: machine for machine in (await db.scalars(select(Machine).where(
            Machine.id.in_([a.machine_id for a in assignments.values()]), Machine.is_deleted.is_(False)))).all()}
        allowed_parts = {plan.part_id}
        if plan.is_left_right_pair:
            allowed_parts.add(plan.paired_part_id)
        normalized, seen_ids, direct_parts, identities = {}, set(), set(), set()
        by_id = {p.id: p for p in existing}
        for product in deepcopy(products):
            fields(product, {"key", "id", "part_id", "product_code", "target_qty", "binding_allowed",
                "conversion_source_key", "route", "pre_authorized_conversions"},
                {"key", "part_id", "product_code", "target_qty", "route"})
            key = word(product["key"])
            if key in normalized:
                invalid("实际产品引用重复")
            identity = integer(product["part_id"], 1), product["product_code"]
            if identity[1] not in ("B", "C") or identity in identities:
                invalid("实际产品只能为不重复的B或C")
            identities.add(identity)
            part = await db.get(Part, identity[0])
            if part is None or part.is_deleted:
                invalid("件号不存在或已停用")
            direct = product.get("binding_allowed", True)
            if type(direct) is not bool:
                invalid()
            qty = integer(product["target_qty"], 1 if direct else 0)
            if direct:
                if part.id not in allowed_parts or product.get("conversion_source_key"):
                    invalid("直接产品须属于计划主件或配对件")
                direct_parts.add(part.id)
            elif qty != 0 or not product.get("conversion_source_key"):
                invalid("转换目标须显式关联来源且不占直接订单需求")
            stored = None
            if "id" in product:
                stored = by_id.get(new_id(product["id"]))
                if stored is None or stored.id in seen_ids:
                    invalid("配置产品不属于该订单或重复引用")
                seen_ids.add(stored.id)
                if (stored.part_id, stored.product_code, stored.binding_allowed) != (*identity, direct):
                    raise QrError(409, "STATE_CONFLICT", "既有产品身份不可替换")
                allocated = await db.scalar(select(func.coalesce(func.sum(m.ProductOutputAllocation.order_qty), 0)).where(
                    m.ProductOutputAllocation.order_product_id == stored.id))
                if allocated > qty:
                    raise QrError(409, "STATE_CONFLICT", "目标量不能小于已分配订单数量")
            route = product["route"]
            fields(route, {"route_code", "revision", "steps", "first_output_process_code"},
                {"route_code", "revision", "steps", "first_output_process_code"})
            word(route["route_code"], 80)
            integer(route["revision"], 1)
            if not isinstance(route["steps"], list) or not 1 <= len(route["steps"]) <= 100:
                invalid("请提供完整有序工艺路线")
            codes = []
            for step in route["steps"]:
                fields(step, {"code", "name", "machine_ids", "machine_types"}, {"code"})
                codes.append(word(step["code"]))
                if "name" in step:
                    word(step["name"], 200)
                ids, types = step.get("machine_ids", []), step.get("machine_types", [])
                if not isinstance(ids, list) or not isinstance(types, list) or not (ids or types):
                    invalid("工艺必须限制实际机台或机台类型")
                for mid in ids:
                    integer(mid, 1)
                for machine_type in types:
                    word(machine_type)
                for restriction in ("machine_ids", "machine_types"):
                    if not step.get(restriction):
                        step.pop(restriction, None)
            if len(codes) != len(set(codes)) or route["first_output_process_code"] not in codes:
                invalid("工艺步骤或首次产出工艺无效")
            normalized[key] = dict(data=product, stored=stored, codes=codes, direct=direct, qty=qty)
        if seen_ids != set(by_id) or direct_parts != allowed_parts or None in allowed_parts:
            invalid("配置须保留全部既有产品，并覆盖主件及配对件")
        totals, targets, target_keys = {}, [], set()
        for target in machine_process_targets:
            fields(target, {"product_key", "assignment_id", "process_code", "target_qty"},
                {"product_key", "assignment_id", "process_code", "target_qty"})
            product = normalized.get(target["product_key"])
            assignment = assignments.get(integer(target["assignment_id"], 1))
            machine = machines.get(assignment.machine_id) if assignment else None
            code = target["process_code"]
            if not product or not machine or code not in product["codes"]:
                invalid("机台分配与产品工艺不匹配")
            step = next(s for s in product["data"]["route"]["steps"] if s["code"] == code)
            if machine.id not in step.get("machine_ids", []) and machine.machine_type not in step.get("machine_types", []):
                invalid("机台不能执行所配置工艺")
            identity = target["product_key"], assignment.id, code
            if identity in target_keys:
                invalid("机台工艺目标重复")
            target_keys.add(identity)
            qty = integer(target["target_qty"])
            totals[(target["product_key"], code)] = totals.get((target["product_key"], code), 0) + qty
            targets.append((target, product))
        for key, product in normalized.items():
            if any(totals.get((key, code)) != product["qty"] for code in product["codes"]):
                invalid("各工艺机台份额之和须等于该实际产品目标量")
            source_key = product["data"].get("conversion_source_key")
            if not product["direct"] and (source_key not in normalized or not normalized[source_key]["direct"]
                    or normalized[source_key]["data"]["product_code"] == product["data"]["product_code"]):
                invalid("转换来源须为本订单的另一实际产品")
        now = await db.scalar(select(func.clock_timestamp()))
        # All preflight validation above is read-only. Nested transaction also
        # rolls back route publication and all following writes on any failure.
        for product in normalized.values():
            data, route_data = product["data"], product["data"]["route"]
            route = await db.scalar(select(m.ProductRouteRevision).where(
                m.ProductRouteRevision.route_code == route_data["route_code"],
                m.ProductRouteRevision.revision == route_data["revision"]))
            if route:
                if (route.product_code != data["product_code"] or route.steps_json != route_data["steps"]
                        or route.first_output_process_code != route_data["first_output_process_code"] or not route.is_published):
                    raise QrError(409, "STATE_CONFLICT", "已发布路线不可覆盖，请创建新版本")
            else:
                route = m.ProductRouteRevision(route_code=route_data["route_code"], revision=route_data["revision"],
                    product_code=data["product_code"], steps_json=route_data["steps"],
                    first_output_process_code=route_data["first_output_process_code"], is_published=True, created_by=actor.id)
                db.add(route)
                await db.flush()
            stored = product["stored"]
            if stored is None:
                stored = m.ProductOrderProduct(order_id=order_id, part_id=data["part_id"], product_code=data["product_code"],
                    target_qty=product["qty"], route_revision_id=route.id, binding_allowed=True, configured_by=actor.id)
                # Insert conversion targets only after resolving their source.
                product["stored"] = stored
            else:
                stored.target_qty, stored.route_revision_id, stored.configured_by = product["qty"], route.id, actor.id
                stored.version += 1
            product["route"] = route
        for product in sorted(normalized.values(), key=lambda p: not p["direct"]):
            stored, data = product["stored"], product["data"]
            if not product["direct"]:
                stored.binding_allowed = False
                stored.conversion_source_id = normalized[data["conversion_source_key"]]["stored"].id
            db.add(stored)
            await db.flush()
        for product in normalized.values():
            authorizations = []
            requests = product["data"].get("pre_authorized_conversions", [])
            if not isinstance(requests, list):
                invalid("转换预授权须为明确目标列表")
            for authorization in requests:
                fields(authorization, {"target_key", "difference_process_codes"}, {"target_key", "difference_process_codes"})
                target = normalized.get(authorization["target_key"])
                difference = [code for code in target["codes"] if code not in product["codes"]] if target else []
                if (not product["direct"] or not target or target["direct"] or target["data"].get("conversion_source_key") != product["data"]["key"]
                        or not difference or authorization["difference_process_codes"] != difference):
                    invalid("预授权必须精确对应转换目标及差异工艺")
                authorizations.append(dict(target_order_product_id=str(target["stored"].id),
                    source_route_revision_id=str(product["route"].id), target_route_revision_id=str(target["route"].id),
                    difference_process_codes=difference, authorized_by=actor.id, authorized_at=now.isoformat()))
            product["stored"].conversion_authorization = {"targets": authorizations}
        for target, product in targets:
            state = await db.scalar(select(m.MachineOrderProcessState).where(
                m.MachineOrderProcessState.assignment_id == target["assignment_id"],
                m.MachineOrderProcessState.order_product_id == product["stored"].id,
                m.MachineOrderProcessState.route_revision_id == product["route"].id,
                m.MachineOrderProcessState.process_code == target["process_code"]).with_for_update())
            if state:
                if state.target_qty != target["target_qty"]:
                    if state.production_status != "pending":
                        raise QrError(409, "STATE_CONFLICT", "已经生产的工艺目标不能直接改写")
                    state.target_qty, state.version = target["target_qty"], state.version + 1
            else:
                db.add(m.MachineOrderProcessState(assignment_id=target["assignment_id"], order_product_id=product["stored"].id,
                    route_revision_id=product["route"].id, process_code=target["process_code"], target_qty=target["target_qty"]))
        if context:
            context.business_owner_id, context.version, context.configured_by = business_owner_id, context.version + 1, actor.id
        else:
            db.add(m.ProductOrderContext(order_id=order_id, business_owner_id=business_owner_id, configured_by=actor.id))
        await db.flush()
        result = await order_qr_context(db, actor, order_id=order_id)
        await write_audit(db, actor.id, AuditAction.UPDATE, f"order-configuration:{order_id}", after=result)
        return result

    return await transactional_write(db, actor.id, "order-configuration", f"order:{order_id}",
        idempotency_key, payload, operation)
