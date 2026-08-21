"""Quality inspection and release management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.part import Part
from app.models.quality import (
    ExemptionType,
    FirstPieceInspection,
    InspectionResult,
    OQCInspection,
    QAExemption,
    PatrolInspection,
)
from app.schemas.quality import (
    FirstPieceInspectionCreate,
    FirstPieceInspectionResponse,
    OQCInspectionCreate,
    OQCInspectionResponse,
    QAExemptionApprove,
    QAExemptionCreate,
    QAExemptionResponse,
    PatrolInspectionCreate,
    PatrolInspectionResponse,
)
from app.services import quality_service

router = APIRouter(prefix="/quality", tags=["Quality"])


def _fpi_to_response(inspection: FirstPieceInspection) -> FirstPieceInspectionResponse:
    """Convert FirstPieceInspection to response."""
    return FirstPieceInspectionResponse(
        id=inspection.id,
        inspection_no=inspection.inspection_no,
        part_id=inspection.part_id,
        session_id=inspection.session_id,
        inspected_qty=inspection.inspected_qty,
        inspected_by=inspection.inspected_by,
        dimension_ok=inspection.dimension_ok,
        dimension_notes=inspection.dimension_notes,
        appearance_ok=inspection.appearance_ok,
        appearance_notes=inspection.appearance_notes,
        function_ok=inspection.function_ok,
        function_notes=inspection.function_notes,
        result=inspection.result,
        notes=inspection.notes,
        inspected_at=inspection.inspected_at,
        created_at=inspection.created_at,
    )


def _oqc_to_response(inspection: OQCInspection) -> OQCInspectionResponse:
    """Convert OQCInspection to response."""
    return OQCInspectionResponse(
        id=inspection.id,
        inspection_no=inspection.inspection_no,
        part_id=inspection.part_id,
        shipment_qty=inspection.shipment_qty,
        order_no=inspection.order_no,
        sample_size=inspection.sample_size,
        inspected_by=inspection.inspected_by,
        aql_level=inspection.aql_level,
        major_defects=inspection.major_defects,
        minor_defects=inspection.minor_defects,
        critical_defects=inspection.critical_defects,
        result=inspection.result,
        notes=inspection.notes,
        inspected_at=inspection.inspected_at,
        created_at=inspection.created_at,
    )


def _exemption_to_response(exemption: QAExemption) -> QAExemptionResponse:
    """Convert QAExemption to response."""
    return QAExemptionResponse(
        id=exemption.id,
        exemption_no=exemption.exemption_no,
        part_id=exemption.part_id,
        exemption_type=exemption.exemption_type,
        issue_description=exemption.issue_description,
        affected_qty=exemption.affected_qty,
        approved_by=exemption.approved_by,
        approved_at=exemption.approved_at,
        exemption_reason=exemption.exemption_reason,
        is_approved=exemption.is_approved,
        is_active=exemption.is_active,
        notes=exemption.notes,
        created_at=exemption.created_at,
    )


def _patrol_to_response(inspection: PatrolInspection) -> PatrolInspectionResponse:
    """Convert PatrolInspection to response."""
    return PatrolInspectionResponse(
        id=inspection.id,
        inspection_no=inspection.inspection_no,
        machine_id=inspection.machine_id,
        session_id=inspection.session_id,
        inspected_by=inspection.inspected_by,
        dimension_check=inspection.dimension_check,
        appearance_check=inspection.appearance_check,
        process_parameter_check=inspection.process_parameter_check,
        sample_size=inspection.sample_size,
        defect_count=inspection.defect_count,
        result=inspection.result,
        notes=inspection.notes,
        corrective_action=inspection.corrective_action,
        action_taken_by=inspection.action_taken_by,
        inspected_at=inspection.inspected_at,
        created_at=inspection.created_at,
    )


# First Piece Inspection endpoints

@router.post("/first-piece", response_model=FirstPieceInspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_first_piece_inspection(
    data: FirstPieceInspectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FirstPieceInspectionResponse:
    """Create a first piece inspection record.

    Used by quality personnel or production supervisors to inspect the first piece
    before mass production starts. Requires LV2 (supervisor/technical).
    """
    require_role(current_user, min_level=2)

    # Verify part exists
    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    inspection = await quality_service.create_first_piece_inspection(
        db,
        part_id=data.part_id,
        inspected_qty=data.inspected_qty,
        result=data.result,
        session_id=data.session_id,
        dimension_ok=data.dimension_ok,
        dimension_notes=data.dimension_notes,
        appearance_ok=data.appearance_ok,
        appearance_notes=data.appearance_notes,
        function_ok=data.function_ok,
        function_notes=data.function_notes,
        notes=data.notes,
        inspected_by=current_user.id,
    )
    return _fpi_to_response(inspection)


@router.get("/first-piece", response_model=list[FirstPieceInspectionResponse])
async def list_first_piece_inspections(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[FirstPieceInspectionResponse]:
    """List first piece inspection records."""
    inspections = await quality_service.get_first_piece_inspections(
        db, part_id=part_id, skip=skip, limit=limit
    )
    return [_fpi_to_response(i) for i in inspections]


@router.get("/first-piece/{inspection_id}", response_model=FirstPieceInspectionResponse)
async def get_first_piece_inspection(
    inspection_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FirstPieceInspectionResponse:
    """Get a first piece inspection by ID."""
    inspection = await quality_service.get_first_piece_inspection(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="First piece inspection not found")
    return _fpi_to_response(inspection)


# OQC Inspection endpoints

@router.post("/oqc", response_model=OQCInspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_oqc_inspection(
    data: OQCInspectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> OQCInspectionResponse:
    """Create an OQC (Outgoing Quality Control) inspection record.

    Used by quality personnel to inspect products before shipment.
    Requires LV2 (quality supervisor/manager).
    """
    require_role(current_user, min_level=2)

    # Verify part exists
    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    inspection = await quality_service.create_oqc_inspection(
        db,
        part_id=data.part_id,
        shipment_qty=data.shipment_qty,
        sample_size=data.sample_size,
        result=data.result,
        order_no=data.order_no,
        aql_level=data.aql_level,
        major_defects=data.major_defects,
        minor_defects=data.minor_defects,
        critical_defects=data.critical_defects,
        notes=data.notes,
        inspected_by=current_user.id,
    )
    return _oqc_to_response(inspection)


@router.get("/oqc", response_model=list[OQCInspectionResponse])
async def list_oqc_inspections(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[OQCInspectionResponse]:
    """List OQC inspection records."""
    inspections = await quality_service.get_oqc_inspections(
        db, part_id=part_id, skip=skip, limit=limit
    )
    return [_oqc_to_response(i) for i in inspections]


@router.get("/oqc/{inspection_id}", response_model=OQCInspectionResponse)
async def get_oqc_inspection(
    inspection_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OQCInspectionResponse:
    """Get an OQC inspection by ID."""
    inspection = await quality_service.get_oqc_inspection(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="OQC inspection not found")
    return _oqc_to_response(inspection)


# QA Exemption endpoints

@router.post("/exemption", response_model=QAExemptionResponse, status_code=status.HTTP_201_CREATED)
async def create_exemption_request(
    data: QAExemptionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> QAExemptionResponse:
    """Create a QA exemption request.

    Used by authorized personnel to request emergency release when quality
    does not meet standards.
    """
    require_role(current_user, min_level=2)

    # Verify part exists
    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    exemption = await quality_service.create_exemption_request(
        db,
        part_id=data.part_id,
        exemption_type=data.exemption_type,
        issue_description=data.issue_description,
        affected_qty=data.affected_qty,
        notes=data.notes,
        requested_by=current_user.id,
    )
    return _exemption_to_response(exemption)


@router.post("/exemption/{exemption_id}/approve", response_model=QAExemptionResponse)
async def approve_exemption(
    exemption_id: int,
    data: QAExemptionApprove,
    db: DbSession,
    current_user: CurrentUser,
) -> QAExemptionResponse:
    """Approve a QA exemption request.

    Requires role_level >= 2.
    """
    require_role(current_user, min_level=2)

    exemption = await quality_service.get_exemption(db, exemption_id)
    if not exemption:
        raise HTTPException(status_code=404, detail="QA exemption not found")

    try:
        exemption = await quality_service.approve_exemption(
            db, exemption, data.exemption_reason, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _exemption_to_response(exemption)


@router.get("/exemption", response_model=list[QAExemptionResponse])
async def list_exemptions(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    is_approved: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[QAExemptionResponse]:
    """List QA exemption requests."""
    exemptions = await quality_service.get_exemptions(
        db, part_id=part_id, is_approved=is_approved, skip=skip, limit=limit
    )
    return [_exemption_to_response(e) for e in exemptions]


@router.get("/exemption/{exemption_id}", response_model=QAExemptionResponse)
async def get_exemption(
    exemption_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QAExemptionResponse:
    """Get a QA exemption by ID."""
    exemption = await quality_service.get_exemption(db, exemption_id)
    if not exemption:
        raise HTTPException(status_code=404, detail="QA exemption not found")
    return _exemption_to_response(exemption)


# Patrol Inspection endpoints

@router.post("/patrol", response_model=PatrolInspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_patrol_inspection(
    data: PatrolInspectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PatrolInspectionResponse:
    """Create a patrol inspection record.

    Used by quality personnel to perform regular inspections during production.
    Requires LV2 (quality supervisor/manager).
    """
    require_role(current_user, min_level=2)

    inspection = await quality_service.create_patrol_inspection(
        db,
        result=data.result,
        session_id=data.session_id,
        machine_id=data.machine_id,
        dimension_check=data.dimension_check,
        appearance_check=data.appearance_check,
        process_parameter_check=data.process_parameter_check,
        sample_size=data.sample_size,
        defect_count=data.defect_count,
        notes=data.notes,
        corrective_action=data.corrective_action,
        inspected_by=current_user.id,
    )
    return _patrol_to_response(inspection)


@router.get("/patrol", response_model=list[PatrolInspectionResponse])
async def list_patrol_inspections(
    db: DbSession,
    current_user: CurrentUser,
    session_id: Optional[int] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PatrolInspectionResponse]:
    """List patrol inspection records."""
    inspections = await quality_service.get_patrol_inspections(
        db, session_id=session_id, machine_id=machine_id, skip=skip, limit=limit
    )
    return [_patrol_to_response(i) for i in inspections]
