"""Production planning and session API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.production import PlanState, SessionState
from app.schemas.production import (
    MachineAssignmentCreate,
    MachineAssignmentResponse,
    ProductionPlanCreate,
    ProductionPlanListResponse,
    ProductionPlanResponse,
    ProductionPlanUpdate,
    ProductionReportCreate,
    ProductionReportResponse,
    ProcessFlowCardResponse,
    SessionCloseRequest,
    SessionResponse,
    SessionStartRequest,
    SessionStartResponse,
)
from app.services import production_service, session_service, process_flow_service

router = APIRouter(prefix="/production", tags=["Production"])


@router.post("/plans", response_model=ProductionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: ProductionPlanCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Create a new production plan (requires role_level >= 3)."""
    require_role(current_user, min_level=3)

    try:
        plan = await production_service.create_plan(db, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionPlanResponse(
        id=plan.id,
        plan_no=plan.plan_no,
        part_id=plan.part_id,
        part_no=plan.part.part_no if plan.part else None,
        part_name=plan.part.part_name if plan.part else None,
        total_qty=plan.total_qty,
        completed_qty=plan.completed_qty,
        priority=plan.priority,
        due_date=plan.due_date,
        start_date=plan.start_date,
        completed_date=plan.completed_date,
        state=plan.state,
        notes=plan.notes,
        created_by=plan.created_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("/plans", response_model=list[ProductionPlanListResponse])
async def list_plans(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[PlanState] = Query(default=None),
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProductionPlanListResponse]:
    """List production plans with optional filters."""
    plans = await production_service.get_plans(db, state=state, part_id=part_id, skip=skip, limit=limit)

    now = datetime.utcnow()
    return [
        ProductionPlanListResponse(
            id=p.id,
            plan_no=p.plan_no,
            part_id=p.part_id,
            part_no=p.part.part_no if p.part else None,
            part_name=p.part.part_name if p.part else None,
            total_qty=p.total_qty,
            completed_qty=p.completed_qty,
            priority=p.priority,
            due_date=p.due_date,
            state=p.state,
            progress_pct=round(p.completed_qty / p.total_qty * 100, 1) if p.total_qty > 0 else 0,
            is_overdue=p.due_date < now and p.state not in (PlanState.COMPLETED, PlanState.CLOSED, PlanState.CANCELLED),
            created_at=p.created_at,
        )
        for p in plans
    ]


@router.get("/plans/{plan_id}", response_model=ProductionPlanResponse)
async def get_plan(
    plan_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Get production plan by ID."""
    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    return ProductionPlanResponse(
        id=plan.id,
        plan_no=plan.plan_no,
        part_id=plan.part_id,
        part_no=plan.part.part_no if plan.part else None,
        part_name=plan.part.part_name if plan.part else None,
        total_qty=plan.total_qty,
        completed_qty=plan.completed_qty,
        priority=plan.priority,
        due_date=plan.due_date,
        start_date=plan.start_date,
        completed_date=plan.completed_date,
        state=plan.state,
        notes=plan.notes,
        created_by=plan.created_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.patch("/plans/{plan_id}", response_model=ProductionPlanResponse)
async def update_plan(
    plan_id: int,
    data: ProductionPlanUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Update production plan."""
    require_role(current_user, min_level=3)

    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    try:
        plan = await production_service.update_plan(db, plan, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionPlanResponse(
        id=plan.id,
        plan_no=plan.plan_no,
        part_id=plan.part_id,
        part_no=plan.part.part_no if plan.part else None,
        part_name=plan.part.part_name if plan.part else None,
        total_qty=plan.total_qty,
        completed_qty=plan.completed_qty,
        priority=plan.priority,
        due_date=plan.due_date,
        start_date=plan.start_date,
        completed_date=plan.completed_date,
        state=plan.state,
        notes=plan.notes,
        created_by=plan.created_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.post("/plans/{plan_id}/assign-machine", response_model=MachineAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_machine(
    plan_id: int,
    data: MachineAssignmentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineAssignmentResponse:
    """Assign a machine to a production plan."""
    require_role(current_user, min_level=3)

    try:
        assignment = await production_service.assign_machine(db, plan_id, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MachineAssignmentResponse(
        id=assignment.id,
        plan_id=assignment.plan_id,
        machine_id=assignment.machine_id,
        machine_no=assignment.machine.machine_no if assignment.machine else None,
        machine_name=assignment.machine.name if assignment.machine else None,
        assigned_qty=assignment.assigned_qty,
        is_primary=assignment.is_primary,
        assigned_at=assignment.assigned_at,
        assigned_by=assignment.assigned_by,
    )


@router.get("/plans/{plan_id}/assignments", response_model=list[MachineAssignmentResponse])
async def get_plan_assignments(
    plan_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MachineAssignmentResponse]:
    """Get machine assignments for a plan."""
    assignments = await production_service.get_plan_assignments(db, plan_id)

    return [
        MachineAssignmentResponse(
            id=a.id,
            plan_id=a.plan_id,
            machine_id=a.machine_id,
            machine_no=a.machine.machine_no if a.machine else None,
            machine_name=a.machine.name if a.machine else None,
            assigned_qty=a.assigned_qty,
            is_primary=a.is_primary,
            assigned_at=a.assigned_at,
            assigned_by=a.assigned_by,
        )
        for a in assignments
    ]


@router.post("/sessions/start", response_model=SessionStartResponse)
async def start_session(
    data: SessionStartRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SessionStartResponse:
    """Start a production session (scan workflow)."""
    require_role(current_user, min_level=1)

    try:
        result = await session_service.start_session(db, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SessionStartResponse(**result)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    plan_id: Optional[int] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    state: Optional[SessionState] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SessionResponse]:
    """List production sessions."""
    sessions = await session_service.get_sessions(db, plan_id, machine_id, state, skip, limit)

    return [
        SessionResponse(
            id=s.id,
            session_no=s.session_no,
            plan_id=s.plan_id,
            machine_id=s.machine_id,
            machine_no=s.machine.machine_no if s.machine else None,
            material_batch_id=s.material_batch_id,
            tooling_id=s.tooling_id,
            tooling_no=None,  # Would need to fetch
            material_validated=s.material_validated,
            force_started=s.force_started,
            state=s.state,
            total_strokes=s.total_strokes,
            total_output=s.total_output,
            total_good_qty=s.total_good_qty,
            started_at=s.started_at,
            closed_at=s.closed_at,
            process_flow_no=s.process_flow_no,
        )
        for s in sessions
    ]


@router.post("/reports", response_model=ProductionReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_report(
    data: ProductionReportCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionReportResponse:
    """Submit a production report (strokes report)."""
    require_role(current_user, min_level=1)

    try:
        report = await session_service.submit_report(db, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionReportResponse(
        id=report.id,
        report_no=report.report_no,
        session_id=report.session_id,
        strokes=report.strokes,
        cavity_count=report.cavity_count,
        output_qty=report.output_qty,
        good_qty=report.good_qty,
        reject_qty=report.reject_qty,
        reject_reasons=report.reject_reasons,
        operator_id=report.operator_id,
        operator_name=report.operator_name,
        reported_at=report.reported_at,
    )


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: int,
    data: Optional[SessionCloseRequest] = None,
    db: DbSession = Depends(),
    current_user: CurrentUser = Depends(),
) -> dict:
    """Close a production session and generate process flow card."""
    require_role(current_user, min_level=1)

    try:
        result = await session_service.close_session(db, session_id, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SessionResponse:
    """Get production session by ID."""
    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Production session not found")

    return SessionResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        machine_no=session.machine.machine_no if session.machine else None,
        material_batch_id=session.material_batch_id,
        tooling_id=session.tooling_id,
        tooling_no=None,
        material_validated=session.material_validated,
        force_started=session.force_started,
        state=session.state,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        total_good_qty=session.total_good_qty,
        started_at=session.started_at,
        closed_at=session.closed_at,
        process_flow_no=session.process_flow_no,
    )


@router.get("/sessions/{session_id}/reports", response_model=list[ProductionReportResponse])
async def get_session_reports(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProductionReportResponse]:
    """Get all reports for a session."""
    reports = await session_service.get_session_reports(db, session_id)

    return [
        ProductionReportResponse(
            id=r.id,
            report_no=r.report_no,
            session_id=r.session_id,
            strokes=r.strokes,
            cavity_count=r.cavity_count,
            output_qty=r.output_qty,
            good_qty=r.good_qty,
            reject_qty=r.reject_qty,
            reject_reasons=r.reject_reasons,
            operator_id=r.operator_id,
            operator_name=r.operator_name,
            reported_at=r.reported_at,
        )
        for r in reports
    ]


@router.get("/process-flows", response_model=list[ProcessFlowCardResponse])
async def list_process_flows(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProcessFlowCardResponse]:
    """List process flow cards."""
    flows = await process_flow_service.get_process_flows(
        db, part_id=part_id, machine_id=machine_id, skip=skip, limit=limit
    )

    return [
        ProcessFlowCardResponse(
            id=f.id,
            card_no=f.card_no,
            session_id=f.session_id,
            part_id=f.part_id,
            part_no=f.part.part_no if f.part else None,
            part_name=f.part.part_name if f.part else None,
            machine_id=f.machine_id,
            machine_no=f.machine.machine_no if f.machine else None,
            material_batch_id=f.material_batch_id,
            material_lot_no=f.material_lot_no,
            total_strokes=f.total_strokes,
            total_output=f.total_output,
            good_qty=f.good_qty,
            reject_qty=f.reject_qty,
            production_start=f.production_start,
            production_end=f.production_end,
            duration_minutes=f.duration_minutes,
            status=f.status,
            qr_code_path=f.qr_code_path,
            created_at=f.created_at,
        )
        for f in flows
    ]


@router.get("/process-flows/{card_no}", response_model=ProcessFlowCardResponse)
async def get_process_flow(
    card_no: str,
    db: DbSession,
    current_user: CurrentUser,
) -> ProcessFlowCardResponse:
    """Get process flow card by card number."""
    flow = await process_flow_service.get_process_flow_by_no(db, card_no)
    if not flow:
        raise HTTPException(status_code=404, detail="Process flow card not found")

    return ProcessFlowCardResponse(
        id=flow.id,
        card_no=flow.card_no,
        session_id=flow.session_id,
        part_id=flow.part_id,
        part_no=flow.part.part_no if flow.part else None,
        part_name=flow.part.part_name if flow.part else None,
        machine_id=flow.machine_id,
        machine_no=flow.machine.machine_no if flow.machine else None,
        material_batch_id=flow.material_batch_id,
        material_lot_no=flow.material_lot_no,
        total_strokes=flow.total_strokes,
        total_output=flow.total_output,
        good_qty=flow.good_qty,
        reject_qty=flow.reject_qty,
        production_start=flow.production_start,
        production_end=flow.production_end,
        duration_minutes=flow.duration_minutes,
        status=flow.status,
        qr_code_path=flow.qr_code_path,
        created_at=flow.created_at,
    )
