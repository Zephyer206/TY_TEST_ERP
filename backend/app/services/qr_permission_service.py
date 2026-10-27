"""Product QR department, capability, order and scan-context authorization."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import false, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.models.audit import AuditAction
from app.models.production import PlanMachineAssignment, ProductionPlan
from app.models.user import User
from app.models import product_box as m
from app.services.qr_transaction_service import (
    QrError, check_version, lock_permission_users, transactional_write, write_audit,
)

CAPABILITIES = frozenset({"qr.trace", "qr.production", "qr.split", "qr.print", "qr.bind",
                         "qr.supervise", "qr.generate", "qr.metadata", "qr.configure", "qr.admin"})


def validate_actor(actor: Any) -> None:
    if (not isinstance(getattr(actor, "id", None), int) or actor.id <= 0
            or getattr(actor, "role_level", 0) not in (1, 2, 3, 4)):
        raise QrError(403, "FORBIDDEN", "当前账号无二维码操作权限")


async def capabilities(db: AsyncSession, actor: Any) -> set[str]:
    validate_actor(actor)
    return set((await db.execute(select(m.QrCapabilityGrant.capability).where(
        m.QrCapabilityGrant.user_id == actor.id, m.QrCapabilityGrant.revoked_at.is_(None)
    ))).scalars())


async def visible_order_clause(db: AsyncSession, actor: Any, order_column):
    caps = await capabilities(db, actor)
    if actor.role_level >= 3:
        return true()
    if actor.dept == "sales":
        if actor.role_level < 2:
            return false()
        return order_column.in_(select(m.ProductOrderContext.order_id).where(
            m.ProductOrderContext.business_owner_id == actor.id))
    if actor.dept == "prod" and caps & {"qr.production", "qr.supervise", "qr.trace", "qr.configure", "qr.metadata"}:
        return true()
    if actor.dept == "warehouse" and caps & {"qr.bind", "qr.split", "qr.print", "qr.trace", "qr.metadata"}:
        return true()
    if actor.dept == "quality" and "qr.trace" in caps:
        return true()
    if actor.dept == "engineering" and caps & {"qr.configure", "qr.trace"}:
        return true()
    return false()


async def can_view_order(db: AsyncSession, actor: Any, order_id: int) -> bool:
    clause = await visible_order_clause(db, actor, ProductionPlan.id)
    return await db.scalar(select(ProductionPlan.id).where(ProductionPlan.id == order_id, clause)) is not None


async def require_action(db: AsyncSession, actor: Any, action: str, *, order_id: int | None = None,
                         context_id: int | None = None, order_product_id: int | None = None,
                         lock: bool = False) -> None:
    validate_actor(actor)
    if lock:
        await lock_permission_users(db, actor.id)
    try:
        require_role(actor, min_level=1)
    except HTTPException:
        raise QrError(403, "FORBIDDEN", "当前账号无二维码操作权限") from None
    caps = await capabilities(db, actor)
    production = actor.dept == "prod" and "qr.production" in caps
    supervisor = actor.dept == "prod" and actor.role_level >= 2 and "qr.supervise" in caps
    owner = False
    if order_id is not None and actor.dept == "sales" and actor.role_level >= 2:
        owner = await db.scalar(select(m.ProductOrderContext.id).where(
            m.ProductOrderContext.order_id == order_id, m.ProductOrderContext.business_owner_id == actor.id)) is not None
    admin = actor.role_level == 4 and "qr.admin" in caps
    allowed = {
        "generate": (admin and "qr.generate" in caps) if actor.role_level == 4 else (
            actor.dept == "prod" and actor.role_level >= 2 and "qr.generate" in caps),
        "print": "qr.print" in caps and (actor.role_level == 4 or actor.dept in ("prod", "warehouse")),
        "warehouse_bind": actor.dept == "warehouse" and "qr.bind" in caps,
        "supervise": supervisor or owner,
        "metadata": "qr.metadata" in caps and (actor.dept in ("prod", "warehouse") or owner),
        "split": actor.dept in ("prod", "warehouse") and "qr.split" in caps,
        "configure": admin or (actor.dept in ("prod", "engineering") and actor.role_level >= 2 and "qr.configure" in caps),
        "admin": admin,
        "production_bind": production, "quantity": production, "advance": production,
        "complete": production, "conversion_confirm": production, "create_exception": production,
        "pool_read": actor.role_level >= 3 or (
            actor.dept in ("prod", "warehouse", "quality", "engineering", "sales")
            and bool(caps & {"qr.trace", "qr.production", "qr.bind", "qr.supervise", "qr.print", "qr.generate", "qr.configure", "qr.metadata"})),
        "trace": actor.role_level >= 3 or "qr.trace" in caps or (
            actor.dept == "prod" and bool(caps & {"qr.production", "qr.supervise"})) or (
            actor.dept == "warehouse" and bool(caps & {"qr.bind", "qr.split", "qr.print"})),
    }.get(action, False)
    if not allowed or (order_id is not None and not await can_view_order(db, actor, order_id)):
        raise QrError(403, "FORBIDDEN", "当前账号无此订单的操作权限")
    if action in {"production_bind", "quantity", "advance", "complete", "conversion_confirm", "create_exception"}:
        await require_context(db, actor, context_id, order_id, order_product_id)


async def require_context(db, actor, context_id, order_id, order_product_id):
    if context_id is None:
        raise QrError(409, "STATE_CONFLICT", "请先扫描机台并选择订单")
    context = (await db.execute(select(m.MachineProductionContext).where(
        m.MachineProductionContext.id == context_id,
        m.MachineProductionContext.user_id == actor.id,
        m.MachineProductionContext.closed_at.is_(None),
        m.MachineProductionContext.expires_at > func.clock_timestamp(),
    ))).scalar_one_or_none()
    if context is None or context.state_id is None:
        raise QrError(403, "FORBIDDEN", "扫码上下文不属于当前账号或已失效")
    row = (await db.execute(select(m.MachineOrderProcessState, m.ProductOrderProduct, PlanMachineAssignment)
        .join(m.ProductOrderProduct, m.ProductOrderProduct.id == m.MachineOrderProcessState.order_product_id)
        .join(PlanMachineAssignment, PlanMachineAssignment.id == m.MachineOrderProcessState.assignment_id)
        .where(m.MachineOrderProcessState.id == context.state_id))).one_or_none()
    if (not row or not row[2].is_active or row[2].machine_id != context.machine_id
            or row[2].plan_id != row[1].order_id or row[1].order_id != order_id
            or row[1].id != order_product_id):
        raise QrError(403, "FORBIDDEN", "扫码上下文与机台、订单或产品不匹配")
    route = await db.get(m.ProductRouteRevision, row[0].route_revision_id)
    if (not route or not route.is_published or route.product_code != row[1].product_code
            or row[0].process_code not in [step.get("code") for step in route.steps_json]):
        raise QrError(403, "FORBIDDEN", "扫码上下文工艺路线已失效")
    if row[0].production_status == "completed":
        raise QrError(409, "STATE_CONFLICT", "该机台工艺已完成，请重新扫码选择后续工艺")
    return context, row[0]


async def replace_capabilities(db, actor, user_id, requested, expected_version, idempotency_key):
    validate_actor(actor)
    await lock_permission_users(db, actor.id, user_id)
    await require_action(db, actor, "admin")
    if len(requested) != len(set(requested)) or not set(requested) <= CAPABILITIES:
        raise QrError(400, "INVALID_CAPABILITY", "能力列表包含重复或未知项目")
    if await db.scalar(select(User.id).where(User.id == user_id)) is None:
        raise QrError(404, "ENTITY_NOT_FOUND", "目标账号不存在")

    async def operation():
        record = await db.get(m.QrCapabilitySet, user_id, populate_existing=True)
        check_version(record.version if record else 0, expected_version, code="STATE_CONFLICT")
        old = (await db.execute(select(m.QrCapabilityGrant).where(
            m.QrCapabilityGrant.user_id == user_id, m.QrCapabilityGrant.revoked_at.is_(None)))).scalars().all()
        old_caps = {grant.capability for grant in old}
        for grant in old:
            if grant.capability not in requested:
                grant.revoked_by, grant.revoked_at = actor.id, func.clock_timestamp()
        for cap in sorted(set(requested) - old_caps):
            db.add(m.QrCapabilityGrant(user_id=user_id, capability=cap, granted_by=actor.id))
        if record:
            record.version += 1
        else:
            record = m.QrCapabilitySet(user_id=user_id, version=1)
            db.add(record)
        await write_audit(db, actor.id, AuditAction.UPDATE, f"capabilities:{user_id}",
                          before={"capabilities": sorted(old_caps)}, after={"capabilities": sorted(requested)})
        return {"user_id": user_id, "version": record.version, "capabilities": sorted(requested)}

    return await transactional_write(db, actor.id, "capabilities", f"user:{user_id}", idempotency_key,
        {"capabilities": sorted(requested), "expected_version": expected_version}, operation)


async def list_capabilities(db, actor, *, user_id=None, page=1, page_size=50):
    await require_action(db, actor, "admin")
    query = select(User.id, User.dept, User.role_level).order_by(User.id)
    if user_id is not None:
        query = query.where(User.id == user_id)
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()
    items = []
    for row in rows:
        record = await db.get(m.QrCapabilitySet, row.id)
        caps = set((await db.execute(select(m.QrCapabilityGrant.capability).where(
            m.QrCapabilityGrant.user_id == row.id, m.QrCapabilityGrant.revoked_at.is_(None)))).scalars())
        items.append({"user_id": row.id, "dept": row.dept, "role_level": row.role_level,
                      "version": record.version if record else 0, "capabilities": sorted(caps)})
    return {"items": items, "page": page, "page_size": page_size}
