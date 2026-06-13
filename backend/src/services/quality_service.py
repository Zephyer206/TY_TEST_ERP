"""Business logic for quality inspection and release management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.part import Part
from app.models.production import ProductionSession
from app.models.quality import (
    ExemptionType,
    FirstPieceInspection,
    InspectionResult,
    OQCInspection,
    QAExemption,
    PatrolInspection,
)


def generate_inspection_no(prefix: str) -> str:
    """Generate a unique inspection number."""
    now = datetime.utcnow()
    return f"{prefix}-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


async def create_first_piece_inspection(
    db: AsyncSession,
    part_id: int,
    inspected_qty: int,
    result: InspectionResult,
    session_id: Optional[int] = None,
    dimension_ok: bool = False,
    dimension_notes: Optional[str] = None,
    appearance_ok: bool = False,
    appearance_notes: Optional[str] = None,
    function_ok: bool = False,
    function_notes: Optional[str] = None,
    notes: Optional[str] = None,
    inspected_by: Optional[int] = None,
) -> FirstPieceInspection:
    """Create a first piece inspection record."""
    inspection_no = generate_inspection_no("FPI")

    inspection = FirstPieceInspection(
        inspection_no=inspection_no,
        part_id=part_id,
        session_id=session_id,
        inspected_qty=inspected_qty,
        inspected_by=inspected_by,
        dimension_ok=dimension_ok,
        dimension_notes=dimension_notes,
        appearance_ok=appearance_ok,
        appearance_notes=appearance_notes,
        function_ok=function_ok,
        function_notes=function_notes,
        result=result,
        notes=notes,
    )
    db.add(inspection)

    # Record audit event
    await _record_audit(
        db,
        action="first_piece_inspection",
        entity_type="FirstPieceInspection",
        entity_id=0,
        user_id=inspected_by,
        details=f"Part {part_id}: {result.value}",
    )

    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_first_piece_inspection(
    db: AsyncSession,
    inspection_id: int,
) -> Optional[FirstPieceInspection]:
    """Get a first piece inspection by ID."""
    result = await db.execute(
        select(FirstPieceInspection)
        .options(joinedload(FirstPieceInspection.part))
        .where(FirstPieceInspection.id == inspection_id)
    )
    return result.scalar_one_or_none()


async def get_first_piece_inspections(
    db: AsyncSession,
    part_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[FirstPieceInspection]:
    """Get first piece inspections."""
    query = select(FirstPieceInspection).options(joinedload(FirstPieceInspection.part))

    if part_id:
        query = query.where(FirstPieceInspection.part_id == part_id)

    query = query.order_by(FirstPieceInspection.inspected_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def create_oqc_inspection(
    db: AsyncSession,
    part_id: int,
    shipment_qty: int,
    sample_size: int,
    result: InspectionResult,
    order_no: Optional[str] = None,
    aql_level: Optional[str] = None,
    major_defects: int = 0,
    minor_defects: int = 0,
    critical_defects: int = 0,
    notes: Optional[str] = None,
    inspected_by: Optional[int] = None,
) -> OQCInspection:
    """Create an OQC inspection record."""
    inspection_no = generate_inspection_no("OQC")

    inspection = OQCInspection(
        inspection_no=inspection_no,
        part_id=part_id,
        shipment_qty=shipment_qty,
        order_no=order_no,
        sample_size=sample_size,
        inspected_by=inspected_by,
        aql_level=aql_level,
        major_defects=major_defects,
        minor_defects=minor_defects,
        critical_defects=critical_defects,
        result=result,
        notes=notes,
    )
    db.add(inspection)

    # Record audit event
    await _record_audit(
        db,
        action="oqc_inspection",
        entity_type="OQCInspection",
        entity_id=0,
        user_id=inspected_by,
        details=f"Part {part_id}: {result.value}, defects: M{major_defects}/m{minor_defects}/c{critical_defects}",
    )

    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_oqc_inspection(
    db: AsyncSession,
    inspection_id: int,
) -> Optional[OQCInspection]:
    """Get an OQC inspection by ID."""
    result = await db.execute(
        select(OQCInspection)
        .options(joinedload(OQCInspection.part))
        .where(OQCInspection.id == inspection_id)
    )
    return result.scalar_one_or_none()


async def get_oqc_inspections(
    db: AsyncSession,
    part_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[OQCInspection]:
    """Get OQC inspections."""
    query = select(OQCInspection).options(joinedload(OQCInspection.part))

    if part_id:
        query = query.where(OQCInspection.part_id == part_id)

    query = query.order_by(OQCInspection.inspected_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def create_exemption_request(
    db: AsyncSession,
    part_id: int,
    exemption_type: ExemptionType,
    issue_description: str,
    affected_qty: int,
    notes: Optional[str] = None,
    requested_by: Optional[int] = None,
) -> QAExemption:
    """Create a QA exemption request."""
    exemption_no = generate_inspection_no("EXM")

    exemption = QAExemption(
        exemption_no=exemption_no,
        part_id=part_id,
        exemption_type=exemption_type,
        issue_description=issue_description,
        affected_qty=affected_qty,
        notes=notes,
    )
    db.add(exemption)

    # Record audit event
    await _record_audit(
        db,
        action="exemption_request",
        entity_type="QAExemption",
        entity_id=0,
        user_id=requested_by,
        details=f"Part {part_id}: {exemption_type.value} - {issue_description[:50]}",
    )

    await db.commit()
    await db.refresh(exemption)
    return exemption


async def approve_exemption(
    db: AsyncSession,
    exemption: QAExemption,
    exemption_reason: str,
    approved_by: int,
) -> QAExemption:
    """Approve a QA exemption (requires role_level >= 2)."""
    if exemption.is_approved:
        raise ValueError("Exemption already approved")

    exemption.is_approved = True
    exemption.approved_by = approved_by
    exemption.approved_at = datetime.utcnow()
    exemption.exemption_reason = exemption_reason

    # Record audit event with detailed info
    await _record_audit(
        db,
        action="exemption_approved",
        entity_type="QAExemption",
        entity_id=exemption.id,
        user_id=approved_by,
        details=f"Exemption {exemption.exemption_no}: {exemption_reason}",
    )

    await db.commit()
    await db.refresh(exemption)
    return exemption


async def get_exemption(
    db: AsyncSession,
    exemption_id: int,
) -> Optional[QAExemption]:
    """Get a QA exemption by ID."""
    result = await db.execute(
        select(QAExemption)
        .options(joinedload(QAExemption.part))
        .where(QAExemption.id == exemption_id)
    )
    return result.scalar_one_or_none()


async def get_exemptions(
    db: AsyncSession,
    part_id: Optional[int] = None,
    is_approved: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[QAExemption]:
    """Get QA exemptions."""
    query = select(QAExemption).options(joinedload(QAExemption.part))

    if part_id:
        query = query.where(QAExemption.part_id == part_id)
    if is_approved is not None:
        query = query.where(QAExemption.is_approved == is_approved)

    query = query.order_by(QAExemption.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def create_patrol_inspection(
    db: AsyncSession,
    result: InspectionResult,
    session_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    dimension_check: bool = False,
    appearance_check: bool = False,
    process_parameter_check: bool = False,
    sample_size: int = 0,
    defect_count: int = 0,
    notes: Optional[str] = None,
    corrective_action: Optional[str] = None,
    inspected_by: Optional[int] = None,
) -> PatrolInspection:
    """Create a patrol inspection record."""
    inspection_no = generate_inspection_no("PAT")

    inspection = PatrolInspection(
        inspection_no=inspection_no,
        session_id=session_id,
        machine_id=machine_id,
        inspected_by=inspected_by,
        dimension_check=dimension_check,
        appearance_check=appearance_check,
        process_parameter_check=process_parameter_check,
        sample_size=sample_size,
        defect_count=defect_count,
        result=result,
        notes=notes,
        corrective_action=corrective_action,
    )
    db.add(inspection)

    # Record audit event
    await _record_audit(
        db,
        action="patrol_inspection",
        entity_type="PatrolInspection",
        entity_id=0,
        user_id=inspected_by,
        details=f"Session {session_id}: {result.value}, defects: {defect_count}",
    )

    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_patrol_inspections(
    db: AsyncSession,
    session_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[PatrolInspection]:
    """Get patrol inspections."""
    query = select(PatrolInspection)

    if session_id:
        query = query.where(PatrolInspection.session_id == session_id)
    if machine_id:
        query = query.where(PatrolInspection.machine_id == machine_id)

    query = query.order_by(PatrolInspection.inspected_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def _record_audit(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: int,
    user_id: Optional[int],
    details: str,
) -> None:
    """Record an audit event for quality operations."""
    from app.models.audit import AuditLog

    audit = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=details,
        ip_address=None,
    )
    db.add(audit)
