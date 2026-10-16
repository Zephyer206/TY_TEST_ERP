"""Business logic for packaging management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.part import Part
from app.models.packaging import (
    Inventory,
    InventoryTransaction,
    PackagingRecord,
    PackagingStatus,
)
from app.models.production import ProductionSession


def generate_package_no() -> str:
    """Generate a unique package number."""
    now = datetime.utcnow()
    return f"PKG-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


async def create_packaging_record(
    db: AsyncSession,
    part_id: int,
    package_qty: int,
    box_no: Optional[str] = None,
    session_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> PackagingRecord:
    """Create a packaging record from scan."""
    package_no = generate_package_no()

    record = PackagingRecord(
        package_no=package_no,
        part_id=part_id,
        session_id=session_id,
        package_qty=package_qty,
        box_no=box_no,
        status=PackagingStatus.SCANNED,
        operator_id=operator_id,
        notes=notes,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_packaging_record(
    db: AsyncSession,
    record_id: int,
) -> Optional[PackagingRecord]:
    """Get a packaging record by ID."""
    result = await db.execute(
        select(PackagingRecord)
        .options(
            joinedload(PackagingRecord.part),
            joinedload(PackagingRecord.session),
        )
        .where(PackagingRecord.id == record_id)
    )
    return result.scalar_one_or_none()


async def get_packaging_record_by_no(
    db: AsyncSession,
    package_no: str,
) -> Optional[PackagingRecord]:
    """Get a packaging record by package number."""
    result = await db.execute(
        select(PackagingRecord)
        .options(
            joinedload(PackagingRecord.part),
            joinedload(PackagingRecord.session),
        )
        .where(PackagingRecord.package_no == package_no)
    )
    return result.scalar_one_or_none()


async def get_packaging_records(
    db: AsyncSession,
    part_id: Optional[int] = None,
    status: Optional[PackagingStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[PackagingRecord]:
    """Get packaging records with filters."""
    query = (
        select(PackagingRecord)
        .options(joinedload(PackagingRecord.part))
        .where(PackagingRecord.id > 0)
    )

    if part_id:
        query = query.where(PackagingRecord.part_id == part_id)
    if status:
        query = query.where(PackagingRecord.status == status)

    query = query.order_by(PackagingRecord.scanned_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def inspect_packaging(
    db: AsyncSession,
    record: PackagingRecord,
    passed: bool,
    inspected_by: int,
    notes: Optional[str] = None,
) -> PackagingRecord:
    """Perform inspection on packaging record and update inventory if passed."""
    if record.status != PackagingStatus.SCANNED:
        raise ValueError(f"Record already inspected: {record.status.value}")

    record.status = PackagingStatus.PASSED if passed else PackagingStatus.REJECTED
    record.inspected_by = inspected_by
    record.inspected_at = datetime.utcnow()
    record.inspection_notes = notes

    # Update inventory if passed
    if passed:
        await _update_inventory(
            db,
            part_id=record.part_id,
            quantity=record.package_qty,
            transaction_type="incoming",
            reference_type="packaging_record",
            reference_id=record.id,
            operator_id=inspected_by,
            reason="全检合格入库",
        )

    await db.commit()
    await db.refresh(record)
    return record


async def get_inventory(
    db: AsyncSession,
    part_id: int,
) -> Optional[Inventory]:
    """Get inventory for a part."""
    result = await db.execute(
        select(Inventory).where(Inventory.part_id == part_id)
    )
    return result.scalar_one_or_none()


async def get_inventories(
    db: AsyncSession,
    part_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Inventory]:
    """Get inventories with optional filters."""
    query = (
        select(Inventory)
        .options(joinedload(Inventory.part))
        .where(Inventory.id > 0)
    )

    if part_id:
        query = query.where(Inventory.part_id == part_id)

    query = query.order_by(Inventory.last_update_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def adjust_inventory(
    db: AsyncSession,
    part_id: int,
    quantity: int,
    reason: str,
    operator_id: Optional[int] = None,
) -> Inventory:
    """Adjust inventory quantity manually."""
    inventory = await get_inventory(db, part_id)

    if not inventory:
        # Create new inventory record
        inventory = Inventory(
            part_id=part_id,
            stock_qty=0,
            reserved_qty=0,
            last_update_by=operator_id,
        )
        db.add(inventory)
        await db.flush()

    stock_before = inventory.stock_qty
    inventory.stock_qty += quantity
    inventory.last_update_by = operator_id
    inventory.last_update_at = datetime.utcnow()

    if inventory.stock_qty < 0:
        raise ValueError("Inventory cannot be negative")

    await db.execute(
        update(Part)
        .where(Part.id == part_id)
        .values(stock_pcs=inventory.stock_qty, updated_at=datetime.utcnow())
    )

    # Record transaction
    await _record_inventory_transaction(
        db,
        part_id=part_id,
        transaction_type="adjustment",
        quantity=quantity,
        stock_before=stock_before,
        stock_after=inventory.stock_qty,
        reference_type="adjustment",
        operator_id=operator_id,
        reason=reason,
    )

    await db.commit()
    await db.refresh(inventory)
    return inventory


async def get_inventory_transactions(
    db: AsyncSession,
    part_id: int,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[InventoryTransaction]:
    """Get inventory transactions for a part."""
    result = await db.execute(
        select(InventoryTransaction)
        .where(InventoryTransaction.part_id == part_id)
        .order_by(InventoryTransaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def _update_inventory(
    db: AsyncSession,
    part_id: int,
    quantity: int,
    transaction_type: str,
    reference_type: str,
    reference_id: int,
    operator_id: Optional[int],
    reason: str,
) -> Inventory:
    """Update inventory and record transaction."""
    inventory = await get_inventory(db, part_id)

    if not inventory:
        inventory = Inventory(
            part_id=part_id,
            stock_qty=0,
            reserved_qty=0,
            last_update_by=operator_id,
        )
        db.add(inventory)
        await db.flush()

    stock_before = inventory.stock_qty
    inventory.stock_qty += quantity
    inventory.last_update_by = operator_id
    inventory.last_update_at = datetime.utcnow()

    await db.execute(
        update(Part)
        .where(Part.id == part_id)
        .values(stock_pcs=inventory.stock_qty, updated_at=datetime.utcnow())
    )

    await _record_inventory_transaction(
        db,
        part_id=part_id,
        transaction_type=transaction_type,
        quantity=quantity,
        stock_before=stock_before,
        stock_after=inventory.stock_qty,
        reference_type=reference_type,
        reference_id=reference_id,
        operator_id=operator_id,
        reason=reason,
    )

    return inventory


async def _record_inventory_transaction(
    db: AsyncSession,
    part_id: int,
    transaction_type: str,
    quantity: int,
    stock_before: int,
    stock_after: int,
    reference_type: Optional[str],
    reference_id: Optional[int],
    operator_id: Optional[int],
    reason: Optional[str],
) -> InventoryTransaction:
    """Record an inventory transaction."""
    transaction = InventoryTransaction(
        part_id=part_id,
        transaction_type=transaction_type,
        quantity=quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_type=reference_type,
        reference_id=reference_id,
        operator_id=operator_id,
        reason=reason,
    )
    db.add(transaction)
    return transaction
