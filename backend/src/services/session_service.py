"""Business logic for production session management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.machine import Machine, MachineState
from app.models.part import Part
from app.models.production import (
    PlanState,
    ProcessFlowCard,
    ProductionReport,
    ProductionSession,
    SessionState,
)
from app.models.tooling import Tooling
from app.models.user import User
from app.schemas.production import ProductionReportCreate, SessionCloseRequest, SessionStartRequest


def generate_session_no(db: AsyncSession) -> str:
    """Generate a unique session number."""
    now = datetime.utcnow()
    return f"PS-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


def generate_report_no(db: AsyncSession) -> str:
    """Generate a unique report number."""
    now = datetime.utcnow()
    return f"PR-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


def generate_process_flow_no(db: AsyncSession) -> str:
    """Generate a unique process flow card number."""
    now = datetime.utcnow()
    return f"PFC-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


async def get_session_by_id(
    db: AsyncSession,
    session_id: int,
) -> Optional[ProductionSession]:
    """Get production session by ID."""
    result = await db.execute(
        select(ProductionSession)
        .options(
            selectinload(ProductionSession.plan),
            selectinload(ProductionSession.machine),
        )
        .where(ProductionSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def get_active_session(
    db: AsyncSession,
    machine_id: int,
) -> Optional[ProductionSession]:
    """Get active session for a machine."""
    result = await db.execute(
        select(ProductionSession)
        .options(selectinload(ProductionSession.plan))
        .where(
            ProductionSession.machine_id == machine_id,
            ProductionSession.state == SessionState.OPEN,
        )
        .order_by(ProductionSession.started_at.desc())
    )
    return result.scalar_one_or_none()


async def start_session(
    db: AsyncSession,
    data: SessionStartRequest,
    operator: User,
) -> dict:
    """Start a production session.

    Validates material-tooling matching and creates session.
    """
    # Validate plan exists
    result = await db.execute(
        select(ProductionSession).where(ProductionSession.plan_id == data.plan_id)
    )
    existing = result.scalar_one_or_none()
    if existing and existing.state == SessionState.OPEN:
        raise ValueError("There is already an active session for this plan")

    # Get machine
    machine_result = await db.execute(
        select(Machine).where(Machine.id == data.machine_id, Machine.is_deleted == False)
    )
    machine = machine_result.scalar_one_or_none()
    if not machine:
        raise ValueError("Machine not found")

    # Get tooling from machine
    tooling_id = data.tooling_id or machine.current_tooling_id
    tooling = None
    tooling_no = None
    if tooling_id:
        tooling_result = await db.execute(
            select(Tooling).where(Tooling.id == tooling_id)
        )
        tooling = tooling_result.scalar_one_or_none()
        if tooling:
            tooling_no = tooling.tooling_no

    # Validate material-tooling matching
    machine_matching = True
    material_validated = False

    if data.material_batch_id and tooling_id:
        # TODO: Add actual material-tooling validation logic
        # For now, just check if both are provided
        material_validated = True

    # Create session
    session_no = generate_session_no(db)
    session = ProductionSession(
        session_no=session_no,
        plan_id=data.plan_id,
        machine_id=data.machine_id,
        material_batch_id=data.material_batch_id,
        tooling_id=tooling_id,
        material_validated=material_validated,
        force_started=False,
        state=SessionState.OPEN,
    )
    db.add(session)

    # Update machine state
    machine.state = MachineState.RUNNING

    await db.commit()
    await db.refresh(session)

    message = "会话开启成功"
    if not material_validated:
        message = "会话开启成功，但原材料与模具匹配验证未完成"

    return {
        "session_id": session.id,
        "session_no": session.session_no,
        "plan_id": session.plan_id,
        "machine_id": session.machine_id,
        "material_validated": session.material_validated,
        "force_started": session.force_started,
        "tooling_id": tooling_id,
        "tooling_no": tooling_no,
        "machine_matching": machine_matching,
        "message": message,
    }


async def submit_report(
    db: AsyncSession,
    data: ProductionReportCreate,
    operator: User,
) -> ProductionReport:
    """Submit a production report (stroke report)."""
    # Get session
    session = await get_session_by_id(db, data.session_id)
    if not session:
        raise ValueError("Production session not found")

    if session.state != SessionState.OPEN:
        raise ValueError("Session is not open")

    # Get cavity count from tooling
    cavity_count = 1
    if session.tooling_id:
        tooling_result = await db.execute(
            select(Tooling).where(Tooling.id == session.tooling_id)
        )
        tooling = tooling_result.scalar_one_or_none()
        if tooling and tooling.cavity_count:
            cavity_count = tooling.cavity_count

    # Calculate output
    output_qty = data.strokes * cavity_count

    # Generate report number
    report_no = generate_report_no(db)

    # Create report
    report = ProductionReport(
        report_no=report_no,
        session_id=data.session_id,
        strokes=data.strokes,
        cavity_count=cavity_count,
        output_qty=output_qty,
        good_qty=data.good_qty,
        reject_qty=data.reject_qty,
        reject_reasons=data.reject_reasons,
        operator_id=operator.id if hasattr(operator, 'id') else None,
        operator_name=data.operator_name,
    )
    db.add(report)

    # Update session totals
    session.total_strokes += data.strokes
    session.total_output += output_qty
    session.total_good_qty += data.good_qty

    await db.commit()
    await db.refresh(report)
    return report


async def close_session(
    db: AsyncSession,
    session_id: int,
    data: Optional[SessionCloseRequest],
    operator: User,
) -> dict:
    """Close a production session and generate process flow card."""
    session = await get_session_by_id(db, session_id)
    if not session:
        raise ValueError("Production session not found")

    if session.state != SessionState.OPEN:
        raise ValueError("Session is not open")

    # Close session
    session.state = SessionState.CLOSED
    session.closed_at = datetime.utcnow()
    session.closed_by = operator.id if hasattr(operator, 'id') else None

    # Get related entities
    plan_result = await db.execute(
        select(ProductionSession).where(ProductionSession.id == session_id)
    )
    session_data = plan_result.scalar_one_or_none()
    plan_id = session.plan_id

    # Get plan for part info
    from app.models.production import ProductionPlan
    plan_result = await db.execute(
        select(ProductionPlan).where(ProductionPlan.id == plan_id)
    )
    plan = plan_result.scalar_one_or_none()

    # Get machine
    machine_result = await db.execute(
        select(Machine).where(Machine.id == session.machine_id)
    )
    machine = machine_result.scalar_one_or_none()

    # Calculate duration
    duration = 0
    if session.started_at and session.closed_at:
        duration = int((session.closed_at - session.started_at).total_seconds() / 60)

    # Generate process flow card
    process_flow_no = generate_process_flow_no(db)
    session.process_flow_no = process_flow_no

    part_id = plan.part_id if plan else 0

    process_card = ProcessFlowCard(
        card_no=process_flow_no,
        session_id=session.id,
        part_id=part_id,
        machine_id=session.machine_id,
        material_batch_id=session.material_batch_id,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.total_good_qty,
        reject_qty=session.total_output - session.total_good_qty,
        production_start=session.started_at,
        production_end=session.closed_at,
        duration_minutes=duration,
    )
    db.add(process_card)

    # Update plan completed quantity
    if plan:
        plan.completed_qty += session.total_good_qty
        if plan.completed_qty >= plan.total_qty:
            plan.state = PlanState.COMPLETED
            plan.completed_date = datetime.utcnow()

    # Update machine state
    if machine:
        machine.state = MachineState.IDLE

    await db.commit()
    await db.refresh(session)
    await db.refresh(process_card)

    return {
        "session_id": session.id,
        "session_no": session.session_no,
        "process_flow_no": process_flow_no,
        "total_strokes": session.total_strokes,
        "total_output": session.total_output,
        "good_qty": session.total_good_qty,
        "reject_qty": session.total_output - session.total_good_qty,
        "duration_minutes": duration,
        "plan_completed_qty": plan.completed_qty if plan else 0,
        "plan_total_qty": plan.total_qty if plan else 0,
    }


async def get_session_reports(
    db: AsyncSession,
    session_id: int,
) -> Sequence[ProductionReport]:
    """Get all reports for a session."""
    result = await db.execute(
        select(ProductionReport)
        .where(ProductionReport.session_id == session_id)
        .order_by(ProductionReport.reported_at.desc())
    )
    return result.scalars().all()


async def get_sessions(
    db: AsyncSession,
    plan_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    state: Optional[SessionState] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[ProductionSession]:
    """Get production sessions with filters."""
    query = (
        select(ProductionSession)
        .options(selectinload(ProductionSession.machine))
        .where(ProductionSession.id > 0)
    )

    if plan_id:
        query = query.where(ProductionSession.plan_id == plan_id)
    if machine_id:
        query = query.where(ProductionSession.machine_id == machine_id)
    if state:
        query = query.where(ProductionSession.state == state)

    query = query.order_by(ProductionSession.started_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
