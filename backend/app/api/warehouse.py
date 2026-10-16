"""Warehouse and material batch management API endpoints."""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text, select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.audit import AuditAction, AuditLog
from app.models.packaging import Inventory, InventoryTransaction
from app.models.part import Part
from app.models.warehouse import (
    BatchStatus,
    BatchTransaction,
    IQCResult,
    Material,
    MaterialBatch,
    MaterialBatchChild,
    QRScanLog,
    ScanOperation,
    ScanType,
    Supplier,
)
from app.schemas.warehouse import (
    BatchConsumeRequest,
    BatchScrapRequest,
    BatchSplitRequest,
    BatchTraceResponse,
    BatchTransactionResponse,
    IQCUpdate,
    MaterialBatchChildScanResponse,
    MaterialBatchCreate,
    MaterialBatchDetailResponse,
    MaterialBatchResponse,
    MaterialBatchChildResponse,
    MaterialBatchScanResponse,
    MaterialCreate,
    MaterialResponse,
    QRScanLogCreate,
    QRScanLogResponse,
    SupplierCreate,
    SupplierResponse,
    FinishedGoodsInventoryPage,
    FinishedGoodsLedgerPage,
    FinishedGoodsLedgerSummary,
    FinishedGoodsLedgerDay,
    FinishedGoodsLedgerEntry,
    FinishedGoodsLedgerTransaction,
    FinishedGoodsInventoryReconcile,
    FinishedGoodsReviewPage,
    FinishedGoodsLocationUpdate,
    FinishedGoodsReviewResolve,
)
from app.schemas.packaging import InventoryAdjustmentRequest
from app.services import material_batch_service

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


async def _latest_finished_goods_batch_id(db: DbSession) -> Optional[int]:
    result = await db.execute(text("""
        SELECT id
        FROM import_batches
        WHERE imported_by LIKE 'system:finished_goods_snapshot:%'
        ORDER BY id DESC
        LIMIT 1
    """))
    return result.scalar_one_or_none()


@router.get("/finished-goods", response_model=FinishedGoodsInventoryPage)
async def list_finished_goods_inventory(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, max_length=100),
    customer_id: Optional[int] = Query(default=None, ge=1),
    customer_part_no: Optional[str] = Query(default=None, max_length=150),
    part_name: Optional[str] = Query(default=None, max_length=200),
    location: Optional[str] = Query(default=None, max_length=100),
    missing_location: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> FinishedGoodsInventoryPage:
    """List formal finished-goods balances linked to the part master."""
    filters = [
        "p.is_deleted = FALSE",
        "NULLIF(BTRIM(p.customer_part_no), '') IS NOT NULL",
    ]
    params: dict[str, object] = {"offset": (page - 1) * page_size, "limit": page_size}
    if customer_id is not None:
        params["customer_id"] = customer_id
        filters.append("""(p.customer_id = :customer_id OR EXISTS (
            SELECT 1 FROM part_customer_aliases pca
            WHERE pca.part_id = p.id AND pca.customer_id = :customer_id
              AND pca.is_active = TRUE AND pca.data_quality_status = 'approved'
        ))""")
    if customer_part_no and customer_part_no.strip():
        # The inventory search box accepts a customer-part-number fragment
        # (for example, ``399`` should find ``4DM3990108``). Keep aliases
        # under the same contains-match semantics so the visible search and
        # the autocomplete suggestions behave consistently.
        params["customer_part_no"] = f"%{customer_part_no.strip()}%"
        alias_customer_filter = "AND pca.customer_id = :customer_id" if customer_id is not None else ""
        filters.append(f"""(p.customer_part_no ILIKE :customer_part_no OR EXISTS (
            SELECT 1 FROM part_customer_aliases pca
            WHERE pca.part_id = p.id {alias_customer_filter}
              AND pca.customer_part_no ILIKE :customer_part_no
              AND pca.is_active = TRUE AND pca.data_quality_status = 'approved'
        ))""")
    if part_name and part_name.strip():
        params["part_name"] = f"%{part_name.strip()}%"
        alias_customer_filter = "AND pca.customer_id = :customer_id" if customer_id is not None else ""
        filters.append(f"""(p.internal_name ILIKE :part_name OR p.customer_part_name ILIKE :part_name OR EXISTS (
            SELECT 1 FROM part_customer_aliases pca
            WHERE pca.part_id = p.id {alias_customer_filter}
              AND pca.customer_part_name ILIKE :part_name
              AND pca.is_active = TRUE AND pca.data_quality_status = 'approved'
        ))""")
    if search and search.strip():
        params["search"] = f"%{search.strip()}%"
        filters.append("""(p.internal_part_no ILIKE :search OR p.internal_name ILIKE :search
            OR p.customer_part_no ILIKE :search OR p.customer_part_name ILIKE :search
            OR c.name ILIKE :search)""")
    if location and location.strip():
        params["location"] = f"%{location.strip()}%"
        filters.append("i.location ILIKE :location")
    if missing_location:
        filters.append("NULLIF(BTRIM(i.location), '') IS NULL")
    where = " AND ".join(filters)

    base = f"""
        FROM finished_goods_inventory i
        JOIN parts p ON p.id = i.part_id
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE {where}
    """
    total = (await db.execute(text(f"SELECT COUNT(*) {base}"), params)).scalar_one()
    rows = (await db.execute(text(f"""
        SELECT i.id, i.part_id, p.internal_part_no, p.internal_name AS part_name,
               p.customer_part_no, p.customer_part_name, c.name AS customer_name,
               COALESCE(i.stock_qty, 0) AS stock_qty,
               COALESCE(i.reserved_qty, 0) AS reserved_qty,
               COALESCE(i.stock_qty, 0) - COALESCE(i.reserved_qty, 0) AS available_qty,
               COALESCE((
                   SELECT SUM(ssl.qty)
                   FROM shipping_shipment_lines ssl
                   JOIN shipping_shipments ss ON ss.id = ssl.shipment_id
                   JOIN shipping_order_lines sol ON sol.id = ssl.order_line_id
                   WHERE sol.part_id = i.part_id
                     AND ss.confirmed_at >= CURRENT_TIMESTAMP - INTERVAL '1 month'
               ), 0)::int AS last_month_shipped_qty,
               COALESCE((
                   SELECT SUM(ssl.qty)
                   FROM shipping_shipment_lines ssl
                   JOIN shipping_shipments ss ON ss.id = ssl.shipment_id
                   JOIN shipping_order_lines sol ON sol.id = ssl.order_line_id
                   WHERE sol.part_id = i.part_id
                     AND ss.confirmed_at >= CURRENT_TIMESTAMP - INTERVAL '3 months'
               ), 0)::int AS last_3_month_shipped_qty,
               i.location, i.last_update_at
        {base}
        ORDER BY i.stock_qty DESC, i.part_id
        OFFSET :offset LIMIT :limit
    """), params)).mappings().all()

    summary_row = (await db.execute(text("""
        SELECT COUNT(*) AS inventory_rows,
               COALESCE(SUM(i.stock_qty), 0) AS total_stock,
               COALESCE(SUM(i.reserved_qty), 0) AS total_reserved,
               COALESCE(SUM(i.stock_qty - i.reserved_qty), 0) AS total_available,
               COUNT(*) FILTER (WHERE NULLIF(BTRIM(i.location), '') IS NULL) AS missing_location_rows
        FROM finished_goods_inventory i
        JOIN parts p ON p.id = i.part_id
        WHERE p.is_deleted = FALSE
          AND NULLIF(BTRIM(p.customer_part_no), '') IS NOT NULL
    """))).mappings().one()
    batch_id = await _latest_finished_goods_batch_id(db)
    review_rows = 0
    if batch_id is not None:
        review_rows = (await db.execute(text("""
            SELECT COUNT(*) FROM excel_import_rows
            WHERE batch_id=:batch_id AND validation_status='REVIEW'
        """), {"batch_id": batch_id})).scalar_one()

    return FinishedGoodsInventoryPage(
        items=[dict(row) for row in rows], total=total, page=page, page_size=page_size,
        summary={**dict(summary_row), "review_rows": review_rows, "batch_id": batch_id},
    )


@router.get("/finished-goods/review", response_model=FinishedGoodsReviewPage)
async def list_finished_goods_review_rows(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, max_length=100),
    category: Optional[str] = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> FinishedGoodsReviewPage:
    """List isolated review rows from the latest finished-goods snapshot."""
    batch_id = await _latest_finished_goods_batch_id(db)
    if batch_id is None:
        return FinishedGoodsReviewPage(items=[], total=0, page=page, page_size=page_size, batch_id=None, categories={})

    filters = ["batch_id=:batch_id", "validation_status='REVIEW'"]
    params: dict[str, object] = {
        "batch_id": batch_id, "offset": (page - 1) * page_size, "limit": page_size,
    }
    if search and search.strip():
        params["search"] = f"%{search.strip()}%"
        filters.append("""(source_sheet ILIKE :search OR parsed_customer_part_no ILIKE :search
            OR parsed_customer_part_name ILIKE :search)""")
    if category and category.strip():
        params["category"] = f"%{category.strip()}%"
        filters.append("validation_errors ILIKE :category")
    where = " AND ".join(filters)
    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM excel_import_rows WHERE {where}"), params
    )).scalar_one()
    rows = (await db.execute(text(f"""
        SELECT id, batch_id, source_sheet, source_row,
               parsed_customer_part_no AS customer_part_no,
               parsed_customer_part_name AS customer_part_name,
               CASE
                   WHEN raw_data->>'closing_qty' ~ '^[+-]?[0-9]+(?:\.[0-9]+)?$'
                   THEN (raw_data->>'closing_qty')::double precision
                   ELSE NULL
               END AS closing_qty,
               NULLIF(BTRIM(raw_data->>'location'), '') AS location, validation_errors
        FROM excel_import_rows
        WHERE {where}
        ORDER BY source_sheet, source_row
        OFFSET :offset LIMIT :limit
    """), params)).mappings().all()
    category_rows = (await db.execute(text("""
        SELECT NULLIF(BTRIM(error), '') AS error, COUNT(*) AS count
        FROM excel_import_rows
        CROSS JOIN LATERAL regexp_split_to_table(
            COALESCE(NULLIF(validation_errors, ''), '其他待处理'), ';'
        ) AS error
        WHERE batch_id=:batch_id AND validation_status='REVIEW'
        GROUP BY NULLIF(BTRIM(error), '')
        ORDER BY count DESC, error
    """), {"batch_id": batch_id})).all()

    items = []
    for row in rows:
        item = dict(row)
        errors = [value.strip() for value in (item.pop("validation_errors") or "").split(";") if value.strip()]
        item["validation_errors"] = errors
        item["missing_part"] = any("零件库没有对应的件号" in value or "零件未匹配" in value for value in errors)
        items.append(item)
    return FinishedGoodsReviewPage(
        items=items, total=total, page=page, page_size=page_size, batch_id=batch_id,
        categories={str(error or '其他待处理'): int(count) for error, count in category_rows},
    )


@router.get("/finished-goods/{inventory_id}/ledger", response_model=FinishedGoodsLedgerPage)
async def finished_goods_ledger(
    inventory_id: int,
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(default=90, ge=1, le=366),
) -> FinishedGoodsLedgerPage:
    """Return daily incoming/outgoing movements and calculated closing stock."""
    inventory = (await db.execute(
        select(Inventory).where(Inventory.id == inventory_id)
    )).scalar_one_or_none()
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    to_date = datetime.utcnow().date()
    from_date = to_date - timedelta(days=days - 1)
    rows = (await db.execute(text("""
        SELECT id, created_at, created_at::date AS day, transaction_type, quantity,
               stock_before, stock_after, reason, reference_type, operator_id
        FROM inventory_transactions
        WHERE part_id=:part_id
          AND created_at >= :from_ts
          AND created_at < :to_ts
          AND transaction_type IN ('incoming', 'outgoing', 'adjustment')
        ORDER BY created_at, id
    """), {
        "part_id": inventory.part_id,
        "from_ts": datetime.combine(from_date, datetime.min.time()),
        "to_ts": datetime.combine(to_date + timedelta(days=1), datetime.min.time()),
    })).mappings().all()

    incoming_by_day: dict[date, int] = {}
    outgoing_by_day: dict[date, int] = {}
    period_net = 0
    entries: list[FinishedGoodsLedgerTransaction] = []
    for row in rows:
        quantity = int(row["quantity"] or 0)
        affects_stock = row["reference_type"] != "historical_note"
        if affects_stock and (row["transaction_type"] == "incoming" or (row["transaction_type"] == "adjustment" and quantity > 0)):
            incoming_by_day[row["day"]] = incoming_by_day.get(row["day"], 0) + abs(quantity)
        elif affects_stock and (row["transaction_type"] == "outgoing" or (row["transaction_type"] == "adjustment" and quantity < 0)):
            outgoing_by_day[row["day"]] = outgoing_by_day.get(row["day"], 0) + abs(quantity)
        if affects_stock:
            period_net += quantity
        entries.append(FinishedGoodsLedgerTransaction(
            id=int(row["id"]), occurred_at=row["created_at"],
            transaction_type=(
                "incoming" if row["transaction_type"] == "incoming" or (row["transaction_type"] == "adjustment" and quantity > 0)
                else "outgoing"
            ),
            quantity=abs(quantity), stock_before=int(row["stock_before"]),
            stock_after=int(row["stock_after"]), reason=row["reason"],
            reference_type=row["reference_type"], operator_id=row["operator_id"],
            affects_stock=row["reference_type"] != "historical_note",
        ))

    opening_stock = int(inventory.stock_qty) - period_net
    running_stock = opening_stock
    ledger_days: list[FinishedGoodsLedgerDay] = []
    for day_offset in range(days):
        day = from_date + timedelta(days=day_offset)
        incoming = incoming_by_day.get(day, 0)
        outgoing = outgoing_by_day.get(day, 0)
        running_stock += incoming - outgoing
        ledger_days.append(FinishedGoodsLedgerDay(
            day=day, incoming_qty=incoming, outgoing_qty=outgoing,
            net_qty=incoming - outgoing, closing_qty=running_stock,
        ))

    return FinishedGoodsLedgerPage(
        inventory_id=inventory.id,
        part_id=inventory.part_id,
        summary=FinishedGoodsLedgerSummary(
            opening_stock=opening_stock,
            total_incoming=sum(incoming_by_day.values()),
            total_outgoing=sum(outgoing_by_day.values()),
            closing_stock=int(inventory.stock_qty),
            from_date=from_date,
            to_date=to_date,
        ),
        days=ledger_days,
        entries=entries,
    )


@router.post("/finished-goods/{inventory_id}/ledger/entry", response_model=dict)
async def create_finished_goods_ledger_entry(
    inventory_id: int,
    data: FinishedGoodsLedgerEntry,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Register a warehouse income or expense and recalculate the balance."""
    require_role(current_user, min_level=2)
    inventory = (await db.execute(
        select(Inventory).where(Inventory.id == inventory_id).with_for_update()
    )).scalar_one_or_none()
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    if data.occurred_on and data.occurred_on > datetime.utcnow().date():
        raise HTTPException(status_code=422, detail="发生日期不能晚于今天")
    signed_quantity = data.quantity if data.transaction_type == 'incoming' else -data.quantity
    stock_before = int(inventory.stock_qty)
    stock_after = stock_before + signed_quantity
    if data.affects_stock and stock_after < inventory.reserved_qty:
        raise HTTPException(status_code=409, detail="支出后库存不能低于已预留数量")
    if data.affects_stock:
        inventory.stock_qty = stock_after
        inventory.last_update_by = current_user.id
        inventory.last_update_at = datetime.utcnow()
        await db.execute(
            Part.__table__.update().where(Part.id == inventory.part_id).values(
                stock_pcs=stock_after, updated_at=datetime.utcnow()
            )
        )
    occurred_at = datetime.combine(data.occurred_on, datetime.min.time()) if data.occurred_on else datetime.utcnow()
    db.add(InventoryTransaction(
        part_id=inventory.part_id,
        transaction_type=data.transaction_type,
        quantity=signed_quantity,
        stock_before=stock_before if data.affects_stock else int(inventory.stock_qty),
        stock_after=stock_after if data.affects_stock else int(inventory.stock_qty),
        reference_type=("historical_ledger" if data.affects_stock else "historical_note") if data.occurred_on else "manual_ledger",
        reference_id=inventory.id,
        reason=data.reason.strip(),
        operator_id=current_user.id,
        created_at=occurred_at,
    ))
    db.add(AuditLog(
        action=AuditAction.UPDATE,
        entity_type="finished_goods_inventory",
        entity_id=inventory.id,
        user_id=current_user.id,
        username=current_user.username,
        changes_summary=("补录成品库存收入" if data.transaction_type == 'incoming' else "补录成品库存支出") if data.occurred_on else ("登记成品库存收入" if data.transaction_type == 'incoming' else "登记成品库存支出"),
        old_values={"stock_qty": stock_before},
        new_values={"stock_qty": stock_after if data.affects_stock else stock_before, "quantity": data.quantity, "reason": data.reason.strip(), "occurred_on": str(data.occurred_on) if data.occurred_on else None, "affects_stock": data.affects_stock},
    ))
    return {"id": inventory.id, "part_id": inventory.part_id, "transaction_type": data.transaction_type, "quantity": signed_quantity, "stock_qty": int(inventory.stock_qty), "affects_stock": data.affects_stock}


@router.post("/finished-goods/{inventory_id}/ledger/reconcile", response_model=dict)
async def reconcile_finished_goods_inventory(
    inventory_id: int,
    data: FinishedGoodsInventoryReconcile,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Reconcile physical stock and record a signed stocktake transaction."""
    require_role(current_user, min_level=2)
    inventory = (await db.execute(
        select(Inventory).where(Inventory.id == inventory_id).with_for_update()
    )).scalar_one_or_none()
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    if data.occurred_on and data.occurred_on > datetime.utcnow().date():
        raise HTTPException(status_code=422, detail="盘点日期不能晚于今天")
    stock_before = int(inventory.stock_qty)
    difference = int(data.physical_stock) - stock_before
    if difference == 0:
        return {"id": inventory.id, "part_id": inventory.part_id, "stock_qty": stock_before, "difference": 0, "transaction_id": None}
    stock_after = stock_before + difference
    if stock_after < inventory.reserved_qty:
        raise HTTPException(status_code=409, detail="盘点后库存不能低于已预留数量")
    inventory.stock_qty = stock_after
    inventory.last_update_by = current_user.id
    inventory.last_update_at = datetime.utcnow()
    await db.execute(
        Part.__table__.update().where(Part.id == inventory.part_id).values(
            stock_pcs=stock_after, updated_at=datetime.utcnow()
        )
    )
    transaction = InventoryTransaction(
        part_id=inventory.part_id,
        transaction_type="incoming" if difference > 0 else "outgoing",
        quantity=difference,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_type="inventory_reconciliation",
        reference_id=inventory.id,
        reason=data.reason.strip(),
        operator_id=current_user.id,
        created_at=datetime.combine(data.occurred_on, datetime.min.time()) if data.occurred_on else datetime.utcnow(),
    )
    db.add(transaction)
    await db.flush()
    db.add(AuditLog(
        action=AuditAction.UPDATE,
        entity_type="finished_goods_inventory",
        entity_id=inventory.id,
        user_id=current_user.id,
        username=current_user.username,
        changes_summary="登记库存盘点差异",
        old_values={"stock_qty": stock_before},
        new_values={"stock_qty": stock_after, "physical_stock": data.physical_stock, "difference": difference, "reason": data.reason.strip()},
    ))
    return {"id": inventory.id, "part_id": inventory.part_id, "stock_qty": stock_after, "difference": difference, "transaction_id": transaction.id}


@router.patch("/finished-goods/{inventory_id}/location", response_model=dict)
async def update_finished_goods_location(
    inventory_id: int,
    data: FinishedGoodsLocationUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Update a finished-goods location without changing stock quantities."""
    require_role(current_user, min_level=1)
    inventory = (await db.execute(
        select(Inventory).where(Inventory.id == inventory_id).with_for_update()
    )).scalar_one_or_none()
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    inventory.location = data.location.strip() if data.location and data.location.strip() else None
    inventory.last_update_by = current_user.id
    inventory.last_update_at = datetime.utcnow()
    db.add(AuditLog(
        action=AuditAction.UPDATE,
        entity_type="finished_goods_inventory",
        entity_id=inventory.id,
        user_id=current_user.id,
        username=current_user.username,
        changes_summary="更新成品库位",
        new_values={"location": inventory.location},
    ))
    return {"id": inventory.id, "part_id": inventory.part_id, "location": inventory.location}


@router.post("/finished-goods/{inventory_id}/adjust", response_model=dict)
async def adjust_finished_goods_inventory(
    inventory_id: int,
    data: InventoryAdjustmentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Apply an audited stock adjustment to a formal finished-goods row."""
    require_role(current_user, min_level=3)
    inventory = (await db.execute(
        select(Inventory).where(Inventory.id == inventory_id).with_for_update()
    )).scalar_one_or_none()
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    if not data.reason.strip():
        raise HTTPException(status_code=422, detail="调整原因不能为空")
    stock_before = inventory.stock_qty
    stock_after = stock_before + data.quantity
    if stock_after < inventory.reserved_qty:
        raise HTTPException(status_code=409, detail="调整后库存不能低于已预留数量")
    if stock_after < 0:
        raise HTTPException(status_code=409, detail="库存不能为负数")
    inventory.stock_qty = stock_after
    inventory.last_update_by = current_user.id
    inventory.last_update_at = datetime.utcnow()
    await db.execute(
        select(Part.id).where(Part.id == inventory.part_id).with_for_update()
    )
    await db.execute(
        Part.__table__.update().where(Part.id == inventory.part_id).values(
            stock_pcs=stock_after, updated_at=datetime.utcnow()
        )
    )
    db.add(InventoryTransaction(
        part_id=inventory.part_id,
        transaction_type="adjustment",
        quantity=data.quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_type="finished_goods_inventory",
        reference_id=inventory.id,
        reason=data.reason.strip(),
        operator_id=current_user.id,
    ))
    db.add(AuditLog(
        action=AuditAction.UPDATE,
        entity_type="finished_goods_inventory",
        entity_id=inventory.id,
        user_id=current_user.id,
        username=current_user.username,
        changes_summary="调整成品库存",
        old_values={"stock_qty": stock_before},
        new_values={"stock_qty": stock_after, "reason": data.reason.strip()},
    ))
    return {"id": inventory.id, "part_id": inventory.part_id, "stock_qty": stock_after, "reserved_qty": inventory.reserved_qty}


@router.post("/finished-goods/review/{row_id}/resolve", response_model=dict)
async def resolve_finished_goods_review(
    row_id: int,
    data: FinishedGoodsReviewResolve,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Confirm a review row and immediately place it in formal inventory."""
    require_role(current_user, min_level=2)
    batch_id = await _latest_finished_goods_batch_id(db)
    if batch_id is None:
        raise HTTPException(status_code=404, detail="No finished-goods import batch")
    row = (await db.execute(text("""
        SELECT id, batch_id, validation_status, parsed_customer_part_no,
               parsed_customer_part_name, resolved_customer_id, raw_data->>'closing_qty' AS closing_qty
        FROM excel_import_rows
        WHERE id=:row_id AND batch_id=:batch_id
        FOR UPDATE
    """), {"row_id": row_id, "batch_id": batch_id})).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Review row not found")
    if row["validation_status"] != "REVIEW":
        raise HTTPException(status_code=409, detail="该记录已经处理")
    part = (await db.execute(select(Part).where(Part.id == data.part_id, Part.is_deleted.is_(False)))).scalar_one_or_none()
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")
    quantity = data.stock_qty
    if quantity is None and row["closing_qty"] not in (None, ""):
        try:
            quantity = int(float(row["closing_qty"]))
        except (TypeError, ValueError):
            quantity = None
    if quantity is None:
        raise HTTPException(status_code=422, detail="请填写有效库存数量")
    inventory = (await db.execute(
        select(Inventory).where(Inventory.part_id == data.part_id).with_for_update()
    )).scalar_one_or_none()
    if inventory is None:
        inventory = Inventory(part_id=data.part_id, stock_qty=0, reserved_qty=0)
        db.add(inventory)
        await db.flush()
    if quantity < inventory.reserved_qty:
        raise HTTPException(status_code=409, detail="确认数量不能低于已预留数量")
    stock_before = inventory.stock_qty
    inventory.stock_qty = quantity
    if data.location is not None:
        inventory.location = data.location.strip() or None
    inventory.last_update_by = current_user.id
    inventory.last_update_at = datetime.utcnow()
    await db.execute(Part.__table__.update().where(Part.id == data.part_id).values(stock_pcs=quantity, updated_at=datetime.utcnow()))
    if quantity != stock_before:
        db.add(InventoryTransaction(
            part_id=data.part_id,
            transaction_type="incoming" if quantity > stock_before else "adjustment",
            quantity=quantity - stock_before,
            stock_before=stock_before,
            stock_after=quantity,
            reference_type="finished_goods_review",
            reference_id=row_id,
            reason=data.note or "待处理库存确认入正式库存",
            operator_id=current_user.id,
        ))
    await db.execute(text("""
        UPDATE excel_import_rows
        SET validation_status='IMPORTED', validation_errors=NULL,
            resolved_part_id=:part_id,
            resolved_customer_id=COALESCE(resolved_customer_id, :customer_id)
        WHERE id=:row_id AND batch_id=:batch_id
    """), {"part_id": data.part_id, "customer_id": row["resolved_customer_id"], "row_id": row_id, "batch_id": batch_id})
    db.add(AuditLog(
        action=AuditAction.IMPORT,
        entity_type="excel_import_row",
        entity_id=row_id,
        user_id=current_user.id,
        username=current_user.username,
        changes_summary="待处理成品库存确认入正式库存",
        new_values={"part_id": data.part_id, "stock_qty": quantity, "location": inventory.location, "note": data.note},
    ))
    return {"row_id": row_id, "batch_id": batch_id, "status": "IMPORTED", "part_id": data.part_id, "stock_qty": quantity, "reserved_qty": inventory.reserved_qty, "location": inventory.location}


def _batch_to_response(batch: MaterialBatch) -> MaterialBatchResponse:
    """Convert MaterialBatch to response."""
    return MaterialBatchResponse(
        id=batch.id,
        batch_no=batch.batch_no or batch.qr_uid,
        qr_code=batch.qr_code,
        material_id=batch.material_id or 0,
        supplier_id=batch.supplier_id,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight or 0,
        net_weight=batch.net_weight,
        current_weight=batch.current_weight or 0,
        status=batch.status or BatchStatus.PENDING_IQC,
        iqc_result=batch.iqc_result,
        iqc_time=batch.iqc_time,
        iqc_by=batch.iqc_by,
        iqc_notes=batch.iqc_notes,
        parent_batch_id=batch.parent_batch_id,
        po_no=batch.po_no,
        received_at=batch.received_at,
        created_at=batch.created_at,
    )


def _batch_detail_to_response(batch: MaterialBatch) -> MaterialBatchDetailResponse:
    """Convert MaterialBatch to detail response."""
    children = []
    if batch.children:
        for child in batch.children:
            children.append(
                MaterialBatchChildResponse(
                    id=child.id,
                    child_batch_no=child.child_batch_no,
                    child_qr_code=child.child_qr_code,
                    width=child.width,
                    length=child.length,
                    current_weight=child.current_weight,
                    status=child.status,
                    created_at=child.created_at,
                )
            )

    return MaterialBatchDetailResponse(
        id=batch.id,
        batch_no=batch.batch_no or batch.qr_uid or "",
        qr_code=batch.qr_code,
        material_id=batch.material_id or 0,
        material_name=batch.material.name if batch.material else (batch.material_name or ""),
        material_grade=batch.material.grade if batch.material else None,
        supplier_id=batch.supplier_id,
        supplier_name=batch.supplier.name if batch.supplier else (batch.supplier_name or ""),
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight or 0,
        net_weight=batch.net_weight,
        current_weight=batch.current_weight or 0,
        status=batch.status or BatchStatus.PENDING_IQC,
        iqc_result=batch.iqc_result,
        iqc_time=batch.iqc_time,
        iqc_by=batch.iqc_by,
        iqc_notes=batch.iqc_notes,
        parent_batch_id=batch.parent_batch_id,
        po_no=batch.po_no,
        received_at=batch.received_at,
        created_at=batch.created_at,
        children=children,
    )


@router.post("/material-batches", response_model=MaterialBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_material_batch(
    data: MaterialBatchCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Create a new material batch (register incoming material). Requires LV2 (warehouse manager)."""
    require_role(current_user, min_level=2)

    # Verify material exists
    result = await db.execute(select(Material).where(Material.id == data.material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Verify supplier if provided
    if data.supplier_id:
        result = await db.execute(select(Supplier).where(Supplier.id == data.supplier_id))
        supplier = result.scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

    batch = await material_batch_service.create_material_batch(
        db,
        material_id=data.material_id,
        gross_weight=data.gross_weight,
        supplier_id=data.supplier_id,
        thickness=data.thickness,
        width=data.width,
        length=data.length,
        po_no=data.po_no,
    )
    return _batch_to_response(batch)


@router.get("/material-batches", response_model=list[MaterialBatchResponse])
async def list_material_batches(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[BatchStatus] = Query(default=None, alias="status"),
    material_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MaterialBatchResponse]:
    """List material batches with optional filters."""
    batches = await material_batch_service.get_batches(
        db,
        status=status_filter,
        material_id=material_id,
        skip=skip,
        limit=limit,
    )
    return [_batch_to_response(b) for b in batches]


@router.get("/material-batches/{batch_id}", response_model=MaterialBatchDetailResponse)
async def get_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchDetailResponse:
    """Get material batch details."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")
    return _batch_detail_to_response(batch)


@router.get("/material-batches/by-no/{batch_no}", response_model=MaterialBatchDetailResponse)
async def get_material_batch_by_no(
    batch_no: str,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchDetailResponse:
    """Get material batch by batch number."""
    batch = await material_batch_service.get_batch_by_no(db, batch_no)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")
    return _batch_detail_to_response(batch)


@router.put("/material-batches/{batch_id}/iqc", response_model=MaterialBatchResponse)
async def perform_iqc(
    batch_id: int,
    data: IQCUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Perform IQC inspection on a material batch. Requires LV2 (quality supervisor)."""
    require_role(current_user, min_level=2)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.perform_iqc(
            db, batch, data.result, current_user.id, data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.post("/material-batches/{batch_id}/split", response_model=list[MaterialBatchScanResponse])
async def split_material_batch(
    batch_id: int,
    data: BatchSplitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MaterialBatchScanResponse]:
    """Split a material batch into child batches (each with unique QR code).

    T015: 扫码母卷后执行分条，返回各子卷的 qr_code 供打印标签。
    Requires LV2 (warehouse manager).
    """
    require_role(current_user, min_level=2)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    splits = [s.model_dump() for s in data.splits]

    try:
        children = await material_batch_service.split_batch(
            db, batch, splits, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 记录分条扫码日志
    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=batch.id,
        entity_no=batch.batch_no,
        operation=ScanOperation.SPLIT,
        operator_id=current_user.id,
        notes=f"Split into {len(children)} child batches",
    )

    return [
        MaterialBatchScanResponse(
            id=c.id,
            batch_no=c.batch_no,
            qr_code=c.qr_code,
            qr_image_base64=generate_material_batch_qr_base64(c.id) if c.qr_code else None,
            material_id=c.material_id,
            material_name=c.material.name if c.material else None,
            material_grade=c.material.grade if c.material else None,
            supplier_name=c.supplier.name if c.supplier else None,
            thickness=c.thickness,
            width=c.width,
            length=c.length,
            gross_weight=c.gross_weight,
            current_weight=c.current_weight,
            status=c.status,
            iqc_result=None,
            iqc_time=None,
            received_at=c.received_at,
            created_at=c.created_at,
            parent_batch_id=batch.id,
            parent_batch_no=batch.batch_no,
        )
        for c in children
    ]


@router.post("/material-batches/{batch_id}/consume", response_model=MaterialBatchResponse)
async def consume_material(
    batch_id: int,
    data: BatchConsumeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Consume material from a batch (called during production)."""
    require_role(current_user, min_level=1)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.consume_material(
            db,
            batch,
            weight=data.weight,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            operator_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.post("/material-batches/{batch_id}/scrap", response_model=MaterialBatchResponse)
async def scrap_material_batch(
    batch_id: int,
    data: BatchScrapRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchResponse:
    """Scrap a material batch. Requires LV3 (boss approval for material write-off)."""
    require_role(current_user, min_level=3)

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    try:
        batch = await material_batch_service.scrap_batch(
            db, batch, data.reason, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _batch_to_response(batch)


@router.get("/material-batches/{batch_id}/trace", response_model=BatchTraceResponse)
async def trace_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> BatchTraceResponse:
    """Trace a material batch with all its transactions."""
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    transactions = await material_batch_service.get_batch_transactions(db, batch_id)

    return BatchTraceResponse(
        batch=_batch_detail_to_response(batch),
        transactions=[
            BatchTransactionResponse(
                id=t.id,
                batch_id=t.batch_id,
                batch_no=t.batch_no,
                transaction_type=t.transaction_type,
                quantity_change=t.quantity_change,
                weight_after=t.weight_after,
                reference_type=t.reference_type,
                reference_id=t.reference_id,
                operator_id=t.operator_id,
                notes=t.notes,
                created_at=t.created_at,
            )
            for t in transactions
        ],
    )


# ── QR Scan Endpoints ────────────────────────────────────────────────────────

@router.get("/material-batches/scan/{batch_id}", response_model=MaterialBatchScanResponse)
async def scan_material_batch(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchScanResponse:
    """Scan material batch QR code, record scan log, return full ledger info.

    T012: 扫码原料二维码，记录扫码日志，返回完整台账。
    """
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=batch.id,
        entity_no=batch.batch_no,
        operation=ScanOperation.QUERY,
        operator_id=current_user.id,
    )

    parent_batch_no = None
    if batch.parent_batch_id:
        parent = await material_batch_service.get_batch_by_id(db, batch.parent_batch_id)
        if parent:
            parent_batch_no = parent.batch_no

    return MaterialBatchScanResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        qr_image_base64=generate_material_batch_qr_base64(batch.id) if batch.qr_code else None,
        material_id=batch.material_id,
        material_name=batch.material.name if batch.material else None,
        material_grade=batch.material.grade if batch.material else None,
        supplier_name=batch.supplier.name if batch.supplier else None,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        gross_weight=batch.gross_weight,
        current_weight=batch.current_weight,
        status=batch.status,
        iqc_result=batch.iqc_result,
        iqc_time=batch.iqc_time,
        received_at=batch.received_at,
        created_at=batch.created_at,
        parent_batch_id=batch.parent_batch_id,
        parent_batch_no=parent_batch_no,
    )


@router.get("/material-batches/scan/child/{child_id}", response_model=MaterialBatchChildScanResponse)
async def scan_child_batch(
    child_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchChildScanResponse:
    """Scan child batch QR code: child info + parent info + sibling list.

    T016: 扫码子卷，返回子卷台账 + 母卷完整信息 + 同胞子卷列表。
    """
    child = await material_batch_service.get_child_batch_by_id(db, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child batch not found")

    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=child.id,
        entity_no=child.batch_no,
        operation=ScanOperation.QUERY,
        operator_id=current_user.id,
    )

    parent = child.parent_batch
    siblings: list[MaterialBatchScanResponse] = []
    parent_response = None

    if parent:
        parent_response = MaterialBatchScanResponse(
            id=parent.id,
            batch_no=parent.batch_no,
            qr_code=parent.qr_code,
            qr_image_base64=generate_material_batch_qr_base64(parent.id) if parent.qr_code else None,
            material_id=parent.material_id,
            material_name=parent.material.name if parent.material else None,
            material_grade=parent.material.grade if parent.material else None,
            supplier_name=parent.supplier.name if parent.supplier else None,
            thickness=parent.thickness,
            width=parent.width,
            length=parent.length,
            gross_weight=parent.gross_weight,
            current_weight=parent.current_weight,
            status=parent.status,
            iqc_result=parent.iqc_result,
            iqc_time=parent.iqc_time,
            received_at=parent.received_at,
            created_at=parent.created_at,
            parent_batch_id=None,
            parent_batch_no=None,
        )
        sibling_rows = await material_batch_service.get_sibling_batches(
            db, parent_batch_id=parent.id, exclude_id=child.id
        )
        for sib in sibling_rows:
            siblings.append(
                MaterialBatchScanResponse(
                    id=sib.id,
                    batch_no=sib.batch_no,
                    qr_code=sib.qr_code,
                    qr_image_base64=generate_material_batch_qr_base64(sib.id) if sib.qr_code else None,
                    material_id=sib.material_id,
                    material_name=sib.material.name if sib.material else None,
                    material_grade=sib.material.grade if sib.material else None,
                    supplier_name=sib.supplier.name if sib.supplier else None,
                    thickness=sib.thickness,
                    width=sib.width,
                    length=sib.length,
                    gross_weight=sib.gross_weight,
                    current_weight=sib.current_weight,
                    status=sib.status,
                    iqc_result=sib.iqc_result,
                    iqc_time=sib.iqc_time,
                    received_at=sib.received_at,
                    created_at=sib.created_at,
                    parent_batch_id=sib.parent_batch_id,
                    parent_batch_no=None,
                )
            )

    child_response = MaterialBatchScanResponse(
        id=child.id,
        batch_no=child.batch_no,
        qr_code=child.qr_code,
        qr_image_base64=generate_material_batch_qr_base64(child.id) if child.qr_code else None,
        material_id=child.material_id,
        material_name=child.material.name if child.material else None,
        material_grade=child.material.grade if child.material else None,
        supplier_name=child.supplier.name if child.supplier else None,
        thickness=child.thickness,
        width=child.width,
        length=child.length,
        gross_weight=child.gross_weight,
        current_weight=child.current_weight,
        status=child.status,
        iqc_result=child.iqc_result,
        iqc_time=child.iqc_time,
        received_at=child.received_at,
        created_at=child.created_at,
        parent_batch_id=child.parent_batch_id,
        parent_batch_no=parent.batch_no if parent else None,
    )

    return MaterialBatchChildScanResponse(
        child_batch=child_response,
        parent_batch=parent_response,
        sibling_batches=siblings,
    )


@router.get("/material-batches/{batch_id}/children", response_model=list[MaterialBatchScanResponse])
async def list_child_batches(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MaterialBatchScanResponse]:
    """List all child batches of a parent batch.

    T017: 扫码母卷，返回所有子卷列表（含状态）。
    """
    parent = await material_batch_service.get_parent_batch(db, batch_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Material batch not found")

    await material_batch_service.create_scan_log(
        db,
        scan_type=ScanType.MAT,
        entity_id=parent.id,
        entity_no=parent.batch_no,
        operation=ScanOperation.QUERY,
        operator_id=current_user.id,
    )

    result = await db.execute(
        select(MaterialBatchChild)
        .where(MaterialBatchChild.parent_batch_id == batch_id)
        .order_by(MaterialBatchChild.created_at)
    )
    children = result.scalars().all()

    responses: list[MaterialBatchScanResponse] = []
    for c in children:
        child_batch = await material_batch_service.get_batch_by_id(db, c.id)
        if child_batch:
            responses.append(
                MaterialBatchScanResponse(
                    id=c.id,
                    batch_no=c.child_batch_no,
                    qr_code=c.child_qr_code,
                    qr_image_base64=None,
                    material_id=child_batch.material_id,
                    material_name=child_batch.material.name if child_batch.material else None,
                    material_grade=child_batch.material.grade if child_batch.material else None,
                    supplier_name=child_batch.supplier.name if child_batch.supplier else None,
                    thickness=child_batch.thickness,
                    width=c.width,
                    length=c.length,
                    gross_weight=c.current_weight,
                    current_weight=c.current_weight,
                    status=c.status,
                    iqc_result=None,
                    iqc_time=None,
                    received_at=None,
                    created_at=c.created_at,
                    parent_batch_id=batch_id,
                    parent_batch_no=parent.batch_no,
                )
            )
    return responses


# Supplier endpoints

@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SupplierResponse:
    """Create a new supplier - LV2: warehouse/business staff."""
    require_role(current_user, min_level=2)

    supplier = await material_batch_service.create_supplier(
        db,
        name=data.name,
        contact_person=data.contact_person,
        contact_phone=data.contact_phone,
        address=data.address,
        notes=data.notes,
    )

    return SupplierResponse(
        id=supplier.id,
        supplier_no=supplier.supplier_no,
        name=supplier.name,
        contact_person=supplier.contact_person,
        contact_phone=supplier.contact_phone,
        address=supplier.address,
        notes=supplier.notes,
        is_active=supplier.is_active,
        created_at=supplier.created_at,
    )


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SupplierResponse]:
    """List suppliers."""
    suppliers = await material_batch_service.get_suppliers(
        db, is_active=is_active, skip=skip, limit=limit
    )

    return [
        SupplierResponse(
            id=s.id,
            supplier_no=s.supplier_no,
            name=s.name,
            contact_person=s.contact_person,
            contact_phone=s.contact_phone,
            address=s.address,
            notes=s.notes,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in suppliers
    ]


# Material catalog endpoints

@router.post("/materials", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: MaterialCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialResponse:
    """Create a new material in the catalog."""
    require_role(current_user, min_level=2)

    material = await material_batch_service.create_material(
        db,
        name=data.name,
        grade=data.grade,
        thickness=data.thickness,
        width=data.width,
        weight_per_unit=data.weight_per_unit,
        unit=data.unit,
        supplier_id=data.supplier_id,
    )

    return MaterialResponse(
        id=material.id,
        material_no=material.material_no,
        name=material.name,
        grade=material.grade,
        thickness=material.thickness,
        width=material.width,
        weight_per_unit=material.weight_per_unit,
        unit=material.unit,
        supplier_id=material.supplier_id,
        supplier_name=material.supplier.name if material.supplier else None,
        is_active=material.is_active,
        created_at=material.created_at,
    )


@router.get("/materials", response_model=list[MaterialResponse])
async def list_materials(
    db: DbSession,
    current_user: CurrentUser,
    grade: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MaterialResponse]:
    """List materials in the catalog."""
    materials = await material_batch_service.get_materials(
        db, grade=grade, skip=skip, limit=limit
    )

    return [
        MaterialResponse(
            id=m.id,
            material_no=m.material_no,
            name=m.name,
            grade=m.grade,
            thickness=m.thickness,
            width=m.width,
            weight_per_unit=m.weight_per_unit,
            unit=m.unit,
            supplier_id=m.supplier_id,
            supplier_name=m.supplier.name if m.supplier else None,
            is_active=m.is_active,
            created_at=m.created_at,
        )
        for m in materials
    ]


# ── QR Scan Log ─────────────────────────────────────────────────────────────

@router.post("/scans", response_model=QRScanLogResponse, status_code=status.HTTP_201_CREATED)
async def create_scan_log(
    data: QRScanLogCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> QRScanLogResponse:
    """Record a QR code scan event."""
    log = await material_batch_service.create_scan_log(
        db,
        scan_type=data.scan_type,
        entity_id=data.entity_id,
        entity_no=data.entity_no,
        operation=data.operation,
        operator_id=current_user.id,
        notes=data.notes,
    )
    return QRScanLogResponse(
        id=log.id,
        scan_type=log.scan_type,
        entity_id=log.entity_id,
        entity_no=log.entity_no,
        operator_id=log.operator_id,
        operation=log.operation,
        notes=log.notes,
        scanned_at=log.scanned_at,
    )


@router.get("/scans/{entity_type}/{entity_id}", response_model=list[QRScanLogResponse])
async def get_scan_logs(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[QRScanLogResponse]:
    """Get scan history for a specific entity."""
    logs = await material_batch_service.get_scan_logs_by_entity(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
    )
    return [
        QRScanLogResponse(
            id=log.id,
            scan_type=log.scan_type,
            entity_id=log.entity_id,
            entity_no=log.entity_no,
            operator_id=log.operator_id,
            operation=log.operation,
            notes=log.notes,
            scanned_at=log.scanned_at,
        )
        for log in logs
    ]


# ── T026: Reprint QR ────────────────────────────────────────────────────────

@router.post("/material-batches/{batch_id}/reprint-qr", response_model=MaterialBatchScanResponse)
async def reprint_material_batch_qr(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialBatchScanResponse:
    """Reprint QR code for a material batch.

    Returns the batch info with qr_content and qr_image_base64.
    Records the reprint operation in qr_scan_logs.
    """
    batch = await material_batch_service.get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if not batch.qr_code:
        raise HTTPException(status_code=400, detail="Batch has no QR code")

    from app.services.qr_service import generate_qr_base64
    qr_image_base64 = generate_qr_base64(batch.qr_code)

    # Record reprint scan log
    await material_batch_service.create_scan_log(
        db,
        scan_type="MAT",
        entity_id=batch.id,
        entity_no=batch.batch_no,
        operation="reprint",
        operator_id=current_user.id,
        notes="QR code reprint",
    )
    await db.commit()

    return MaterialBatchScanResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        qr_code=batch.qr_code,
        qr_image_base64=qr_image_base64,
        material_name=batch.material.name if batch.material else None,
        material_grade=batch.material.grade if batch.material else None,
        supplier_name=batch.supplier.name if batch.supplier else None,
        status=batch.status.value if batch.status else None,
        lifecycle_status=batch.lifecycle_status.value if batch.lifecycle_status else None,
        gross_weight=batch.gross_weight,
        current_weight=batch.current_weight,
        thickness=batch.thickness,
        width=batch.width,
        length=batch.length,
        received_at=batch.received_at,
        iqc_result=batch.iqc_result.value if batch.iqc_result else None,
    )
