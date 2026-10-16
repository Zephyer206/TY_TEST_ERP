"""Transactional service for the shipping-order workflow."""

from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditAction, AuditLog
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.shipping_order import (
    ShippingCancellationConsent, ShippingLabelConfirmation, ShippingLogistics,
    ShippingOrder, ShippingOrderLine, ShippingShipment, ShippingShipmentLine,
)
from app.models.packaging import Inventory, InventoryTransaction
from app.models.user import User


class ShippingWarning(Exception):
    def __init__(self, code: str, message: str, details: list[dict]):
        self.code, self.message, self.details = code, message, details
        super().__init__(message)


class InventoryShortage(Exception):
    def __init__(self, details: list[dict]):
        self.details = details
        super().__init__("正式库存不足，无法预占")


def _audit_action(action: str) -> AuditAction:
    return {
        "create": AuditAction.CREATE,
        "update": AuditAction.UPDATE,
        "submit": AuditAction.SUBMIT,
        "cancel": AuditAction.CANCEL,
        "delete": AuditAction.DELETE,
        "confirm": AuditAction.APPROVE,
        "approve": AuditAction.APPROVE,
    }.get(action, AuditAction.UPDATE)


async def write_audit(db: AsyncSession, *, action: str, entity_type: str, entity_id: Optional[int], user: User, summary: str = "", old: Optional[dict] = None, new: Optional[dict] = None) -> None:
    db.add(AuditLog(action=_audit_action(action), entity_type=entity_type, entity_id=entity_id, user_id=user.id, username=user.username, changes_summary=summary, old_values=old, new_values=new))


def shipped_qty(line: ShippingOrderLine) -> int:
    return sum(int(item.qty) for item in (line.shipment_lines or []))


def remaining_qty(line: ShippingOrderLine) -> int:
    return max(0, int(line.ordered_qty) - shipped_qty(line) - int(line.cancelled_qty or 0))


async def _lock_inventory_rows(db: AsyncSession, part_ids: Sequence[int]) -> dict[int, Inventory]:
    ids = list(dict.fromkeys(int(part_id) for part_id in part_ids if part_id is not None))
    if not ids:
        return {}
    rows = (await db.execute(
        select(Inventory).where(Inventory.part_id.in_(ids)).with_for_update()
    )).scalars().all()
    return {row.part_id: row for row in rows}


async def _record_inventory_event(
    db: AsyncSession,
    inventory: Inventory,
    *,
    transaction_type: str,
    quantity: int,
    reference_type: str,
    reference_id: int,
    operator_id: int,
    reason: str,
) -> None:
    db.add(InventoryTransaction(
        part_id=inventory.part_id,
        transaction_type=transaction_type,
        quantity=quantity,
        stock_before=inventory.stock_qty,
        stock_after=inventory.stock_qty,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        operator_id=operator_id,
    ))


async def inventory_snapshot(db: AsyncSession, part_id: Optional[int]) -> Optional[Inventory]:
    if part_id is None:
        return None
    return (await db.execute(select(Inventory).where(Inventory.part_id == part_id))).scalar_one_or_none()


async def reserve_order_inventory(db: AsyncSession, order: ShippingOrder, user: User) -> None:
    """Reserve formal-order quantities atomically against verified inventory."""
    if order.order_type != "formal":
        return
    missing_part_lines = [line.id for line in order.lines if line.part_id is None]
    if missing_part_lines:
        raise ValueError("INVENTORY_PART_REQUIRED")
    requested: dict[int, int] = {}
    for line in order.lines:
        requested[line.part_id] = requested.get(line.part_id, 0) + int(line.ordered_qty)
    inventories = await _lock_inventory_rows(db, list(requested))
    shortages: list[dict] = []
    for part_id, qty in requested.items():
        inventory = inventories.get(part_id)
        available = (inventory.stock_qty - inventory.reserved_qty) if inventory else 0
        if inventory is None or available < qty:
            shortages.append({"part_id": part_id, "requested_qty": qty, "stock_qty": inventory.stock_qty if inventory else 0, "reserved_qty": inventory.reserved_qty if inventory else 0, "available_qty": available})
    if shortages:
        raise InventoryShortage(shortages)
    for part_id, qty in requested.items():
        inventory = inventories[part_id]
        inventory.reserved_qty += qty
        inventory.last_update_by = user.id
        inventory.last_update_at = datetime.utcnow()
        await _record_inventory_event(db, inventory, transaction_type="reserve", quantity=0, reference_type="shipping_order", reference_id=order.id, operator_id=user.id, reason=f"订单提交预占 {qty} 件")


async def release_inventory_for_lines(db: AsyncSession, line_quantities: dict[int, int], order: ShippingOrder, user: User, reason: str) -> None:
    """Release reservations for order lines; caller has validated quantities."""
    lines = (await db.execute(select(ShippingOrderLine).where(ShippingOrderLine.id.in_(list(line_quantities))))).scalars().all() if line_quantities else []
    by_part: dict[int, int] = {}
    for line in lines:
        if line.part_id is not None:
            by_part[line.part_id] = by_part.get(line.part_id, 0) + int(line_quantities.get(line.id, 0))
    inventories = await _lock_inventory_rows(db, list(by_part))
    for part_id, qty in by_part.items():
        inventory = inventories.get(part_id)
        if inventory is None or inventory.reserved_qty < qty:
            raise ValueError("INVENTORY_RESERVATION_MISMATCH")
        inventory.reserved_qty -= qty
        inventory.last_update_by = user.id
        inventory.last_update_at = datetime.utcnow()
        await _record_inventory_event(db, inventory, transaction_type="unreserve", quantity=0, reference_type="shipping_order", reference_id=order.id, operator_id=user.id, reason=reason)


async def deduct_shipped_inventory(db: AsyncSession, line_quantities: dict[int, int], order: ShippingOrder, user: User) -> None:
    lines = (await db.execute(select(ShippingOrderLine).where(ShippingOrderLine.id.in_(list(line_quantities))))).scalars().all() if line_quantities else []
    by_part: dict[int, int] = {}
    for line in lines:
        if line.part_id is not None:
            by_part[line.part_id] = by_part.get(line.part_id, 0) + int(line_quantities.get(line.id, 0))
    inventories = await _lock_inventory_rows(db, list(by_part))
    shortages: list[dict] = []
    for part_id, qty in by_part.items():
        inventory = inventories.get(part_id)
        if inventory is None or inventory.stock_qty < qty or inventory.reserved_qty < qty:
            shortages.append({"part_id": part_id, "requested_qty": qty, "stock_qty": inventory.stock_qty if inventory else 0, "reserved_qty": inventory.reserved_qty if inventory else 0})
    if shortages:
        raise InventoryShortage(shortages)
    for part_id, qty in by_part.items():
        inventory = inventories[part_id]
        stock_before = inventory.stock_qty
        inventory.stock_qty -= qty
        inventory.reserved_qty -= qty
        inventory.last_update_by = user.id
        inventory.last_update_at = datetime.utcnow()
        await db.execute(update(Part).where(Part.id == part_id).values(stock_pcs=inventory.stock_qty, updated_at=datetime.utcnow()))
        db.add(InventoryTransaction(part_id=part_id, transaction_type="outgoing", quantity=-qty, stock_before=stock_before, stock_after=inventory.stock_qty, reference_type="shipping_order", reference_id=order.id, reason="订单发货扣减库存", operator_id=user.id))


def shipment_totals(lines: Iterable) -> dict[int, int]:
    """Aggregate repeated line entries before checking shipment remainder."""
    totals: dict[int, int] = {}
    for item in lines:
        totals[item.order_line_id] = totals.get(item.order_line_id, 0) + int(item.qty)
    return totals


def derive_line_status(line: ShippingOrderLine, submitted: bool = True) -> str:
    shipped = shipped_qty(line)
    remaining = remaining_qty(line)
    if not submitted:
        return "draft"
    if remaining == 0 and shipped == 0:
        return "cancelled"
    if shipped == line.ordered_qty:
        return "shipped"
    if shipped > 0 and remaining == 0:
        return "partially_shipped_remaining_cancelled"
    if shipped > 0:
        return "partially_shipped"
    if line.label_confirmation:
        return "ready_to_ship"
    return "awaiting_label"


def derive_order_status(order: ShippingOrder) -> str:
    if order.status == "draft":
        return "draft"
    statuses = [derive_line_status(line) for line in order.lines]
    if statuses and all(s == "cancelled" for s in statuses):
        return "cancelled"
    if statuses and all(s in {"shipped", "cancelled", "partially_shipped_remaining_cancelled"} for s in statuses):
        return "completed_with_cancellation" if any(s != "shipped" for s in statuses) else "completed"
    if any(s in {"partially_shipped", "partially_shipped_remaining_cancelled"} for s in statuses):
        return "partially_shipped"
    if any(s == "ready_to_ship" for s in statuses):
        return "ready_to_ship"
    return "pending"


async def load_order(db: AsyncSession, order_id: int) -> Optional[ShippingOrder]:
    q = select(ShippingOrder).where(ShippingOrder.id == order_id).options(
        selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.shipment_lines),
        selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.label_confirmation),
        selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.cancellation_consents),
        selectinload(ShippingOrder.shipments).selectinload(ShippingShipment.lines),
        selectinload(ShippingOrder.shipments).selectinload(ShippingShipment.logistics),
    )
    return (await db.execute(q)).scalar_one_or_none()


def _order_no() -> str:
    return f"SO-{datetime.utcnow():%Y%m%d%H%M%S%f}"[-22:]


async def create_draft(db: AsyncSession, payload, user: User) -> ShippingOrder:
    order = ShippingOrder(order_no=_order_no(), order_type=payload.order_type, customer_id=payload.customer_id, temporary_customer_name=payload.temporary_customer_name, po_no=payload.po_no, status="draft", created_by=user.id)
    for item in payload.lines:
        order.lines.append(ShippingOrderLine(part_id=item.part_id, part_customer_alias_id=item.part_customer_alias_id, customer_part_no_snapshot=item.customer_part_no, part_name_snapshot=item.part_name, ordered_qty=item.ordered_qty, planned_ship_date=item.planned_ship_date, remark=item.remark, status="draft"))
    db.add(order)
    await db.flush()
    await write_audit(db, action="create", entity_type="shipping_order", entity_id=order.id, user=user, summary="创建发货订单草稿")
    return order


async def update_draft(db: AsyncSession, order: ShippingOrder, payload, user: User) -> ShippingOrder:
    if order.status != "draft":
        raise ValueError("DRAFT_NOT_EDITABLE")
    order.order_type, order.customer_id, order.temporary_customer_name, order.po_no = payload.order_type, payload.customer_id, payload.temporary_customer_name, payload.po_no
    order.last_modified_at = datetime.utcnow()
    order.lines.clear()
    for item in payload.lines:
        order.lines.append(ShippingOrderLine(part_id=item.part_id, part_customer_alias_id=item.part_customer_alias_id, customer_part_no_snapshot=item.customer_part_no, part_name_snapshot=item.part_name, ordered_qty=item.ordered_qty, planned_ship_date=item.planned_ship_date, remark=item.remark, status="draft"))
    await db.flush()
    await write_audit(db, action="update", entity_type="shipping_order", entity_id=order.id, user=user, summary="修改发货订单草稿")
    return order


async def customer_part_search(db: AsyncSession, customer_id: int, q: str) -> list[tuple[PartCustomerAlias, Part]]:
    stmt = select(PartCustomerAlias, Part, Inventory).join(Part, Part.id == PartCustomerAlias.part_id).outerjoin(Inventory, Inventory.part_id == Part.id).where(PartCustomerAlias.customer_id == customer_id, PartCustomerAlias.is_active.is_(True), PartCustomerAlias.customer_part_no.ilike(f"%{q}%"), Part.is_deleted.is_(False)).order_by(PartCustomerAlias.customer_part_no).limit(50)
    return list((await db.execute(stmt)).all())


async def submit_order(db: AsyncSession, order: ShippingOrder, payload, user: User) -> ShippingOrder:
    if order.status != "draft":
        raise ValueError("DRAFT_NOT_EDITABLE")
    if order.order_type == "formal" and (not order.customer_id or not (order.po_no or "").strip()):
        raise ValueError("FORMAL_CUSTOMER_PO_REQUIRED")
    if order.order_type == "sample" and not (order.customer_id or (order.temporary_customer_name or "").strip()):
        raise ValueError("SAMPLE_CUSTOMER_REQUIRED")
    if not order.lines:
        raise ValueError("ORDER_LINES_REQUIRED")
    if any(line.ordered_qty <= 0 for line in order.lines):
        raise ValueError("INVALID_ORDER_QTY")
    if any(line.planned_ship_date < date.today() for line in order.lines):
        raise ValueError("INVALID_PLANNED_DATE")
    if any(not line.customer_part_no_snapshot.strip() or not line.part_name_snapshot.strip() for line in order.lines):
        raise ValueError("INVALID_ORDER_LINE")
    warnings: list[dict] = []
    if order.customer_id and order.po_no:
        duplicate = (await db.execute(select(ShippingOrder).where(ShippingOrder.id != order.id, ShippingOrder.customer_id == order.customer_id, ShippingOrder.po_no == order.po_no, ShippingOrder.status != "cancelled").order_by(ShippingOrder.created_at.desc()))).scalars().all()
        warnings.extend({"order_id": x.id, "order_no": x.order_no, "status": x.status, "created_at": x.created_at.isoformat()} for x in duplicate)
    unknown = []
    if order.customer_id:
        for line in order.lines:
            found = await db.scalar(select(PartCustomerAlias.id).where(PartCustomerAlias.customer_id == order.customer_id, PartCustomerAlias.customer_part_no == line.customer_part_no_snapshot, PartCustomerAlias.is_active.is_(True)))
            if not found:
                unknown.append({"line_id": line.id, "customer_part_no": line.customer_part_no_snapshot})
    if warnings and not payload.confirm_duplicate_po:
        raise ShippingWarning("DUPLICATE_CUSTOMER_PO", "该客户和PO号已有订单，请确认是否继续提交。", warnings)
    if unknown and not payload.confirm_unregistered_customer_parts:
        raise ShippingWarning("UNREGISTERED_CUSTOMER_PARTS", "该客户件号在零件档案中找不到，请确认是否继续提交。", unknown)
    await reserve_order_inventory(db, order, user)
    now = datetime.utcnow()
    order.status, order.submitted_at, order.last_modified_at = "pending", now, now
    for line in order.lines:
        line.status = "awaiting_label"
    await db.flush()
    await write_audit(db, action="submit", entity_type="shipping_order", entity_id=order.id, user=user, summary="提交发货订单")
    return order


async def confirm_label(db: AsyncSession, line: ShippingOrderLine, user: User, remark: Optional[str] = None) -> ShippingLabelConfirmation:
    if not line.order or line.order.status == "draft":
        raise ValueError("order is not submitted")
    if line.label_confirmation:
        return line.label_confirmation
    confirmation = ShippingLabelConfirmation(order_line_id=line.id, confirmed_by=user.id, remark=remark)
    db.add(confirmation)
    line.status = "ready_to_ship"
    await db.flush()
    await write_audit(db, action="confirm", entity_type="shipping_label_confirmation", entity_id=confirmation.id, user=user, summary="标签确认")
    return confirmation


async def promote_formal_lines_from_qualified_inventory(
    db: AsyncSession,
    qualified_line_ids: Sequence[int],
    user: User,
    source_reference: Optional[str] = None,
) -> list[ShippingOrderLine]:
    """Promote formal lines after an external inventory/QC system proves them qualified.

    This is deliberately an integration boundary: the caller owns the packaging,
    full-inspection and inventory decision. The shipping domain only records the
    existing label-gate confirmation so the line can enter ``ready_to_ship``;
    inventory reservation or deduction is not performed here.
    """
    ids = list(dict.fromkeys(int(item) for item in qualified_line_ids))
    if not ids:
        return []
    lines = list((await db.execute(
        select(ShippingOrderLine)
        .where(ShippingOrderLine.id.in_(ids))
        .options(selectinload(ShippingOrderLine.order), selectinload(ShippingOrderLine.label_confirmation))
    )).scalars().all())
    by_id = {line.id: line for line in lines}
    missing = [line_id for line_id in ids if line_id not in by_id]
    if missing:
        raise ValueError("INVENTORY_LINE_NOT_FOUND")
    promoted: list[ShippingOrderLine] = []
    remark = "合格成品库存进入标签/待发货路径"
    if source_reference:
        remark = f"{remark}（来源：{source_reference}）"
    for line_id in ids:
        line = by_id[line_id]
        if line.order.order_type != "formal" or line.order.status == "draft":
            raise ValueError("FORMAL_INVENTORY_LINE_REQUIRED")
        await confirm_label(db, line, user, remark)
        promoted.append(line)
    return promoted


async def withdraw(db: AsyncSession, order: ShippingOrder, user: User) -> ShippingOrder:
    if any(line.label_confirmation for line in order.lines):
        raise ValueError("TAGGED_LINE_CANNOT_WITHDRAW")
    if order.status != "draft":
        await release_inventory_for_lines(
            db,
            {line.id: remaining_qty(line) for line in order.lines if remaining_qty(line) > 0},
            order,
            user,
            "订单撤回，释放未发货预占",
        )
    order.status, order.submitted_at, order.last_modified_at = "draft", None, datetime.utcnow()
    for line in order.lines:
        line.status = "draft"
    await write_audit(db, action="update", entity_type="shipping_order", entity_id=order.id, user=user, summary="撤回到草稿")
    return order


def actor_kind(user: User) -> str:
    dept = (user.dept or "").lower()
    position = (user.position or "").lower()
    if any(token in f"{dept} {position}" for token in ("label", "标签", "warehouse", "仓库")):
        return "label"
    return "business"


async def cancel_line(db: AsyncSession, line: ShippingOrderLine, request, user: User):
    if request.cancel_qty > remaining_qty(line):
        raise ValueError("cancel quantity exceeds remaining quantity")
    if not line.label_confirmation:
        await release_inventory_for_lines(db, {line.id: request.cancel_qty}, line.order, user, "订单明细取消，释放预占")
        line.cancelled_qty += request.cancel_qty
        line.status = derive_line_status(line)
        await write_audit(db, action="cancel", entity_type="shipping_order_line", entity_id=line.id, user=user, summary=request.reason, new={"cancel_qty": request.cancel_qty})
        return None
    consent = ShippingCancellationConsent(order_line_id=line.id, cancel_qty=request.cancel_qty, reason=request.reason)
    if actor_kind(user) == "business":
        consent.business_confirmed_by, consent.business_confirmed_at = user.id, datetime.utcnow()
    else:
        consent.label_confirmed_by, consent.label_confirmed_at = user.id, datetime.utcnow()
    db.add(consent)
    await db.flush()
    await write_audit(
        db,
        action="cancel",
        entity_type="shipping_cancellation_consent",
        entity_id=consent.id,
        user=user,
        summary="创建取消申请",
        new={"cancel_qty": consent.cancel_qty, "reason": consent.reason, "status": consent.status},
    )
    return consent


async def add_cancellation_consent(db: AsyncSession, consent: ShippingCancellationConsent, user: User) -> ShippingCancellationConsent:
    kind = actor_kind(user)
    now = datetime.utcnow()
    if kind == "business":
        if consent.business_confirmed_by:
            raise ValueError("already confirmed")
        consent.business_confirmed_by, consent.business_confirmed_at = user.id, now
        await write_audit(db, action="cancel", entity_type="shipping_cancellation_consent", entity_id=consent.id, user=user, summary="业务确认取消申请", new={"business_confirmed_by": user.id})
    else:
        if consent.label_confirmed_by:
            raise ValueError("already confirmed")
        consent.label_confirmed_by, consent.label_confirmed_at = user.id, now
        await write_audit(db, action="cancel", entity_type="shipping_cancellation_consent", entity_id=consent.id, user=user, summary="标签确认取消申请", new={"label_confirmed_by": user.id})
    if consent.business_confirmed_by and consent.label_confirmed_by:
        line = consent.line
        if consent.cancel_qty > remaining_qty(line):
            raise ValueError("cancel quantity exceeds remaining quantity")
        # State-only callers may provide a lightweight line substitute without
        # ORM identity/order links. Real cancellation rows always have both.
        line_id = getattr(line, "id", None)
        order = getattr(line, "order", None)
        if line_id is not None and order is not None:
            await release_inventory_for_lines(db, {line_id: consent.cancel_qty}, order, user, "取消申请完成，释放预占")
        line.cancelled_qty += consent.cancel_qty
        line.status = derive_line_status(line)
        consent.status, consent.completed_at = "completed", now
        await write_audit(db, action="cancel", entity_type="shipping_cancellation_consent", entity_id=consent.id, user=user, summary=consent.reason, new={"cancel_qty": consent.cancel_qty})
    await db.flush()
    return consent


async def confirm_shipment(db: AsyncSession, order: ShippingOrder, payload, user: User) -> ShippingShipment:
    # Lock the order and every requested line so concurrent warehouse actions
    # cannot both pass the remaining-quantity check.
    await db.execute(select(ShippingOrder.id).where(ShippingOrder.id == order.id).with_for_update())
    requested_totals = shipment_totals(payload.lines)
    requested_ids = list(requested_totals)
    locked_lines = list((await db.execute(
        select(ShippingOrderLine)
        .where(ShippingOrderLine.order_id == order.id, ShippingOrderLine.id.in_(requested_ids))
        .options(selectinload(ShippingOrderLine.label_confirmation), selectinload(ShippingOrderLine.shipment_lines))
        .with_for_update()
    )).scalars().all())
    locked_by_id = {line.id: line for line in locked_lines}
    unknown = []
    for line_id, requested_qty in requested_totals.items():
        line = locked_by_id.get(line_id)
        if not line:
            raise ValueError("order line not found")
        if not line.label_confirmation:
            raise ValueError("LINE_NOT_READY_TO_SHIP")
        if requested_qty > remaining_qty(line):
            raise ValueError("INVALID_SHIPMENT_QTY")
        if order.customer_id:
            found = await db.scalar(select(PartCustomerAlias.id).where(PartCustomerAlias.customer_id == order.customer_id, PartCustomerAlias.customer_part_no == line.customer_part_no_snapshot, PartCustomerAlias.is_active.is_(True)))
            if not found:
                unknown.append({"line_id": line.id, "customer_part_no": line.customer_part_no_snapshot})
    if unknown and not getattr(payload, "confirm_unregistered_customer_parts", False):
        raise ShippingWarning("UNREGISTERED_CUSTOMER_PARTS", "该客户件号在零件档案中找不到，请确认是否继续发货。", unknown)
    await deduct_shipped_inventory(db, requested_totals, order, user)
    shipment = ShippingShipment(shipment_no=f"DN-{datetime.utcnow():%Y%m%d%H%M%S%f}"[-22:], order_id=order.id, confirmed_by=user.id, production_batch_no=payload.production_batch_no, remark=payload.remark)
    shipment.lines = [ShippingShipmentLine(order_line_id=line_id, qty=qty) for line_id, qty in requested_totals.items()]
    shipment.logistics = [ShippingLogistics(carrier_name=x.carrier_name, tracking_no=x.tracking_no, created_by=user.id) for x in payload.logistics]
    db.add(shipment)
    await db.flush()
    for line in locked_lines:
        line.status = derive_line_status(line)
    order.status = derive_order_status(order)
    if order.status in {"completed", "completed_with_cancellation", "cancelled"}:
        order.completed_at = datetime.utcnow()
    await write_audit(db, action="confirm", entity_type="shipping_shipment", entity_id=shipment.id, user=user, summary="确认已发货")
    return shipment


async def update_logistics(db: AsyncSession, shipment: ShippingShipment, payload, user: User) -> ShippingShipment:
    old = [{"carrier_name": x.carrier_name, "tracking_no": x.tracking_no} for x in shipment.logistics]
    shipment.logistics.clear()
    shipment.logistics.extend(ShippingLogistics(carrier_name=x.carrier_name, tracking_no=x.tracking_no, created_by=user.id) for x in payload.logistics)
    await db.flush()
    new = [{"carrier_name": x.carrier_name, "tracking_no": x.tracking_no} for x in payload.logistics]
    await write_audit(db, action="update", entity_type="shipping_logistics", entity_id=shipment.id, user=user, summary="修改物流信息", old={"logistics": old}, new={"logistics": new})
    return shipment


async def cleanup_drafts(db: AsyncSession, *, now: Optional[datetime] = None, dry_run: bool = False) -> list[int]:
    cutoff = (now or datetime.utcnow()) - timedelta(days=7)
    ids = list((await db.execute(select(ShippingOrder.id).where(ShippingOrder.status == "draft", ShippingOrder.last_modified_at < cutoff))).scalars().all())
    if not dry_run and ids:
        for order_id in ids:
            db.add(AuditLog(action=AuditAction.DELETE, entity_type="shipping_order_cleanup", entity_id=order_id, changes_summary="七天草稿自动清理", extra_data={"cutoff": cutoff.isoformat(), "system": True}))
        await db.execute(ShippingOrder.__table__.delete().where(ShippingOrder.id.in_(ids)))
    return ids
