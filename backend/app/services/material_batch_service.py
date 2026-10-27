"""Business logic for material batch management."""

from datetime import datetime
from decimal import Decimal
import math
from uuid import uuid4
from typing import Optional, Sequence

from sqlalchemy import func, select
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
    return f"MAT-{prefix}-{uuid4().hex[:16]}"


def generate_qr_uid() -> str:
    """Generate a unique QR UID (used as the actual unique identifier)."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"MAT-{prefix}-{uuid4().hex[:16]}"


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
    operator_id: Optional[int] = None,
    commit: bool = True,
) -> MaterialBatch:
    """Create a new material batch with auto QR code generation."""
    from app.services.qr_service import generate_material_batch_qr

    _positive_weight(gross_weight)

    qr_uid = generate_qr_uid()
    batch_no = generate_batch_no()

    batch = MaterialBatch(
        qr_uid=qr_uid,
        batch_no=batch_no,
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
    await db.flush()

    batch.qr_code = generate_material_batch_qr(batch.id)
    await _record_transaction(db, batch.id, batch.batch_no, "receive", gross_weight, gross_weight,
                              operator_id=operator_id, reference_type="inbound")
    await db.flush()
    if commit:
        await db.commit()
    return await get_batch_by_id(db, batch.id)


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
    commit: bool = True,
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
        operator_id=operator_id,
        notes=f"IQC result: {result.value}",
    )

    await db.flush()
    if commit:
        await db.commit()
    return await get_batch_by_id(db, batch.id)


async def split_batch(
    db: AsyncSession,
    batch: MaterialBatch,
    splits: list[dict],
    operator_id: Optional[int] = None,
    commit: bool = True,
) -> list[MaterialBatch]:
    """Split a material batch into child batches (single-table design).

    Each child is an independent MaterialBatch with parent_batch_id set.
    Every child gets its own unique QR code.
    """
    from app.services.qr_service import generate_material_batch_qr

    batch = await _locked_batch(db, batch.id)
    if not splits:
        raise ValueError("At least one split is required")
    for split in splits:
        _positive_weight(split.get("weight"))

    if batch.status not in (BatchStatus.AVAILABLE, BatchStatus.PARTIAL):
        raise ValueError(f"Batch not splittable: {batch.status.value}")

    total_split_weight = sum(s.get("weight", 0) for s in splits)
    if total_split_weight > batch.current_weight + 0.001:
        raise ValueError(
            f"Split weight exceeds current weight: {total_split_weight} > {batch.current_weight}"
        )

    existing_names = list((await db.execute(select(MaterialBatch.batch_no).where(
        MaterialBatch.parent_batch_id == batch.id))).scalars())
    existing_names += list((await db.execute(select(MaterialBatchChild.child_batch_no).where(
        MaterialBatchChild.parent_batch_id == batch.id))).scalars())
    existing_indices = [int(name.rsplit("-CH", 1)[-1]) for name in existing_names
                        if name and "-CH" in name and name.rsplit("-CH", 1)[-1].isdigit()]
    next_index = max(existing_indices, default=0) + 1
    parent_number = batch.batch_no or batch.qr_uid
    names = [generate_child_batch_no(parent_number, i) for i in range(next_index, next_index + len(splits))]
    if any(len(name) > 100 for name in names):
        raise ValueError("Child batch number is too long")
    children: list[MaterialBatch] = []
    for child_batch_no, split in zip(names, splits):

        child = MaterialBatch(
            qr_uid=generate_qr_uid(),
            batch_no=child_batch_no,
            qr_code=None,  # 生成后赋值
            material_id=batch.material_id,
            supplier_id=batch.supplier_id,
            thickness=batch.thickness,
            width=split.get("width") or batch.width,
            length=split.get("length") or batch.length,
            gross_weight=split["weight"],
            net_weight=split["weight"],
            current_weight=split["weight"],
            status=BatchStatus.AVAILABLE,
            parent_batch_id=batch.id,
            received_at=datetime.utcnow(),
        )
        db.add(child)
        await db.flush()

        child.qr_code = generate_material_batch_qr(child.id)
        children.append(child)

    # 更新母卷
    batch.current_weight -= total_split_weight
    if batch.current_weight <= 0.001:
        batch.status = BatchStatus.EXHAUSTED
    else:
        batch.status = BatchStatus.PARTIAL

    # 记录分条事务
    await _record_transaction(
        db,
        batch_id=batch.id,
        batch_no=batch.batch_no,
        transaction_type="split",
        quantity_change=-total_split_weight,
        weight_after=batch.current_weight,
        reference_type="split",
        operator_id=operator_id,
        notes=f"Split into {len(children)} child batches: {[c.batch_no for c in children]}",
    )

    # 记录各子卷入库事务
    for child in children:
        await _record_transaction(
            db,
            batch_id=child.id,
            batch_no=child.batch_no,
            transaction_type="receive",
            quantity_change=child.current_weight,
            weight_after=child.current_weight,
            reference_type="split",
            reference_id=batch.id,
            operator_id=operator_id,
            notes=f"Split from parent batch {batch.batch_no}",
        )

    await db.flush()
    if commit:
        await db.commit()
    return list((await db.execute(select(MaterialBatch).options(
        joinedload(MaterialBatch.material), joinedload(MaterialBatch.supplier)).where(
        MaterialBatch.id.in_([child.id for child in children])).order_by(MaterialBatch.id))).scalars())


async def consume_material(
    db: AsyncSession,
    batch: MaterialBatch,
    weight: float,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    commit: bool = True,
) -> MaterialBatch:
    """Consume material from a batch."""
    _positive_weight(weight)
    batch = await _locked_batch(db, batch.id)
    if batch.status not in (BatchStatus.AVAILABLE, BatchStatus.IN_USE, BatchStatus.PARTIAL):
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

    await db.flush()
    if commit:
        await db.commit()
    return await get_batch_by_id(db, batch.id)


def _positive_weight(weight):
    if (isinstance(weight, bool) or not isinstance(weight, (int, float, Decimal))
            or not math.isfinite(weight) or weight <= 0):
        raise ValueError("Weight must be a positive finite number")


async def _locked_batch(db, batch_id):
    row = (await db.execute(select(MaterialBatch).where(
        MaterialBatch.id == batch_id, MaterialBatch.is_deleted.is_(False)).with_for_update()
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None or row.current_weight is None or not math.isfinite(row.current_weight):
        raise ValueError("Material batch is unavailable")
    return row


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
    include_inactive: bool = False,
) -> Sequence[Material]:
    """Get materials with optional filters."""
    query = select(Material).options(joinedload(Material.supplier))
    if not include_inactive:
        query = query.where(Material.is_active == True)

    if grade:
        query = query.where(Material.grade.ilike(f"%{grade}%"))

    query = query.order_by(Material.grade, Material.name).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


# ── QR Scan Log ─────────────────────────────────────────────────────────────

async def create_scan_log(
    db: AsyncSession,
    scan_type: str,
    entity_id: int,
    operation: str,
    entity_no: Optional[str] = None,
    operator_id: Optional[int] = None,
    notes: Optional[str] = None,
):
    """Record a QR code scan event."""
    from app.models.warehouse import QRScanLog

    log = QRScanLog(
        scan_type=scan_type,
        entity_id=entity_id,
        entity_no=entity_no,
        operator_id=operator_id,
        operation=operation,
        notes=notes,
    )
    db.add(log)
    await db.flush()
    return log


async def get_scan_logs_by_entity(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    skip: int = 0,
    limit: int = 50,
):
    """Get scan history for a specific entity."""
    from app.models.warehouse import QRScanLog

    result = await db.execute(
        select(QRScanLog)
        .where(QRScanLog.scan_type == entity_type.upper())
        .where(QRScanLog.entity_id == entity_id)
        .order_by(QRScanLog.scanned_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


# ── Child Batch (Single-Table) ───────────────────────────────────────────────

async def get_child_batch_by_id(
    db: AsyncSession,
    child_id: int,
) -> Optional[MaterialBatch]:
    """Get a child batch (which is a MaterialBatch with parent_batch_id set)."""
    result = await db.execute(
        select(MaterialBatch)
        .options(
            joinedload(MaterialBatch.material),
            joinedload(MaterialBatch.supplier),
        )
        .where(MaterialBatch.id == child_id, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_parent_batch(
    db: AsyncSession,
    parent_id: int,
) -> Optional[MaterialBatch]:
    """Get a parent batch with its children eagerly loaded."""
    result = await db.execute(
        select(MaterialBatch)
        .options(
            joinedload(MaterialBatch.material),
            joinedload(MaterialBatch.supplier),
            selectinload(MaterialBatch.children),
        )
        .where(MaterialBatch.id == parent_id, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_sibling_batches(
    db: AsyncSession,
    parent_batch_id: int,
    exclude_id: Optional[int] = None,
) -> Sequence[MaterialBatch]:
    """Get all sibling batches (same parent)."""
    query = (
        select(MaterialBatch)
        .options(
            joinedload(MaterialBatch.material),
            joinedload(MaterialBatch.supplier),
        )
        .where(
            MaterialBatch.parent_batch_id == parent_batch_id,
            MaterialBatch.is_deleted == False,
        )
    )
    if exclude_id is not None:
        query = query.where(MaterialBatch.id != exclude_id)
    return (await db.execute(query.order_by(MaterialBatch.created_at, MaterialBatch.id))).scalars().all()
