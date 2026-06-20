"""Production planning and reporting API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.machine import Machine
from app.models.production import ProductionPlan, PlanMachineAssignment, PlanStatus, ProcessFlowStatus
from app.schemas.production import (
    MachineAssignmentResponse,
    MaterialMatchResult,
    PlanStatus,
    ProcessFlowCardResponse,
    ProductionPlanCreate,
    ProductionPlanDetailResponse,
    ProductionPlanResponse,
    ProductionPlanUpdate,
    ProductionReportCreate,
    ProductionReportResponse,
    ProductionSessionDetailResponse,
    ProductionSessionResponse,
    SessionStartWithMaterialRequest,
    SessionStatus,
)
from app.services import production_service, process_flow_service, session_service

router = APIRouter(prefix="/production", tags=["Production"])


def _plan_to_response(plan: ProductionPlan) -> ProductionPlanResponse:
    """Convert ProductionPlan to response."""
    return ProductionPlanResponse(
        id=plan.id,
        plan_no=plan.plan_no,
        part_id=plan.part_id,
        total_qty=plan.total_qty,
        planned_start_date=plan.planned_start_date,
        planned_end_date=plan.planned_end_date,
        priority=plan.priority,
        notes=plan.notes,
        completed_qty=plan.completed_qty,
        status=plan.status,
        created_by=plan.created_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _assignment_to_response(assignment: PlanMachineAssignment) -> MachineAssignmentResponse:
    """Convert PlanMachineAssignment to response."""
    return MachineAssignmentResponse(
        id=assignment.id,
        plan_id=assignment.plan_id,
        machine_id=assignment.machine_id,
        machine_no=assignment.machine.machine_no if assignment.machine else None,
        machine_name=assignment.machine.name if assignment.machine else None,
        assigned_qty=assignment.assigned_qty,
        completed_qty=assignment.completed_qty,
        is_active=assignment.is_active,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
    )


@router.post("/plans", response_model=ProductionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_production_plan(
    data: ProductionPlanCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Create a new production plan."""
    require_role(current_user, min_level=3)

    # Verify part exists
    from app.models.part import Part

    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    plan = await production_service.create_plan(
        db,
        part_id=data.part_id,
        total_qty=data.total_qty,
        planned_start_date=data.planned_start_date,
        planned_end_date=data.planned_end_date,
        priority=data.priority,
        notes=data.notes,
        created_by=current_user.id,
    )
    return _plan_to_response(plan)


@router.get("/plans", response_model=list[ProductionPlanResponse])
async def list_production_plans(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[PlanStatus] = Query(default=None, alias="status"),
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProductionPlanResponse]:
    """List production plans with optional filters."""
    plans = await production_service.get_plans(
        db,
        status=status_filter,
        part_id=part_id,
        skip=skip,
        limit=limit,
    )
    return [_plan_to_response(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=ProductionPlanDetailResponse)
async def get_production_plan(
    plan_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanDetailResponse:
    """Get production plan details with assignments."""
    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    response = _plan_to_response(plan)
    assignments = [_assignment_to_response(a) for a in plan.assignments]

    return ProductionPlanDetailResponse(
        id=response.id,
        plan_no=response.plan_no,
        part_id=response.part_id,
        total_qty=response.total_qty,
        planned_start_date=response.planned_start_date,
        planned_end_date=response.planned_end_date,
        priority=response.priority,
        notes=response.notes,
        completed_qty=response.completed_qty,
        status=response.status,
        created_by=response.created_by,
        created_at=response.created_at,
        updated_at=response.updated_at,
        assignments=assignments,
    )


@router.patch("/plans/{plan_id}", response_model=ProductionPlanResponse)
async def update_production_plan(
    plan_id: int,
    data: ProductionPlanUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Update a production plan."""
    require_role(current_user, min_level=3)

    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    plan = await production_service.update_plan(
        db,
        plan,
        total_qty=data.total_qty,
        planned_start_date=data.planned_start_date,
        planned_end_date=data.planned_end_date,
        priority=data.priority,
        notes=data.notes,
        status=data.status,
    )
    return _plan_to_response(plan)


@router.post("/plans/{plan_id}/assign-machine", response_model=MachineAssignmentResponse)
async def assign_machine_to_plan(
    plan_id: int,
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
    assigned_qty: int = Query(..., ge=1),
) -> MachineAssignmentResponse:
    """Assign a machine to a production plan."""
    require_role(current_user, min_level=3)

    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    # Verify machine exists
    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    assignment = await production_service.assign_machine(
        db, plan, machine_id, assigned_qty, current_user
    )
    return _assignment_to_response(assignment)


@router.post("/sessions/verify-material", response_model=MaterialMatchResult)
async def verify_material_match(
    machine_id: int,
    part_id: int,
    material_batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialMatchResult:
    """Verify if material matches the tooling on the machine for the part."""
    result = await session_service.verify_material_tooling_match(
        db, machine_id, part_id, material_batch_id
    )
    return MaterialMatchResult(**result)


@router.post("/sessions/start", response_model=ProductionSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_production_session(
    data: SessionStartWithMaterialRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSessionResponse:
    """Start a new production session with material verification."""
    require_role(current_user, min_level=1)

    try:
        session = await session_service.start_session(
            db,
            machine_id=data.machine_id,
            part_id=data.part_id,
            material_batch_id=data.material_batch_id,
            plan_id=data.plan_id,
            operator_id=current_user.id,
            force_start=data.force_start,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionSessionResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        part_id=session.part_id,
        material_batch_id=session.material_batch_id,
        status=session.status,
        started_at=session.started_at,
        closed_at=session.closed_at,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        process_flow_id=session.process_flow_id,
        operator_id=session.operator_id,
        created_at=session.created_at,
    )


@router.get("/sessions/active", response_model=list[ProductionSessionResponse])
async def list_active_sessions(
    db: DbSession,
    current_user: CurrentUser,
    machine_id: Optional[int] = Query(default=None),
    part_id: Optional[int] = Query(default=None),
) -> list[ProductionSessionResponse]:
    """List active production sessions."""
    sessions = await session_service.get_active_sessions(
        db, machine_id=machine_id, part_id=part_id
    )

    return [
        ProductionSessionResponse(
            id=s.id,
            session_no=s.session_no,
            plan_id=s.plan_id,
            machine_id=s.machine_id,
            tooling_id=s.tooling_id,
            part_id=s.part_id,
            material_batch_id=s.material_batch_id,
            status=s.status,
            started_at=s.started_at,
            closed_at=s.closed_at,
            total_strokes=s.total_strokes,
            total_output=s.total_output,
            good_qty=s.good_qty,
            reject_qty=s.reject_qty,
            process_flow_id=s.process_flow_id,
            operator_id=s.operator_id,
            created_at=s.created_at,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ProductionSessionDetailResponse)
async def get_session(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSessionDetailResponse:
    """Get production session details with reports."""
    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    reports = [
        ProductionReportResponse(
            id=r.id,
            session_id=r.session_id,
            strokes=r.strokes,
            cavity_count=r.cavity_count,
            output=r.output,
            good_qty=r.good_qty,
            reject_qty=r.reject_qty,
            material_used=r.material_used,
            report_time=r.report_time,
            operator_id=r.operator_id,
            notes=r.notes,
            created_at=r.created_at,
        )
        for r in session.reports
    ]

    return ProductionSessionDetailResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        part_id=session.part_id,
        material_batch_id=session.material_batch_id,
        status=session.status,
        started_at=session.started_at,
        closed_at=session.closed_at,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        process_flow_id=session.process_flow_id,
        operator_id=session.operator_id,
        created_at=session.created_at,
        reports=reports,
    )


@router.post("/reports", response_model=ProductionReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_production_report(
    session_id: int,
    data: ProductionReportCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionReportResponse:
    """Submit a production report within a session."""
    require_role(current_user, min_level=1)

    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        report = await session_service.submit_report(
            db,
            session,
            strokes=data.strokes,
            cavity_count=data.cavity_count,
            good_qty=data.good_qty,
            reject_qty=data.reject_qty,
            material_used=data.material_used,
            notes=data.notes,
            operator_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionReportResponse(
        id=report.id,
        session_id=report.session_id,
        strokes=report.strokes,
        cavity_count=report.cavity_count,
        output=report.output,
        good_qty=report.good_qty,
        reject_qty=report.reject_qty,
        material_used=report.material_used,
        report_time=report.report_time,
        operator_id=report.operator_id,
        notes=report.notes,
        created_at=report.created_at,
    )


@router.post("/sessions/{session_id}/close", response_model=ProductionSessionResponse)
async def close_session(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSessionResponse:
    """Close a production session and generate process flow card."""
    require_role(current_user, min_level=1)

    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        session = await session_service.close_session(db, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionSessionResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        part_id=session.part_id,
        material_batch_id=session.material_batch_id,
        status=session.status,
        started_at=session.started_at,
        closed_at=session.closed_at,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        process_flow_id=session.process_flow_id,
        operator_id=session.operator_id,
        created_at=session.created_at,
    )


@router.get("/process-flow-cards", response_model=list[ProcessFlowCardResponse])
async def list_process_flow_cards(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    status_filter: Optional[ProcessFlowStatus] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProcessFlowCardResponse]:
    """List process flow cards."""
    from app.models.production import ProcessFlowStatus

    cards = await process_flow_service.get_process_flow_cards(
        db,
        part_id=part_id,
        machine_id=machine_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )

    return [
        ProcessFlowCardResponse(
            id=c.id,
            card_no=c.card_no,
            session_id=c.session_id,
            part_id=c.part_id,
            machine_id=c.machine_id,
            tooling_id=c.tooling_id,
            material_batch_no=c.material_batch_no,
            planned_qty=c.planned_qty,
            actual_output=c.actual_output,
            good_qty=c.good_qty,
            reject_qty=c.reject_qty,
            status=c.status,
            start_time=c.start_time,
            end_time=c.end_time,
            operator_id=c.operator_id,
            qr_code=c.qr_code,
            qr_image_base64=None,
            created_at=c.created_at,
        )
        for c in cards
    ]


# ── US4: Process Flow Card QR ────────────────────────────────────────────────

class PFCScanResponse(BaseModel):
    """Schema for process flow card scan response."""

    card_id: int
    card_no: str
    part_id: int
    part_name: Optional[str] = None
    machine_id: int
    machine_no: Optional[str] = None
    tooling_id: Optional[int] = None
    tooling_no: Optional[str] = None
    material_batch_no: Optional[str] = None
    planned_qty: int
    actual_output: int
    good_qty: int
    reject_qty: int
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    operator_id: Optional[int] = None
    qr_content: str
    qr_image_base64: str
    scan_history: list

    class Config:
        from_attributes = True


class PFCReverseTraceResponse(BaseModel):
    """Schema for reverse trace response."""

    card_id: int
    card_no: str
    status: str
    good_qty: int
    operator_id: Optional[int] = None
    material_batch_no: Optional[str] = None
    material_name: Optional[str] = None
    supplier_name: Optional[str] = None
    session_id: Optional[int] = None
    scan_history: list

    class Config:
        from_attributes = True


@router.get("/process-flow-cards/scan/{card_id}", response_model=PFCScanResponse)
async def scan_process_flow_card(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCScanResponse:
    """Scan process flow card: get full info, QR image, and scan history.

    Records the scan event in qr_scan_logs.
    """
    try:
        result = await process_flow_service.scan_process_flow_card(
            db, card_id, operator_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    card = result["card"]

    scan_history = []
    for log in result["scan_history"]:
        scan_history.append({
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        })

    return PFCScanResponse(
        card_id=card.id,
        card_no=card.card_no,
        part_id=card.part_id,
        part_name=card.part.part_name if card.part else None,
        machine_id=card.machine_id,
        machine_no=card.machine.machine_no if card.machine else None,
        tooling_id=card.tooling_id,
        tooling_no=card.tooling.name if card.tooling else None,
        material_batch_no=card.material_batch_no,
        planned_qty=card.planned_qty,
        actual_output=card.actual_output,
        good_qty=card.good_qty,
        reject_qty=card.reject_qty,
        status=card.status.value if card.status else None,
        start_time=card.start_time.isoformat() if card.start_time else None,
        end_time=card.end_time.isoformat() if card.end_time else None,
        operator_id=card.operator_id,
        qr_content=result["qr_content"],
        qr_image_base64=result["qr_image_base64"],
        scan_history=scan_history,
    )


@router.get("/process-flow-cards/{card_id}/reverse-trace", response_model=PFCReverseTraceResponse)
async def reverse_trace_card(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCReverseTraceResponse:
    """Reverse trace: from card -> session -> material batch -> supplier.

    Returns the full provenance chain of a process flow card.
    """
    try:
        result = await process_flow_service.reverse_trace_card(db, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    card = result["card"]
    material_batch = result.get("material_batch")

    scan_history = []
    for log in result["scan_history"]:
        scan_history.append({
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        })

    return PFCReverseTraceResponse(
        card_id=card.id,
        card_no=card.card_no,
        status=card.status.value if card.status else None,
        good_qty=card.good_qty,
        operator_id=card.operator_id,
        material_batch_no=card.material_batch_no,
        material_name=material_batch.material_name if material_batch else None,
        supplier_name=material_batch.supplier_name if material_batch else None,
        session_id=card.session_id,
        scan_history=scan_history,
    )


class PFCInboundRequest(BaseModel):
    """Schema for process flow card inbound confirmation."""

    notes: Optional[str] = None


@router.put("/process-flow-cards/{card_id}/inbound", response_model=PFCReverseTraceResponse)
async def confirm_pfc_inbound(
    card_id: int,
    data: PFCInboundRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCReverseTraceResponse:
    """Confirm OQC passed and mark process flow card as inbound.

    Records the inbound operation in qr_scan_logs with operation='inbound'.
    """
    try:
        card = await process_flow_service.confirm_inbound(
            db, card_id,
            operator_id=current_user.id,
            notes=data.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get updated scan history
    from app.models.warehouse import QRScanLog
    history_result = await db.execute(
        select(QRScanLog)
        .where(QRScanLog.scan_type == "PFC", QRScanLog.entity_id == card.id)
        .order_by(QRScanLog.scanned_at.desc())
        .limit(20)
    )
    scan_history_obj = history_result.scalars().all()
    scan_history = [
        {
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        }
        for log in scan_history_obj
    ]

    return PFCReverseTraceResponse(
        card_id=card.id,
        card_no=card.card_no,
        status=card.status.value if card.status else None,
        good_qty=card.good_qty,
        operator_id=card.operator_id,
        material_batch_no=card.material_batch_no,
        material_name=None,
        supplier_name=None,
        session_id=card.session_id,
        scan_history=scan_history,
    )


# ── T027: PFC Reprint QR ───────────────────────────────────────────────────

class PFCReprintResponse(BaseModel):
    """Schema for process flow card reprint response."""

    card_id: int
    card_no: str
    qr_content: str
    qr_image_base64: str

    class Config:
        from_attributes = True


@router.post("/process-flow-cards/{card_id}/reprint-qr", response_model=PFCReprintResponse)
async def reprint_pfc_qr(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCReprintResponse:
    """Reprint QR code for a process flow card.

    Returns the card info with qr_content and qr_image_base64.
    Records the reprint operation in qr_scan_logs.
    """
    try:
        card = await process_flow_service.get_process_flow_card(db, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not card:
        raise HTTPException(status_code=404, detail="Process flow card not found")

    if not card.qr_code:
        raise HTTPException(status_code=400, detail="Card has no QR code")

    from app.services.qr_service import generate_process_flow_qr, generate_qr_base64
    qr_content = generate_process_flow_qr(card.id, card.card_no)
    qr_image_base64 = generate_qr_base64(qr_content)

    # Record reprint scan log
    from app.models.warehouse import QRScanLog
    log = QRScanLog(
        scan_type="PFC",
        entity_id=card.id,
        entity_no=card.card_no,
        operator_id=current_user.id,
        operation="reprint",
        notes="PFC QR code reprint",
    )
    db.add(log)
    await db.commit()

    return PFCReprintResponse(
        card_id=card.id,
        card_no=card.card_no,
        qr_content=qr_content,
        qr_image_base64=qr_image_base64,
    )
