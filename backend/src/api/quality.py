"""Quality control API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.quality import FirstPieceStatus, OQCResult
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


# First Piece Inspection

@router.post("/first-piece", response_model=FirstPieceInspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_first_piece_inspection(
    data: FirstPieceInspectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FirstPieceInspectionResponse:
    """Create a first piece inspection (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    try:
        inspection = await quality_service.create_first_piece_inspection(
            db, data.model_dump(), current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _fpi_to_response(inspection)


@router.get("/first-piece", response_model=list[FirstPieceInspectionResponse])
async def list_first_piece_inspections(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    result: Optional[FirstPieceStatus] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[FirstPieceInspectionResponse]:
    """List first piece inspections."""
    inspections = await quality_service.get_first_piece_inspections(
        db, part_id=part_id, result=result, skip=skip, limit=limit
    )
    return [_fpi_to_response(i) for i in inspections]


@router.get("/first-piece/{inspection_id}", response_model=FirstPieceInspectionResponse)
async def get_first_piece_inspection(
    inspection_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FirstPieceInspectionResponse:
    """Get first piece inspection by ID."""
    inspection = await quality_service.get_first_piece_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return _fpi_to_response(inspection)


@router.get("/first-piece/lookup/{inspection_no}", response_model=FirstPieceInspectionResponse)
async def lookup_first_piece_inspection(
    inspection_no: str,
    db: DbSession,
    current_user: CurrentUser,
) -> FirstPieceInspectionResponse:
    """Lookup first piece inspection by number."""
    inspection = await quality_service.get_first_piece_by_no(db, inspection_no)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return _fpi_to_response(inspection)


# OQC Inspection

@router.post("/oqc", response_model=OQCInspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_oqc_inspection(
    data: OQCInspectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> OQCInspectionResponse:
    """Create an OQC (Outgoing Quality Control) inspection (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    try:
        inspection = await quality_service.create_oqc_inspection(
            db, data.model_dump(), current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _oqc_to_response(inspection)


@router.get("/oqc", response_model=list[OQCInspectionResponse])
async def list_oqc_inspections(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    result: Optional[OQCResult] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[OQCInspectionResponse]:
    """List OQC inspections."""
    inspections = await quality_service.get_oqc_inspections(
        db, part_id=part_id, result=result, skip=skip, limit=limit
    )
    return [_oqc_to_response(i) for i in inspections]


@router.get("/oqc/{inspection_id}", response_model=OQCInspectionResponse)
async def get_oqc_inspection(
    inspection_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OQCInspectionResponse:
    """Get OQC inspection by ID."""
    inspection = await quality_service.get_oqc_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return _oqc_to_response(inspection)


# QA Exemption

@router.post("/exemption", response_model=QAExemptionResponse, status_code=status.HTTP_201_CREATED)
async def create_exemption_request(
    data: QAExemptionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> QAExemptionResponse:
    """Create a QA exemption request (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    try:
        exemption = await quality_service.create_exemption_request(
            db, data.model_dump(), current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _exemption_to_response(exemption)


@router.get("/exemption", response_model=list[QAExemptionResponse])
async def list_exemptions(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[QAExemptionResponse]:
    """List QA exemptions."""
    exemptions = await quality_service.get_exemptions(
        db, part_id=part_id, status=status, skip=skip, limit=limit
    )
    return [_exemption_to_response(e) for e in exemptions]


@router.get("/exemption/{exemption_id}", response_model=QAExemptionResponse)
async def get_exemption(
    exemption_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QAExemptionResponse:
    """Get QA exemption by ID."""
    exemption = await quality_service.get_exemption_by_id(db, exemption_id)
    if not exemption:
        raise HTTPException(status_code=404, detail="Exemption not found")
    return _exemption_to_response(exemption)


@router.post("/exemption/{exemption_id}/approve")
async def approve_exemption(
    exemption_id: int,
    data: QAExemptionApprove,
    db: DbSession,
    current_user: CurrentUser,
) -> QAExemptionResponse:
    """Approve or reject a QA exemption (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    exemption = await quality_service.get_exemption_by_id(db, exemption_id)
    if not exemption:
        raise HTTPException(status_code=404, detail="Exemption not found")

    try:
        exemption = await quality_service.approve_exemption(
            db, exemption, data.approved, current_user,
            notes=data.notes, expires_at=data.expires_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _exemption_to_response(exemption)


# Patrol Inspection

@router.post("/patrol", response_model=PatrolInspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_patrol_inspection(
    data: PatrolInspectionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> PatrolInspectionResponse:
    """Create a patrol inspection (requires role_level >= 2)."""
    require_role(current_user, min_level=2)

    inspection = await quality_service.create_patrol_inspection(
        db, data.model_dump(), current_user
    )
    return _patrol_to_response(inspection)


@router.get("/patrol", response_model=list[PatrolInspectionResponse])
async def list_patrol_inspections(
    db: DbSession,
    current_user: CurrentUser,
    machine_id: Optional[int] = Query(default=None),
    session_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PatrolInspectionResponse]:
    """List patrol inspections."""
    inspections = await quality_service.get_patrol_inspections(
        db, machine_id=machine_id, session_id=session_id, skip=skip, limit=limit
    )
    return [_patrol_to_response(i) for i in inspections]


# Helper functions

def _fpi_to_response(inspection) -> FirstPieceInspectionResponse:
    """Convert FirstPieceInspection to response."""
    return FirstPieceInspectionResponse(
        id=inspection.id,
        inspection_no=inspection.inspection_no,
        part_id=inspection.part_id,
        part_no=inspection.part.part_no if inspection.part else None,
        part_name=inspection.part.part_name if inspection.part else None,
        process_flow_id=inspection.process_flow_id,
        dimension_check=inspection.dimension_check,
        surface_check=inspection.surface_check,
        material_check=inspection.material_check,
        result=inspection.result,
        reject_reasons=inspection.reject_reasons,
        rework_required=inspection.rework_required,
        inspector_id=inspection.inspector_id,
        inspected_at=inspection.inspected_at,
        notes=inspection.notes,
        attachment_paths=inspection.attachment_paths,
        batch_size=inspection.batch_size,
        sample_size=inspection.sample_size,
        created_at=inspection.created_at,
    )


def _oqc_to_response(inspection) -> OQCInspectionResponse:
    """Convert OQCInspection to response."""
    return OQCInspectionResponse(
        id=inspection.id,
        inspection_no=inspection.inspection_no,
        part_id=inspection.part_id,
        part_no=inspection.part.part_no if inspection.part else None,
        part_name=inspection.part.part_name if inspection.part else None,
        shipment_id=inspection.shipment_id,
        inspected_qty=inspection.inspected_qty,
        passed_qty=inspection.passed_qty,
        failed_qty=inspection.failed_qty,
        defect_types=inspection.defect_types,
        defect_positions=inspection.defect_positions,
        result=inspection.result,
        inspector_id=inspection.inspector_id,
        inspected_at=inspection.inspected_at,
        sample_size=inspection.sample_size,
        sampling_plan=inspection.sampling_plan,
        notes=inspection.notes,
        attachment_paths=inspection.attachment_paths,
        created_at=inspection.created_at,
    )


def _exemption_to_response(exemption) -> QAExemptionResponse:
    """Convert QAExemption to response."""
    return QAExemptionResponse(
        id=exemption.id,
        exemption_no=exemption.exemption_no,
        part_id=exemption.part_id,
        part_no=exemption.part.part_no if exemption.part else None,
        part_name=exemption.part.part_name if exemption.part else None,
        related_inspection_id=exemption.related_inspection_id,
        related_inspection_type=exemption.related_inspection_type,
        defect_description=exemption.defect_description,
        quantity_affected=exemption.quantity_affected,
        reason=exemption.reason,
        impact_assessment=exemption.impact_assessment,
        customer_notification_required=exemption.customer_notification_required,
        status=exemption.status,
        requested_by=exemption.requested_by,
        requested_at=exemption.requested_at,
        request_notes=exemption.request_notes,
        approved_by=exemption.approved_by,
        approved_at=exemption.approved_at,
        approval_notes=exemption.approval_notes,
        expires_at=exemption.expires_at,
        batch_no=exemption.batch_no,
        created_at=exemption.created_at,
    )


def _patrol_to_response(inspection) -> PatrolInspectionResponse:
    """Convert PatrolInspection to response."""
    return PatrolInspectionResponse(
        id=inspection.id,
        inspection_no=inspection.inspection_no,
        machine_id=inspection.machine_id,
        production_session_id=inspection.production_session_id,
        check_points=inspection.check_points,
        check_results=inspection.check_results,
        result=inspection.result,
        issues_found=inspection.issues_found,
        severity=inspection.severity,
        corrective_action=inspection.corrective_action,
        action_required=inspection.action_required,
        inspector_id=inspection.inspector_id,
        inspected_at=inspection.inspected_at,
        notes=inspection.notes,
        created_at=inspection.created_at,
    )
