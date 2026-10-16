"""Shipping order API."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models.audit import AuditLog
from app.models.shipping_order import ShippingCancellationConsent, ShippingOrder, ShippingOrderLine, ShippingShipment
from app.schemas.shipping_order import (
    CancelRequest, CancellationConsentRequest, CancellationConsentResponse, CustomerPartSearchResponse,
    LabelConfirmRequest, LogisticsUpdateRequest, OperationHistoryResponse,
    ShippingLineResponse, ShippingOrderCreate, ShippingOrderListResponse,
    ShippingOrderResponse, ShippingOrderUpdate, ShipmentConfirmRequest,
    ShipmentResponse, SubmitRequest,
)
from app.services.shipping_order_service import (
    InventoryShortage, ShippingWarning, add_cancellation_consent, cancel_line, cleanup_drafts,
    confirm_label, confirm_shipment, customer_part_search, derive_line_status,
    derive_order_status, load_order, remaining_qty, shipped_qty, submit_order,
    update_draft, update_logistics, withdraw, create_draft, write_audit,
)

router = APIRouter(prefix="/shipping-orders", tags=["Shipping Orders"])
contract_router = APIRouter(tags=["Shipping Orders"])


def _line_response(line: ShippingOrderLine) -> ShippingLineResponse:
    shipped, remaining = shipped_qty(line), remaining_qty(line)
    return ShippingLineResponse(
        id=line.id, order_id=line.order_id,
        customer_part_no=line.customer_part_no_snapshot,
        customer_part_no_snapshot=line.customer_part_no_snapshot,
        part_id=line.part_id, part_customer_alias_id=line.part_customer_alias_id,
        part_name=line.part_name_snapshot, part_name_snapshot=line.part_name_snapshot,
        ordered_qty=line.ordered_qty, planned_ship_date=line.planned_ship_date,
        remark=line.remark, status=derive_line_status(line, line.order.status != "draft" if line.order else True),
        cancelled_qty=line.cancelled_qty, shipped_qty=shipped, remaining_qty=remaining,
        label_confirmed=bool(line.label_confirmation), created_at=line.created_at, updated_at=line.updated_at,
        cancellation_consents=[CancellationConsentResponse.model_validate(item) for item in (line.cancellation_consents or [])],
    )


def _shipment_response(shipment: ShippingShipment) -> ShipmentResponse:
    return ShipmentResponse.model_validate(shipment)


def _order_response(order: ShippingOrder, *, operation_history: Optional[list[OperationHistoryResponse]] = None) -> ShippingOrderResponse:
    return ShippingOrderResponse(
        id=order.id, order_no=order.order_no, order_type=order.order_type,
        customer_id=order.customer_id, temporary_customer_name=order.temporary_customer_name,
        po_no=order.po_no, status=derive_order_status(order), created_by=order.created_by,
        created_at=order.created_at, last_modified_at=order.last_modified_at,
        submitted_at=order.submitted_at, completed_at=order.completed_at,
        lines=[_line_response(line) for line in order.lines],
        shipments=[_shipment_response(shipment) for shipment in order.shipments],
        operation_history=operation_history or [],
    )


def _workflow_error(code: str) -> HTTPException:
    messages = {
        "FORMAL_CUSTOMER_PO_REQUIRED": "正式订单必须填写客户和 PO 号",
        "SAMPLE_CUSTOMER_REQUIRED": "样件订单必须填写客户或临时客户",
        "ORDER_LINES_REQUIRED": "订单至少需要一条明细",
        "INVALID_ORDER_QTY": "订单数量必须为大于零的整数",
        "INVALID_PLANNED_DATE": "计划发货日期不能早于当前日期",
        "INVALID_ORDER_LINE": "订单明细缺少客户件号或零件名称",
        "INVENTORY_PART_REQUIRED": "正式订单明细必须先匹配零件库，才能预占库存",
        "INVALID_SHIPMENT_QTY": "发货数量不能超过剩余数量",
        "LINE_NOT_READY_TO_SHIP": "明细尚未完成标签确认",
        "LOGISTICS_REQUIRED": "物流公司或物流号至少填写一项",
    }
    status_code = 422 if code.startswith(("FORMAL_", "SAMPLE_", "ORDER_", "INVALID_ORDER_")) else 409
    return HTTPException(status_code=status_code, detail={"code": code, "message": messages.get(code, code)})


def _assert_draft_owner(order: ShippingOrder, user) -> None:
    if order.status == "draft" and order.created_by != user.id:
        raise HTTPException(status_code=403, detail={"code": "DRAFT_NOT_VISIBLE", "message": "草稿仅创建人可见"})


def _not_found(order):
    if not order:
        raise HTTPException(status_code=404, detail="发货订单不存在")
    return order


@router.get("/customer-parts/search", response_model=list[CustomerPartSearchResponse])
async def search_customer_parts(db: DbSession, current_user: CurrentUser, customer_id: int, q: str = Query(min_length=1)):
    rows = await customer_part_search(db, customer_id, q)
    return [CustomerPartSearchResponse(customer_part_no=a.customer_part_no or "", part_id=a.part_id, part_customer_alias_id=a.id, part_name=p.internal_name, customer_part_name=a.customer_part_name, same_physical_part_hint=(f"该件号对应内部零件 {p.id}" if p else None), inventory_stock_qty=inventory.stock_qty if inventory else 0, inventory_reserved_qty=inventory.reserved_qty if inventory else 0, inventory_available_qty=(inventory.stock_qty - inventory.reserved_qty) if inventory else 0, inventory_location=inventory.location if inventory else None) for a, p, inventory in rows]


@router.get("", response_model=ShippingOrderListResponse)
async def list_shipping_orders(
    db: DbSession, current_user: CurrentUser,
    customer_id: Optional[int] = None, order_type: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"), po_no: Optional[str] = None,
    customer_part_no: Optional[str] = None, planned_ship_date_from: Optional[date] = None,
    planned_ship_date_to: Optional[date] = None, created_by: Optional[int] = None,
    skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
):
    q = select(ShippingOrder).options(selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.shipment_lines), selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.label_confirmation), selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.cancellation_consents), selectinload(ShippingOrder.shipments).selectinload(ShippingShipment.lines), selectinload(ShippingOrder.shipments).selectinload(ShippingShipment.logistics))
    q = q.where((ShippingOrder.status != "draft") | (ShippingOrder.created_by == current_user.id))
    if customer_id is not None: q = q.where(ShippingOrder.customer_id == customer_id)
    if order_type: q = q.where(ShippingOrder.order_type == order_type)
    if status_filter: q = q.where(ShippingOrder.status == status_filter)
    if po_no: q = q.where(ShippingOrder.po_no.ilike(f"%{po_no}%"))
    if created_by is not None: q = q.where(ShippingOrder.created_by == created_by)
    if customer_part_no: q = q.join(ShippingOrder.lines).where(ShippingOrderLine.customer_part_no_snapshot.ilike(f"%{customer_part_no}%"))
    if planned_ship_date_from: q = q.join(ShippingOrder.lines, isouter=True).where(ShippingOrderLine.planned_ship_date >= planned_ship_date_from)
    if planned_ship_date_to: q = q.join(ShippingOrder.lines, isouter=True).where(ShippingOrderLine.planned_ship_date <= planned_ship_date_to)
    total = await db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    orders = (await db.execute(q.order_by(ShippingOrder.created_at.desc()).offset(skip).limit(limit))).unique().scalars().all()
    return ShippingOrderListResponse(items=[_order_response(x) for x in orders], total=int(total or 0))


@router.post("", response_model=ShippingOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_shipping_order(payload: ShippingOrderCreate, db: DbSession, current_user: CurrentUser):
    order = await create_draft(db, payload, current_user)
    await db.flush()
    return _order_response(await load_order(db, order.id))


@router.get("/{order_id}", response_model=ShippingOrderResponse)
async def get_shipping_order(order_id: int, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    _assert_draft_owner(order, current_user)
    return _order_response(order, operation_history=await _shipping_history(order_id, db, current_user))


@router.patch("/{order_id}", response_model=ShippingOrderResponse)
async def patch_shipping_order(order_id: int, payload: ShippingOrderUpdate, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    if order.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只有创建人可以修改草稿")
    try:
        await update_draft(db, order, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _order_response(order)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipping_order(order_id: int, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    if order.created_by != current_user.id or order.status != "draft":
        raise HTTPException(status_code=409, detail="只有创建人的草稿可以删除")
    await db.delete(order)


@router.post("/{order_id}/submit", response_model=ShippingOrderResponse)
async def submit_shipping_order(order_id: int, payload: SubmitRequest, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    if order.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只有创建人可以提交")
    try:
        await submit_order(db, order, payload, current_user)
    except ShippingWarning as warning:
        raise HTTPException(status_code=409, detail={"code": warning.code, "message": warning.message, "details": warning.details})
    except InventoryShortage as exc:
        raise HTTPException(status_code=409, detail={"code": "INVENTORY_SHORTAGE", "message": str(exc), "details": exc.details})
    except ValueError as exc:
        if str(exc) in {"FORMAL_CUSTOMER_PO_REQUIRED", "SAMPLE_CUSTOMER_REQUIRED", "ORDER_LINES_REQUIRED", "INVALID_ORDER_QTY", "INVALID_PLANNED_DATE", "INVALID_ORDER_LINE", "INVENTORY_PART_REQUIRED"}:
            raise _workflow_error(str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
    return _order_response(order)


@router.post("/{order_id}/withdraw", response_model=ShippingOrderResponse)
async def withdraw_shipping_order(order_id: int, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    if order.created_by != current_user.id: raise HTTPException(status_code=403, detail="只有创建人可以撤回")
    try: await withdraw(db, order, current_user)
    except ValueError as exc:
        raise _workflow_error(str(exc)) if str(exc) in {"LINE_NOT_READY_TO_SHIP", "INVALID_SHIPMENT_QTY"} else HTTPException(status_code=409, detail=str(exc))
    return _order_response(order)


@router.post("/lines/{line_id}/label-confirm", response_model=dict)
async def label_confirm(line_id: int, payload: LabelConfirmRequest, db: DbSession, current_user: CurrentUser):
    line = (await db.execute(select(ShippingOrderLine).where(ShippingOrderLine.id == line_id).options(selectinload(ShippingOrderLine.order), selectinload(ShippingOrderLine.label_confirmation)))).scalar_one_or_none()
    if not line: raise HTTPException(status_code=404, detail="订单明细不存在")
    try: confirmation = await confirm_label(db, line, current_user, payload.remark)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc))
    return {"id": confirmation.id, "order_line_id": confirmation.order_line_id, "status": "ready_to_ship"}


@router.post("/lines/{line_id}/cancel", response_model=dict)
async def cancel_shipping_line(line_id: int, payload: CancelRequest, db: DbSession, current_user: CurrentUser):
    line = (await db.execute(select(ShippingOrderLine).where(ShippingOrderLine.id == line_id).options(selectinload(ShippingOrderLine.order), selectinload(ShippingOrderLine.label_confirmation), selectinload(ShippingOrderLine.shipment_lines)))).scalar_one_or_none()
    if not line: raise HTTPException(status_code=404, detail="订单明细不存在")
    try: consent = await cancel_line(db, line, payload, current_user)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc))
    return {"status": "pending_consent" if consent else "cancelled", "consent_id": consent.id if consent else None}


@router.post("/lines/{line_id}/cancellation-consent", response_model=dict)
async def cancellation_consent(line_id: int, payload: CancellationConsentRequest, db: DbSession, current_user: CurrentUser):
    consent = (await db.execute(select(ShippingCancellationConsent).where(ShippingCancellationConsent.order_line_id == line_id, ShippingCancellationConsent.status == "pending").order_by(ShippingCancellationConsent.id.desc()).options(selectinload(ShippingCancellationConsent.line).selectinload(ShippingOrderLine.shipment_lines)))).scalars().first()
    if not consent: raise HTTPException(status_code=404, detail="没有待确认的取消申请")
    if not payload.consent:
        consent.status = "rejected"
        await write_audit(db, action="cancel", entity_type="shipping_cancellation_consent", entity_id=consent.id, user=current_user, summary="拒绝取消申请", new={"status": "rejected"})
        return {"status": "rejected", "consent_id": consent.id}
    try: await add_cancellation_consent(db, consent, current_user)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc))
    return {"status": consent.status, "consent_id": consent.id}


@router.post("/{order_id}/shipments/confirm", response_model=ShipmentResponse)
async def confirm_shipping(order_id: int, payload: ShipmentConfirmRequest, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    try: shipment = await confirm_shipment(db, order, payload, current_user)
    except ShippingWarning as warning:
        raise HTTPException(status_code=409, detail={"code": warning.code, "message": warning.message, "details": warning.details})
    except InventoryShortage as exc:
        raise HTTPException(status_code=409, detail={"code": "INVENTORY_SHORTAGE", "message": str(exc), "details": exc.details})
    except ValueError as exc:
        code = str(exc)
        if code in {"INVALID_SHIPMENT_QTY", "LINE_NOT_READY_TO_SHIP", "LOGISTICS_REQUIRED"}:
            raise _workflow_error(code)
        raise HTTPException(status_code=409, detail=code)
    return _shipment_response(shipment)


@router.patch("/shipments/{shipment_id}/logistics", response_model=ShipmentResponse)
async def patch_logistics(shipment_id: int, payload: LogisticsUpdateRequest, db: DbSession, current_user: CurrentUser):
    shipment = (await db.execute(select(ShippingShipment).where(ShippingShipment.id == shipment_id).options(selectinload(ShippingShipment.lines), selectinload(ShippingShipment.logistics)))).scalar_one_or_none()
    if not shipment: raise HTTPException(status_code=404, detail="发货记录不存在")
    await update_logistics(db, shipment, payload, current_user)
    return _shipment_response(shipment)


async def _shipping_history(order_id: int, db: DbSession, current_user: CurrentUser):
    order = _not_found(await load_order(db, order_id))
    _assert_draft_owner(order, current_user)
    line_ids = [x.id for x in order.lines]
    entity_types = ["shipping_order", "shipping_order_line", "shipping_label_confirmation", "shipping_cancellation_consent", "shipping_shipment", "shipping_logistics"]
    shipment_ids = [x.id for x in order.shipments]
    label_ids = [x.label_confirmation.id for x in order.lines if x.label_confirmation]
    consent_ids = list((await db.execute(select(ShippingCancellationConsent.id).where(ShippingCancellationConsent.order_line_id.in_(line_ids)))).scalars().all()) if line_ids else []
    logistics_ids = [item.id for shipment in order.shipments for item in shipment.logistics]
    # Older rows used the shipment ID for logistics audit entries; newer rows
    # use the individual logistics row ID. Query both forms for a complete
    # history during the compatibility window.
    logistics_audit_ids = list(dict.fromkeys(logistics_ids + shipment_ids))
    q = select(AuditLog).where(
        AuditLog.entity_type.in_(entity_types),
        ((AuditLog.entity_type == "shipping_order") & (AuditLog.entity_id == order_id))
        | ((AuditLog.entity_type == "shipping_order_line") & AuditLog.entity_id.in_(line_ids or [-1]))
        | ((AuditLog.entity_type == "shipping_shipment") & AuditLog.entity_id.in_(shipment_ids or [-1]))
        | ((AuditLog.entity_type == "shipping_label_confirmation") & AuditLog.entity_id.in_(label_ids or [-1]))
        | ((AuditLog.entity_type == "shipping_cancellation_consent") & AuditLog.entity_id.in_(consent_ids or [-1]))
        | ((AuditLog.entity_type == "shipping_logistics") & AuditLog.entity_id.in_(logistics_audit_ids or [-1])),
    ).order_by(AuditLog.created_at)
    logs = (await db.execute(q)).scalars().all()
    return [OperationHistoryResponse.model_validate(x) for x in logs]


@router.get("/{order_id}/history", response_model=list[OperationHistoryResponse])
async def shipping_history(order_id: int, db: DbSession, current_user: CurrentUser):
    return await _shipping_history(order_id, db, current_user)


# Historical clients used the more explicit resource name before the current
# route was published. Keep it as a read-only alias during the migration.
@router.get("/{order_id}/operation-history", response_model=list[OperationHistoryResponse])
async def shipping_operation_history(order_id: int, db: DbSession, current_user: CurrentUser):
    return await _shipping_history(order_id, db, current_user)


# Contract resource paths are kept as aliases for clients that address lines and
# shipments as first-class resources; the /shipping-orders paths remain the UI routes.
contract_router.add_api_route("/shipping-order-lines/{line_id}/label-confirm", label_confirm, methods=["POST"], response_model=dict, name="contract_label_confirm")
contract_router.add_api_route("/shipping-order-lines/{line_id}/cancel", cancel_shipping_line, methods=["POST"], response_model=dict, name="contract_cancel_line")
contract_router.add_api_route("/shipping-order-lines/{line_id}/cancellation-consent", cancellation_consent, methods=["POST"], response_model=dict, name="contract_cancellation_consent")
contract_router.add_api_route("/shipping-shipments/{shipment_id}/logistics", patch_logistics, methods=["PATCH"], response_model=ShipmentResponse, name="contract_patch_logistics")
