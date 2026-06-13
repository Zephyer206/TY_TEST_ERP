"""Business logic for material batch management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.production import ProductionSession
from app.models.warehouse import (
    BatchStatus,
    BatchTransaction,
    IQCResult,
    Material,
    MaterialBatch,
    MaterialBatchChild,
    Supplier,
)


def generate_batch_no() -> str:
    """Generate a unique material batch number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"MAT-{prefix}-{now.strftime('%H%M%S')}"


def generate_child_batch_no(parent_batch_no: str, index: int) -> str:
    """Generate a unique child batch number."""
    return f"{parent_batch_no}-CH{index:02d}"


async def create_material_batch(
    db: AsyncSession,
    material_id: int,
    gross_weight: float,
    supplier_id: Optional[int] = None,
    thickness: Optional[float] = None,
    width: Optional[float] = None,
    length: Optional[float] = None,
    po_no: Optional[str] = None,
) -> MaterialBatch:
    """Create a new material batch."""
    batch_no = generate_batch_no()

    batch = MaterialBatch(
        batch_no=batch_no,
        qr_code=f"QR-{batch_no}",
        material_id=material_id,
        supplier_id=supplier_id,
        thickness=thickness,
        width=width,
        length=length,
        gross_weight=gross_weight,
        net_weight=gross_weight,
        current_weight=gross_weight,
        po_no=po_no,
        status=BatchStatus.PENDING_IQC,
        received_at=datetime.utcnow(),
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


async def get_batch_by_id(
    db: AsyncSession,
    batch_id: int,
) -> Optional[MaterialBatch]:
    """Get a material batch by ID."""
    result = await db.execute(
        select(MaterialBatch)
        .options(
            joinedload(MaterialBatch.material),
            joinedload(MaterialBatch.supplier),
            selectinload(MaterialBatch.children),
        )
        .where(MaterialBatch.id == batch_id, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_batch_by_no(
    db: AsyncSession,
    batch_no: str,
) -> Optional[MaterialBatch]:
    """Get a material batch by batch number."""
    result = await db.execute(
        select(MaterialBatch)
        .options(
            joinedload(MaterialBatch.material),
            joinedload(MaterialBatch.supplier),
            selectinload(MaterialBatch.children),
        )
        .where(MaterialBatch.batch_no == batch_no, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_batches(
    db: AsyncSession,
    status: Optional[BatchStatus] = None,
    material_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[MaterialBatch]:
    """Get material batches with optional filters."""
    query = (
        select(MaterialBatch)
        .options(
            joinedload(MaterialBatch.material),
            joinedload(MaterialBatch.supplier),
        )
        .where(MaterialBatch.is_deleted == False)
    )

    if status:
        query = query.where(MaterialBatch.status == status)
    if material_id:
        query = query.where(MaterialBatch.material_id == material_id)

    query = query.order_by(MaterialBatch.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def perform_iqc(
    db: AsyncSession,
    batch: MaterialBatch,
    result: IQCResult,
    operator_id: int,
    notes: Optional[str] = None,
) -> MaterialBatch:
    """Perform IQC inspection on a material batch."""
    if batch.status != BatchStatus.PENDING_IQC:
        raise ValueError(f"Batch not pending IQC: {batch.status.value}")

    batch.iqc_result = result
    batch.iqc_time = datetime.utcnow()
    batch.iqc_by = operator_id
    batch.iqc_notes = notes

    if result == IQCResult.PASSED:
        batch.status = BatchStatus.AVAILABLE
    else:
        batch.status = BatchStatus.REJECTED

    # Record transaction
    await _record_transaction(
        db,
        batch_id=batch.id,
        batch_no=batch.batch_no,
        transaction_type="iqc",
        quantity_change=0,
        weight_after=batch.current_weight,
        reference_type="iqc",
        reference_id=operator_id,
        notes=f"IQC result: {result.value}",
    )

    await db.commit()
    await db.refresh(batch)
    return batch


async def split_batch(
    db: AsyncSession,
    batch: MaterialBatch,
    splits: list[dict],
    operator_id: Optional[int] = None,
) -> list[MaterialBatchChild]:
    """Split a material batch into child batches."""
    if batch.status not in (BatchStatus.AVAILABLE, BatchStatus.PARTIAL):
        raise ValueError(f"Batch not splittable: {batch.status.value}")

    # Validate total weight doesn't exceed current weight
    total_split_weight = sum(s.get("weight", 0) for s in splits)
    if total_split_weight > batch.current_weight + 0.001:  # Allow tiny floating point error
        raise ValueError(f"Split weight exceeds current weight: {total_split_weight} > {batch.current_weight}")

    children = []
    for idx, split in enumerate(splits, start=1):
        child_batch_no = generate_child_batch_no(batch.batch_no, idx)

        child = MaterialBatchChild(
            parent_batch_id=batch.id,
            child_batch_no=child_batch_no,
            child_qr_code=f"QR-{child_batch_no}",
            width=split.get("width", batch.width),
            length=split.get("length", batch.length),
            current_weight=split["weight"],
            status=BatchStatus.AVAILABLE,
        )
        db.add(child)
        children.append(child)

    # Update parent batch weight
    batch.current_weight -= total_split_weight
    if batch.current_weight <= 0.001:  # Nearly exhausted
        batch.status = BatchStatus.EXHAUSTED
    else:
        batch.status = BatchStatus.PARTIAL

    # Record transaction
    await _record_transaction(
        db,
        batch_id=batch.id,
        batch_no=batch.batch_no,
        transaction_type="split",
        quantity_change=-total_split_weight,
        weight_after=batch.current_weight,
        reference_type="split",
        notes=f"Split into {len(children)} child batches",
    )

    await db.commit()

    # Refresh children
    for child in children:
        await db.refresh(child)

    return children


async def consume_material(
    db: AsyncSession,
    batch: MaterialBatch,
    weight: float,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    operator_id: Optional[int] = None,
) -> MaterialBatch:
    """Consume material from a batch."""
    if batch.status not in (BatchStatus.AVAILABLE, BatchStatus.IN_USE):
        raise ValueError(f"Batch not available for consumption: {batch.status.value}")

    if weight > batch.current_weight:
        raise ValueError(f"Consumption weight exceeds current weight: {weight} > {batch.current_weight}")

    batch.current_weight -= weight

    if batch.current_weight <= 0.001:
        batch.status = BatchStatus.EXHAUSTED
    elif batch.status == BatchStatus.AVAILABLE:
        batch.status = BatchStatus.IN_USE

    # Record transaction
    await _record_transaction(
        db,
        batch_id=batch.id,
        batch_no=batch.batch_no,
        transaction_type="consume",
        quantity_change=-weight,
        weight_after=batch.current_weight,
        reference_type=reference_type,
        reference_id=reference_id,
        operator_id=operator_id,
    )

    await db.commit()
    await db.refresh(batch)
    return batch


async def scrap_batch(
    db: AsyncSession,
    batch: MaterialBatch,
    reason: str,
    operator_id: Optional[int] = None,
) -> MaterialBatch:
    """Scrap a material batch."""
    if batch.status == BatchStatus.EXHAUSTED:
        raise ValueError("Batch already exhausted")

    remaining_weight = batch.current_weight
    batch.status = BatchStatus.SCRAPPED

    # Record transaction
    await _record_transaction(
        db,
        batch_id=batch.id,
        batch_no=batch.batch_no,
        transaction_type="scrap",
        quantity_change=-remaining_weight,
        weight_after=0,
        operator_id=operator_id,
        notes=reason,
    )

    await db.commit()
    await db.refresh(batch)
    return batch


async def get_batch_transactions(
    db: AsyncSession,
    batch_id: int,
) -> Sequence[BatchTransaction]:
    """Get all transactions for a batch."""
    result = await db.execute(
        select(BatchTransaction)
        .where(BatchTransaction.batch_id == batch_id)
        .order_by(BatchTransaction.created_at.desc())
    )
    return result.scalars().all()


async def trace_batch(
    db: AsyncSession,
    batch_id: int,
) -> dict:
    """Trace a batch with all its transactions."""
    batch = await get_batch_by_id(db, batch_id)
    if not batch:
        return None

    transactions = await get_batch_transactions(db, batch_id)

    return {
        "batch": batch,
        "transactions": transactions,
    }


async def _record_transaction(
    db: AsyncSession,
    batch_id: int,
    batch_no: str,
    transaction_type: str,
    quantity_change: float,
    weight_after: float,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> BatchTransaction:
    """Record a batch transaction."""
    transaction = BatchTransaction(
        batch_id=batch_id,
        batch_no=batch_no,
        transaction_type=transaction_type,
        quantity_change=quantity_change,
        weight_after=weight_after,
        reference_type=reference_type,
        reference_id=reference_id,
        operator_id=operator_id,
        notes=notes,
    )
    db.add(transaction)
    return transaction


# Supplier operations

async def create_supplier(
    db: AsyncSession,
    name: str,
    contact_person: Optional[str] = None,
    contact_phone: Optional[str] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
) -> Supplier:
    """Create a new supplier."""
    now = datetime.utcnow()
    supplier_no = f"SUP-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

    supplier = Supplier(
        supplier_no=supplier_no,
        name=name,
        contact_person=contact_person,
        contact_phone=contact_phone,
        address=address,
        notes=notes,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def get_suppliers(
    db: AsyncSession,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Supplier]:
    """Get suppliers with optional filters."""
    query = select(Supplier)

    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)

    query = query.order_by(Supplier.name).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


# Material operations

async def create_material(
    db: AsyncSession,
    name: str,
    grade: str,
    thickness: Optional[float] = None,
    width: Optional[float] = None,
    weight_per_unit: Optional[float] = None,
    unit: str = "kg",
    supplier_id: Optional[int] = None,
) -> Material:
    """Create a new material."""
    now = datetime.utcnow()
    material_no = f"MAT-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

    material = Material(
        material_no=material_no,
        name=name,
        grade=grade,
        thickness=thickness,
        width=width,
        weight_per_unit=weight_per_unit,
        unit=unit,
        supplier_id=supplier_id,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


async def get_materials(
    db: AsyncSession,
    grade: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Material]:
    """Get materials with optional filters."""
    query = select(Material).where(Material.is_active == True)

    if grade:
        query = query.where(Material.grade.ilike(f"%{grade}%"))

    query = query.order_by(Material.grade, Material.name).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()
