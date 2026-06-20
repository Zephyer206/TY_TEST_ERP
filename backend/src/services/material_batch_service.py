"""Business logic for warehouse and material batch management."""

import secrets
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.warehouse import (
    IQCResult,
    MaterialBatch,
    MaterialBatchChild,
    MaterialConsumptionLog,
    MaterialStatus,
    Supplier,
)
from app.models.user import User
from app.schemas.warehouse import (
    IQCUpdate,
    MaterialBatchCreate,
    MaterialBatchUpdate,
    SplitRequest,
    SplitSpecItem,
)


def generate_batch_no(db: AsyncSession) -> str:
    """Generate a unique batch number."""
    now = datetime.utcnow()
    suffix = secrets.token_hex(4).upper()[:6]
    return f"MAT-{now.strftime('%Y%m%d')}-{suffix}"


def generate_qr_code() -> str:
    """Generate a unique QR code."""
    return f"MCN-{secrets.token_hex(8).upper()}"


async def create_material_batch(
    db: AsyncSession,
    data: MaterialBatchCreate,
    operator: User,
) -> MaterialBatch:
    """Create a new material batch."""
    batch_no = generate_batch_no(db)
    qr_code = generate_qr_code()

    batch = MaterialBatch(
        batch_no=batch_no,
        qr_code=qr_code,
        material_grade=data.material_grade,
        material_type=data.material_type,
        thickness=data.thickness,
        width=data.width,
        weight_kg=data.weight_kg,
        original_weight_kg=data.weight_kg,
        supplier_id=data.supplier_id,
        purchase_order_no=data.purchase_order_no,
        invoice_no=data.invoice_no,
        unit_price=data.unit_price,
        total_amount=data.unit_price * data.weight_kg if data.unit_price else None,
        warehouse_location=data.warehouse_location,
        shelf_location=data.shelf_location,
        notes=data.notes,
        status=MaterialStatus.PENDING_IQC,
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
    """Get material batch by ID."""
    result = await db.execute(
        select(MaterialBatch)
        .options(selectinload(MaterialBatch.supplier))
        .where(MaterialBatch.id == batch_id, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_batch_by_no(
    db: AsyncSession,
    batch_no: str,
) -> Optional[MaterialBatch]:
    """Get material batch by batch number."""
    result = await db.execute(
        select(MaterialBatch)
        .options(selectinload(MaterialBatch.supplier))
        .where(MaterialBatch.batch_no == batch_no, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_batch_by_qr(
    db: AsyncSession,
    qr_code: str,
) -> Optional[MaterialBatch]:
    """Get material batch by QR code."""
    result = await db.execute(
        select(MaterialBatch)
        .options(selectinload(MaterialBatch.supplier))
        .where(MaterialBatch.qr_code == qr_code, MaterialBatch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_batches(
    db: AsyncSession,
    status: Optional[MaterialStatus] = None,
    material_grade: Optional[str] = None,
    supplier_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[MaterialBatch]:
    """Get material batches with optional filters."""
    query = (
        select(MaterialBatch)
        .options(selectinload(MaterialBatch.supplier))
        .where(MaterialBatch.is_deleted == False)
    )

    if status:
        query = query.where(MaterialBatch.status == status)
    if material_grade:
        query = query.where(MaterialBatch.material_grade.ilike(f"%{material_grade}%"))
    if supplier_id:
        query = query.where(MaterialBatch.supplier_id == supplier_id)

    query = query.order_by(MaterialBatch.received_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_batch(
    db: AsyncSession,
    batch: MaterialBatch,
    data: MaterialBatchUpdate,
) -> MaterialBatch:
    """Update material batch fields."""
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None and hasattr(batch, field):
            setattr(batch, field, value)

    await db.commit()
    await db.refresh(batch)
    return batch


async def process_iqc(
    db: AsyncSession,
    batch: MaterialBatch,
    data: IQCUpdate,
    inspector: User,
) -> MaterialBatch:
    """Process incoming quality check."""
    batch.iqc_result = data.result
    batch.iqc_by = inspector.id if hasattr(inspector, 'id') else None
    batch.iqc_at = datetime.utcnow()
    batch.iqc_notes = data.notes

    if data.result == IQCResult.PASS:
        batch.status = MaterialStatus.AVAILABLE
    elif data.result == IQCResult.FAIL:
        batch.status = MaterialStatus.REJECTED
    else:  # CONDITIONAL
        batch.status = MaterialStatus.AVAILABLE

    await db.commit()
    await db.refresh(batch)
    return batch


async def split_batch(
    db: AsyncSession,
    batch: MaterialBatch,
    data: SplitRequest,
    operator: User,
) -> dict:
    """Split a material batch into multiple child batches."""
    if batch.status not in (MaterialStatus.AVAILABLE, MaterialStatus.IN_USE):
        raise ValueError(f"Cannot split batch in status: {batch.status.value}")

    total_split_weight = sum(
        (s.weight_kg or 0) for s in data.split_specs
    )

    # Allow small tolerance for weight difference
    if abs(total_split_weight - batch.weight_kg) > 0.1:
        raise ValueError(
            f"Split weight total ({total_split_weight}) does not match batch weight ({batch.weight_kg})"
        )

    # Update parent batch status
    batch.status = MaterialStatus.SPLIT
    batch.slit_pieces = len(data.split_specs)
    batch.slit_width = max(s.width for s in data.split_specs)

    children = []
    for spec in data.split_specs:
        child_batch_no = f"{batch.batch_no}-S{spec.position_index + 1:02d}"
        child_qr_code = generate_qr_code()

        weight = spec.weight_kg or (batch.weight_kg / len(data.split_specs))

        child = MaterialBatchChild(
            child_batch_no=child_batch_no,
            qr_code=child_qr_code,
            parent_batch_id=batch.id,
            width=spec.width,
            weight_kg=weight,
            pieces=spec.pieces,
            position_index=spec.position_index,
            status=MaterialStatus.AVAILABLE,
            warehouse_location=spec.warehouse_location or batch.warehouse_location,
            shelf_location=spec.shelf_location or batch.shelf_location,
        )
        db.add(child)
        children.append(child)

    await db.commit()

    # Refresh children
    for child in children:
        await db.refresh(child)

    return {
        "parent_batch_id": batch.id,
        "parent_batch_no": batch.batch_no,
        "parent_status": batch.status,
        "children": children,
    }


async def get_batch_children(
    db: AsyncSession,
    batch_id: int,
) -> Sequence[MaterialBatchChild]:
    """Get all child batches for a parent batch."""
    result = await db.execute(
        select(MaterialBatchChild)
        .where(
            MaterialBatchChild.parent_batch_id == batch_id,
        )
        .order_by(MaterialBatchChild.position_index)
    )
    return result.scalars().all()


async def trace_batch(
    db: AsyncSession,
    batch: MaterialBatch,
) -> dict:
    """Generate trace history for a material batch."""
    entries = []

    # 1. Received entry
    entries.append({
        "timestamp": batch.received_at,
        "event_type": "received",
        "description": f"原材料入库，批次号: {batch.batch_no}",
        "reference_no": batch.batch_no,
        "details": {
            "material_grade": batch.material_grade,
            "weight_kg": batch.original_weight_kg,
            "supplier_id": batch.supplier_id,
        },
    })

    # 2. IQC entry
    if batch.iqc_at:
        entries.append({
            "timestamp": batch.iqc_at,
            "event_type": "iqc",
            "description": f"IQC检验完成，结果: {batch.iqc_result.value if batch.iqc_result else 'N/A'}",
            "operator_id": batch.iqc_by,
            "reference_no": batch.batch_no,
            "details": {
                "result": batch.iqc_result.value if batch.iqc_result else None,
                "notes": batch.iqc_notes,
            },
        })

    # 3. Split entry (if applicable)
    if batch.status == MaterialStatus.SPLIT:
        children = await get_batch_children(db, batch.id)
        entries.append({
            "timestamp": datetime.utcnow(),
            "event_type": "split",
            "description": f"分条操作，分成 {len(children)} 个子卷",
            "reference_no": batch.batch_no,
            "details": {
                "children": [
                    {
                        "child_batch_no": c.child_batch_no,
                        "width": c.width,
                        "weight_kg": c.weight_kg,
                    }
                    for c in children
                ],
            },
        })

    # 4. Consumption entries
    result = await db.execute(
        select(MaterialConsumptionLog)
        .where(MaterialConsumptionLog.batch_id == batch.id)
        .order_by(MaterialConsumptionLog.consumed_at)
    )
    consumption_logs = result.scalars().all()

    for log in consumption_logs:
        entries.append({
            "timestamp": log.consumed_at,
            "event_type": "consumed",
            "description": f"消耗 {log.quantity_kg} kg - {log.purpose}",
            "operator_id": log.consumed_by,
            "reference_no": f"session_{log.production_session_id}" if log.production_session_id else None,
            "details": {
                "quantity_kg": log.quantity_kg,
                "purpose": log.purpose,
                "production_session_id": log.production_session_id,
            },
        })

    # Sort entries by timestamp
    entries.sort(key=lambda x: x["timestamp"])

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "qr_code": batch.qr_code,
        "material_grade": batch.material_grade,
        "current_status": batch.status,
        "original_weight_kg": batch.original_weight_kg,
        "current_weight_kg": batch.weight_kg,
        "entries": entries,
    }


async def consume_material(
    db: AsyncSession,
    batch_id: Optional[int],
    child_batch_id: Optional[int],
    quantity_kg: float,
    purpose: str,
    production_session_id: Optional[int] = None,
    operator: User = None,
) -> MaterialBatch:
    """Record material consumption."""
    if batch_id:
        batch = await get_batch_by_id(db, batch_id)
    elif child_batch_id:
        result = await db.execute(
            select(MaterialBatchChild).where(MaterialBatchChild.id == child_batch_id)
        )
        batch = result.scalar_one_or_none()
        if batch:
            batch.weight_kg -= quantity_kg
    else:
        raise ValueError("Either batch_id or child_batch_id must be provided")

    if not batch:
        raise ValueError("Batch not found")

    if batch.weight_kg < quantity_kg:
        raise ValueError("Insufficient material quantity")

    # Create consumption log
    log = MaterialConsumptionLog(
        batch_id=batch_id,
        child_batch_id=child_batch_id,
        quantity_kg=quantity_kg,
        purpose=purpose,
        production_session_id=production_session_id,
        consumed_by=operator.id if operator and hasattr(operator, 'id') else None,
    )
    db.add(log)

    # Update batch weight
    batch.weight_kg -= quantity_kg
    batch.consumed_qty += quantity_kg

    # Check if fully consumed
    if batch.weight_kg <= 0:
        batch.status = MaterialStatus.CONSUMED
        batch.weight_kg = 0

    await db.commit()
    await db.refresh(batch)
    return batch


# Supplier functions

async def create_supplier(
    db: AsyncSession,
    data: dict,
) -> Supplier:
    """Create a new supplier."""
    supplier = Supplier(**data)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def get_suppliers(
    db: AsyncSession,
    is_active: Optional[bool] = None,
) -> Sequence[Supplier]:
    """Get all suppliers."""
    query = select(Supplier)

    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)

    query = query.order_by(Supplier.code)
    result = await db.execute(query)
    return result.scalars().all()
