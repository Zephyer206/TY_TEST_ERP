"""Business logic for quality control management."""

import secrets
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.part import Part
from app.models.quality import (
    FirstPieceInspection,
    FirstPieceStatus,
    OQCInspection,
    OQCResult,
    QAExemption,
    PatrolInspection,
    InspectionResult,
)
from app.models.user import User


def generate_inspection_no(prefix: str, db: AsyncSession) -> str:
    """Generate a unique inspection number."""
    now = datetime.utcnow()
    suffix = secrets.token_hex(3).upper()[:6]
    return f"{prefix}-{now.strftime('%Y%m%d')}-{suffix}"


# First Piece Inspection

async def create_first_piece_inspection(
    db: AsyncSession,
    data: dict,
    inspector: User,
) -> FirstPieceInspection:
    """Create a new first piece inspection."""
    # Validate part exists
    part_result = await db.execute(select(Part).where(Part.id == data["part_id"]))
    part = part_result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    inspection_no = generate_inspection_no("FPI", db)

    inspection = FirstPieceInspection(
        inspection_no=inspection_no,
        part_id=data["part_id"],
        process_flow_id=data.get("process_flow_id"),
        dimension_check=data.get("dimension_check"),
        surface_check=data.get("surface_check"),
        material_check=data.get("material_check"),
        result=data["result"],
        reject_reasons=data.get("reject_reasons"),
        rework_required=data.get("rework_required", False),
        notes=data.get("notes"),
        attachment_paths=data.get("attachment_paths"),
        batch_size=data.get("batch_size"),
        sample_size=data.get("sample_size"),
        inspector_id=inspector.id if hasattr(inspector, 'id') else None,
        inspected_at=datetime.utcnow(),
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_first_piece_by_id(
    db: AsyncSession,
    inspection_id: int,
) -> Optional[FirstPieceInspection]:
    """Get first piece inspection by ID."""
    result = await db.execute(
        select(FirstPieceInspection)
        .options(selectinload(FirstPieceInspection.part))
        .where(
            FirstPieceInspection.id == inspection_id,
            FirstPieceInspection.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_first_piece_by_no(
    db: AsyncSession,
    inspection_no: str,
) -> Optional[FirstPieceInspection]:
    """Get first piece inspection by number."""
    result = await db.execute(
        select(FirstPieceInspection)
        .options(selectinload(FirstPieceInspection.part))
        .where(
            FirstPieceInspection.inspection_no == inspection_no,
            FirstPieceInspection.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_first_piece_inspections(
    db: AsyncSession,
    part_id: Optional[int] = None,
    result: Optional[FirstPieceStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[FirstPieceInspection]:
    """Get first piece inspections with filters."""
    query = (
        select(FirstPieceInspection)
        .options(selectinload(FirstPieceInspection.part))
        .where(FirstPieceInspection.is_deleted == False)
    )

    if part_id:
        query = query.where(FirstPieceInspection.part_id == part_id)
    if result:
        query = query.where(FirstPieceInspection.result == result)

    query = query.order_by(FirstPieceInspection.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# OQC Inspection

async def create_oqc_inspection(
    db: AsyncSession,
    data: dict,
    inspector: User,
) -> OQCInspection:
    """Create a new OQC inspection."""
    # Validate part exists
    part_result = await db.execute(select(Part).where(Part.id == data["part_id"]))
    part = part_result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    # Validate quantities
    if data["passed_qty"] + data["failed_qty"] != data["inspected_qty"]:
        raise ValueError("passed_qty + failed_qty must equal inspected_qty")

    inspection_no = generate_inspection_no("OQC", db)

    inspection = OQCInspection(
        inspection_no=inspection_no,
        part_id=data["part_id"],
        shipment_id=data.get("shipment_id"),
        inspected_qty=data["inspected_qty"],
        passed_qty=data["passed_qty"],
        failed_qty=data["failed_qty"],
        defect_types=data.get("defect_types"),
        defect_positions=data.get("defect_positions"),
        result=data["result"],
        sample_size=data.get("sample_size"),
        sampling_plan=data.get("sampling_plan"),
        notes=data.get("notes"),
        attachment_paths=data.get("attachment_paths"),
        inspector_id=inspector.id if hasattr(inspector, 'id') else None,
        inspected_at=datetime.utcnow(),
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_oqc_by_id(
    db: AsyncSession,
    inspection_id: int,
) -> Optional[OQCInspection]:
    """Get OQC inspection by ID."""
    result = await db.execute(
        select(OQCInspection)
        .options(selectinload(OQCInspection.part))
        .where(
            OQCInspection.id == inspection_id,
            OQCInspection.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_oqc_inspections(
    db: AsyncSession,
    part_id: Optional[int] = None,
    result: Optional[OQCResult] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[OQCInspection]:
    """Get OQC inspections with filters."""
    query = (
        select(OQCInspection)
        .options(selectinload(OQCInspection.part))
        .where(OQCInspection.is_deleted == False)
    )

    if part_id:
        query = query.where(OQCInspection.part_id == part_id)
    if result:
        query = query.where(OQCInspection.result == result)

    query = query.order_by(OQCInspection.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# QA Exemption

async def create_exemption_request(
    db: AsyncSession,
    data: dict,
    requester: User,
) -> QAExemption:
    """Create a new QA exemption request."""
    # Validate part exists
    part_result = await db.execute(select(Part).where(Part.id == data["part_id"]))
    part = part_result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    exemption_no = generate_inspection_no("EXM", db)

    exemption = QAExemption(
        exemption_no=exemption_no,
        part_id=data["part_id"],
        related_inspection_id=data.get("related_inspection_id"),
        related_inspection_type=data.get("related_inspection_type"),
        defect_description=data["defect_description"],
        quantity_affected=data["quantity_affected"],
        reason=data["reason"],
        impact_assessment=data.get("impact_assessment"),
        customer_notification_required=data.get("customer_notification_required", False),
        status="pending",
        requested_by=requester.id if hasattr(requester, 'id') else None,
        requested_at=datetime.utcnow(),
        request_notes=data.get("notes"),
        batch_no=data.get("batch_no"),
    )
    db.add(exemption)
    await db.commit()
    await db.refresh(exemption)
    return exemption


async def get_exemption_by_id(
    db: AsyncSession,
    exemption_id: int,
) -> Optional[QAExemption]:
    """Get QA exemption by ID."""
    result = await db.execute(
        select(QAExemption)
        .options(selectinload(QAExemption.part))
        .where(
            QAExemption.id == exemption_id,
            QAExemption.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_exemptions(
    db: AsyncSession,
    part_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[QAExemption]:
    """Get QA exemptions with filters."""
    query = (
        select(QAExemption)
        .options(selectinload(QAExemption.part))
        .where(QAExemption.is_deleted == False)
    )

    if part_id:
        query = query.where(QAExemption.part_id == part_id)
    if status:
        query = query.where(QAExemption.status == status)

    query = query.order_by(QAExemption.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def approve_exemption(
    db: AsyncSession,
    exemption: QAExemption,
    approved: bool,
    approver: User,
    notes: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> QAExemption:
    """Approve or reject a QA exemption."""
    if exemption.status != "pending":
        raise ValueError("Exemption is not in pending status")

    exemption.approved_by = approver.id if hasattr(approver, 'id') else None
    exemption.approved_at = datetime.utcnow()
    exemption.approval_notes = notes
    exemption.status = "approved" if approved else "rejected"
    exemption.expires_at = expires_at

    await db.commit()
    await db.refresh(exemption)
    return exemption


# Patrol Inspection

async def create_patrol_inspection(
    db: AsyncSession,
    data: dict,
    inspector: User,
) -> PatrolInspection:
    """Create a new patrol inspection."""
    inspection_no = generate_inspection_no("PAT", db)

    inspection = PatrolInspection(
        inspection_no=inspection_no,
        machine_id=data.get("machine_id"),
        production_session_id=data.get("production_session_id"),
        check_points=data.get("check_points"),
        check_results=data.get("check_results"),
        result=data["result"],
        issues_found=data.get("issues_found"),
        severity=data.get("severity"),
        corrective_action=data.get("corrective_action"),
        action_required=data.get("action_required", False),
        notes=data.get("notes"),
        inspector_id=inspector.id if hasattr(inspector, 'id') else None,
        inspected_at=datetime.utcnow(),
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


async def get_patrol_inspections(
    db: AsyncSession,
    machine_id: Optional[int] = None,
    session_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[PatrolInspection]:
    """Get patrol inspections with filters."""
    query = select(PatrolInspection).where(PatrolInspection.is_deleted == False)

    if machine_id:
        query = query.where(PatrolInspection.machine_id == machine_id)
    if session_id:
        query = query.where(PatrolInspection.production_session_id == session_id)

    query = query.order_by(PatrolInspection.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
