"""Business logic for packaging management."""

import secrets
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.part import Part
from app.models.packaging import (
    FinishedGoodsInventory,
    InspectionResult,
    InventoryTransaction,
    PackagingRecord,
    PackagingStatus,
)
from app.models.user import User


def generate_record_no(db: AsyncSession) -> str:
    """Generate a unique packaging record number."""
    now = datetime.utcnow()
    suffix = secrets.token_hex(3).upper()[:6]
    return f"PKG-{now.strftime('%Y%m%d')}-{suffix}"


def generate_transaction_no(db: AsyncSession) -> str:
    """Generate a unique transaction number."""
    now = datetime.utcnow()
    suffix = secrets.token_hex(3).upper()[:6]
    return f"INV-{now.strftime('%Y%m%d')}-{suffix}"


# Packaging Record Operations

async def create_packaging_record(
    db: AsyncSession,
    data: dict,
    operator: User,
) -> PackagingRecord:
    """Create a new packaging record from scan."""
    # Validate part exists
    part_result = await db.execute(select(Part).where(Part.id == data["part_id"]))
    part = part_result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    record_no = generate_record_no(db)

    record = PackagingRecord(
        record_no=record_no,
        part_id=data["part_id"],
        quantity=data["quantity"],
        box_barcode=data.get("box_barcode"),
        packaging_type=data.get("packaging_type"),
        box_no=data.get("box_no"),
        gross_weight=data.get("gross_weight"),
        net_weight=data.get("net_weight"),
        production_batch_no=data.get("production_batch_no"),
        process_flow_no=data.get("process_flow_no"),
        notes=data.get("notes"),
        status=PackagingStatus.SCANNED,
        scanned_by=operator.id if hasattr(operator, 'id') else None,
        scanned_at=datetime.utcnow(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_record_by_id(
    db: AsyncSession,
    record_id: int,
) -> Optional[PackagingRecord]:
    """Get packaging record by ID."""
    result = await db.execute(
        select(PackagingRecord)
        .options(selectinload(PackagingRecord.part))
        .where(
            PackagingRecord.id == record_id,
            PackagingRecord.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_record_by_barcode(
    db: AsyncSession,
    box_barcode: str,
) -> Optional[PackagingRecord]:
    """Get packaging record by box barcode."""
    result = await db.execute(
        select(PackagingRecord)
        .options(selectinload(PackagingRecord.part))
        .where(
            PackagingRecord.box_barcode == box_barcode,
            PackagingRecord.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_records(
    db: AsyncSession,
    part_id: Optional[int] = None,
    status: Optional[PackagingStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[PackagingRecord]:
    """Get packaging records with filters."""
    query = (
        select(PackagingRecord)
        .options(selectinload(PackagingRecord.part))
        .where(PackagingRecord.is_deleted == False)
    )

    if part_id:
        query = query.where(PackagingRecord.part_id == part_id)
    if status:
        query = query.where(PackagingRecord.status == status)

    query = query.order_by(PackagingRecord.scanned_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def process_inspection(
    db: AsyncSession,
    record: PackagingRecord,
    inspected_qty: int,
    passed_qty: int,
    rejected_qty: int,
    visual_result: Optional[str],
    notes: Optional[str],
    warehouse_location: Optional[str],
    shelf_location: Optional[str],
    inspector: User,
) -> PackagingRecord:
    """Process packaging inspection and update inventory."""
    # Validate quantities
    if passed_qty + rejected_qty != inspected_qty:
        raise ValueError("passed_qty + rejected_qty must equal inspected_qty")

    # Update record
    record.status = PackagingStatus.PASSED if rejected_qty == 0 else PackagingStatus.REJECTED
    record.inspected_qty = inspected_qty
    record.passed_qty = passed_qty
    record.rejected_qty = rejected_qty
    record.inspection_notes = notes
    record.visual_inspection_result = InspectionResult(visual_result) if visual_result else None
    record.visual_inspection_by = inspector.id if hasattr(inspector, 'id') else None
    record.visual_inspection_at = datetime.utcnow()

    # If passed, update stock
    if rejected_qty == 0:
        record.stock_qty = passed_qty
        record.warehouse_location = warehouse_location
        record.shelf_location = shelf_location

        # Update or create inventory
        await _update_inventory(
            db,
            part_id=record.part_id,
            quantity_change=passed_qty,
            warehouse_location=warehouse_location or "",
            shelf_location=shelf_location,
            batch_no=record.production_batch_no,
            operator=inspector,
            reference_type="packaging",
            reference_id=record.id,
        )

    await db.commit()
    await db.refresh(record)
    return record


async def _update_inventory(
    db: AsyncSession,
    part_id: int,
    quantity_change: int,
    warehouse_location: str,
    shelf_location: Optional[str],
    batch_no: Optional[str],
    operator: User,
    reference_type: Optional[str],
    reference_id: Optional[int],
) -> FinishedGoodsInventory:
    """Update finished goods inventory and create transaction."""
    # Find or create inventory record
    result = await db.execute(
        select(FinishedGoodsInventory).where(
            FinishedGoodsInventory.part_id == part_id,
            FinishedGoodsInventory.warehouse_location == warehouse_location,
        )
    )
    inventory = result.scalar_one_or_none()

    quantity_before = 0
    if inventory:
        quantity_before = inventory.quantity
        inventory.quantity += quantity_change
        inventory.latest_batch_no = batch_no
        inventory.latest_production_date = datetime.utcnow()
        if shelf_location:
            inventory.shelf_location = shelf_location
    else:
        inventory = FinishedGoodsInventory(
            part_id=part_id,
            warehouse_location=warehouse_location,
            shelf_location=shelf_location,
            quantity=quantity_change,
            latest_batch_no=batch_no,
            latest_production_date=datetime.utcnow(),
        )
        db.add(inventory)

    # Create transaction record
    transaction_no = generate_transaction_no(db)
    transaction = InventoryTransaction(
        transaction_no=transaction_no,
        part_id=part_id,
        transaction_type="STOCK_IN",
        quantity_before=quantity_before,
        quantity_change=quantity_change,
        quantity_after=quantity_before + quantity_change,
        reference_type=reference_type,
        reference_id=reference_id,
        warehouse_location=warehouse_location,
        operated_by=operator.id if hasattr(operator, 'id') else None,
    )
    db.add(transaction)

    await db.flush()
    return inventory


# Inventory Operations

async def get_inventory(
    db: AsyncSession,
    part_id: Optional[int] = None,
    warehouse_location: Optional[str] = None,
) -> Sequence[FinishedGoodsInventory]:
    """Get finished goods inventory."""
    query = (
        select(FinishedGoodsInventory)
        .options(selectinload(FinishedGoodsInventory.part))
        .where(FinishedGoodsInventory.quantity > 0)
    )

    if part_id:
        query = query.where(FinishedGoodsInventory.part_id == part_id)
    if warehouse_location:
        query = query.where(FinishedGoodsInventory.warehouse_location == warehouse_location)

    result = await db.execute(query)
    return result.scalars().all()


async def get_transactions(
    db: AsyncSession,
    part_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[InventoryTransaction]:
    """Get inventory transactions."""
    query = (
        select(InventoryTransaction)
        .options(selectinload(InventoryTransaction.part))
    )

    if part_id:
        query = query.where(InventoryTransaction.part_id == part_id)
    if transaction_type:
        query = query.where(InventoryTransaction.transaction_type == transaction_type)

    query = query.order_by(InventoryTransaction.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def adjust_inventory(
    db: AsyncSession,
    part_id: int,
    warehouse_location: str,
    quantity_change: int,
    reason: str,
    operator: User,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
) -> FinishedGoodsInventory:
    """Adjust inventory manually."""
    # Find inventory
    result = await db.execute(
        select(FinishedGoodsInventory).where(
            FinishedGoodsInventory.part_id == part_id,
            FinishedGoodsInventory.warehouse_location == warehouse_location,
        )
    )
    inventory = result.scalar_one_or_none()

    quantity_before = 0
    transaction_type = "ADJUSTMENT"

    if quantity_change > 0:
        transaction_type = "STOCK_IN"
    else:
        transaction_type = "STOCK_OUT"

    if inventory:
        if inventory.quantity + quantity_change < 0:
            raise ValueError("Insufficient inventory")
        quantity_before = inventory.quantity
        inventory.quantity += quantity_change
    else:
        if quantity_change < 0:
            raise ValueError("Inventory not found")
        inventory = FinishedGoodsInventory(
            part_id=part_id,
            warehouse_location=warehouse_location,
            quantity=quantity_change,
        )
        db.add(inventory)

    # Create transaction
    transaction_no = generate_transaction_no(db)
    transaction = InventoryTransaction(
        transaction_no=transaction_no,
        part_id=part_id,
        transaction_type=transaction_type,
        quantity_before=quantity_before,
        quantity_change=quantity_change,
        quantity_after=quantity_before + quantity_change,
        reference_type=reference_type or "ADJUSTMENT",
        reference_id=reference_id,
        warehouse_location=warehouse_location,
        operated_by=operator.id if hasattr(operator, 'id') else None,
        notes=reason,
    )
    db.add(transaction)

    await db.commit()
    await db.refresh(inventory)
    return inventory
