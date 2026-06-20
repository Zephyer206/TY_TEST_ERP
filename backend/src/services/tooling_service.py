"""Business logic for tooling/mold management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from src.models.machine import Machine, MachineState
from src.models.tooling import Tooling, ToolingMaintenanceLog, ToolingPart, ToolingState
from src.models.user import User


def generate_tooling_no() -> str:
    """Generate a unique tooling number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"TL-{prefix}-{now.strftime('%H%M%S')}"


async def create_tooling(
    db: AsyncSession,
    name: str,
    customer_product_no: Optional[str] = None,
    cavity_count: Optional[int] = None,
    tonnage: Optional[float] = None,
    ppap_no: Optional[str] = None,
    vehicle_model: Optional[str] = None,
    spec_data: Optional[str] = None,
    parent_id: Optional[int] = None,
) -> Tooling:
    """Create a new tooling/mold record.

    Tooling starts in AVAILABLE state.
    """
    tooling_no = generate_tooling_no()

    tooling = Tooling(
        tooling_no=tooling_no,
        name=name,
        customer_product_no=customer_product_no,
        cavity_count=cavity_count,
        tonnage=tonnage,
        ppap_no=ppap_no,
        vehicle_model=vehicle_model,
        spec_data=spec_data,
        parent_id=parent_id,
        state=ToolingState.AVAILABLE,
    )
    db.add(tooling)
    await db.commit()
    await db.refresh(tooling)
    return tooling


async def get_tooling_by_id(
    db: AsyncSession,
    tooling_id: int,
) -> Optional[Tooling]:
    """Get a tooling by ID with parent-child relationships and maintenance logs."""
    result = await db.execute(
        select(Tooling)
        .options(
            selectinload(Tooling.children),
            joinedload(Tooling.parent),
            selectinload(Tooling.maintenance_logs),
        )
        .where(Tooling.id == tooling_id, Tooling.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_toolings(
    db: AsyncSession,
    state: Optional[ToolingState] = None,
    customer_product_no: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Tooling]:
    """Get toolings with optional filters."""
    query = (
        select(Tooling)
        .options(
            selectinload(Tooling.children),
            joinedload(Tooling.parent),
        )
        .where(Tooling.is_deleted == False)
    )

    if state:
        query = query.where(Tooling.state == state)
    if customer_product_no:
        query = query.where(Tooling.customer_product_no.ilike(f"%{customer_product_no}%"))

    query = query.order_by(Tooling.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_tooling(
    db: AsyncSession,
    tooling: Tooling,
    name: Optional[str] = None,
    customer_product_no: Optional[str] = None,
    cavity_count: Optional[int] = None,
    tonnage: Optional[float] = None,
    ppap_no: Optional[str] = None,
    vehicle_model: Optional[str] = None,
    spec_data: Optional[str] = None,
) -> Tooling:
    """Update tooling basic info."""
    if name is not None:
        tooling.name = name
    if customer_product_no is not None:
        tooling.customer_product_no = customer_product_no
    if cavity_count is not None:
        tooling.cavity_count = cavity_count
    if tonnage is not None:
        tooling.tonnage = tonnage
    if ppap_no is not None:
        tooling.ppap_no = ppap_no
    if vehicle_model is not None:
        tooling.vehicle_model = vehicle_model
    if spec_data is not None:
        tooling.spec_data = spec_data

    await db.commit()
    await db.refresh(tooling)
    return tooling


async def report_fault(
    db: AsyncSession,
    machine: Machine,
    fault_reason: Optional[str],
    reporter: User,
) -> Machine:
    """Report a fault on a machine.

    Machine enters FAULT state, waiting for first scan confirmation.
    """
    if machine.state == MachineState.FAULT:
        raise ValueError("Machine already has an active fault report")

    machine.state = MachineState.FAULT
    machine.fault_time = datetime.utcnow()
    machine.fault_reported_by = reporter.id
    machine.fault_reason = fault_reason

    await db.commit()
    await db.refresh(machine)
    return machine


async def first_scan(
    db: AsyncSession,
    machine: Machine,
    fault_reason: Optional[str] = None,
) -> Machine:
    """First scan on a faulty machine - start maintenance.

    Machine enters PENDING_CHECK state (maintenance in progress).
    If machine has tooling mounted, create maintenance log for the tooling.
    """
    if machine.state != MachineState.FAULT:
        raise ValueError(f"Machine not in fault state: {machine.state.value}")

    machine.state = MachineState.PENDING_CHECK
    machine.repair_start_time = datetime.utcnow()

    if machine.current_tooling_id:
        tooling_result = await db.execute(
            select(Tooling).where(Tooling.id == machine.current_tooling_id)
        )
        tooling = tooling_result.scalar_one_or_none()
        if tooling:
            log = ToolingMaintenanceLog(
                tooling_id=tooling.id,
                machine_id=machine.id,
                fault_time=machine.fault_time,
                fault_reason=fault_reason or machine.fault_reason,
                repair_start_time=datetime.utcnow(),
            )
            db.add(log)
            await db.flush()
            tooling.active_maintenance_id = log.id
            tooling.state = ToolingState.MAINTENANCE

    await db.commit()
    await db.refresh(machine)
    return machine


async def second_scan(
    db: AsyncSession,
    machine: Machine,
    action: str,
    operator: User,
) -> Machine:
    """Second scan on a machine under repair - complete repair or dismount tooling.

    Actions:
    - 'complete': Mark repair complete, machine returns to RUNNING (if had job) or IDLE
    - 'dismount': Remove tooling from machine, tooling enters maintenance pool
    """
    if machine.state != MachineState.PENDING_CHECK:
        raise ValueError(f"Machine not pending check: {machine.state.value}")

    if action not in ("complete", "dismount"):
        raise ValueError(f"Invalid action: {action}. Must be 'complete' or 'dismount'")

    tooling_id = machine.current_tooling_id

    if action == "complete":
        machine.state = MachineState.IDLE if not machine.current_tooling_id else MachineState.RUNNING
        machine.repair_start_time = None

        if tooling_id:
            tooling_result = await db.execute(
                select(Tooling).where(Tooling.id == tooling_id)
            )
            tooling = tooling_result.scalar_one_or_none()
            if tooling and tooling.active_maintenance_id:
                log_result = await db.execute(
                    select(ToolingMaintenanceLog).where(
                        ToolingMaintenanceLog.id == tooling.active_maintenance_id
                    )
                )
                log = log_result.scalar_one_or_none()
                if log:
                    log.repair_end_time = datetime.utcnow()
                    log.repair_completed_by = operator.id
                    log.is_active = False
                tooling.active_maintenance_id = None

    elif action == "dismount":
        machine.state = MachineState.IDLE
        machine.repair_start_time = None

        if tooling_id:
            tooling_result = await db.execute(
                select(Tooling).where(Tooling.id == tooling_id)
            )
            tooling = tooling_result.scalar_one_or_none()
            if tooling:
                tooling.state = ToolingState.MAINTENANCE
                if tooling.active_maintenance_id:
                    log_result = await db.execute(
                        select(ToolingMaintenanceLog).where(
                            ToolingMaintenanceLog.id == tooling.active_maintenance_id
                        )
                    )
                    log = log_result.scalar_one_or_none()
                    if log:
                        log.repair_end_time = datetime.utcnow()
                        log.repair_completed_by = operator.id
                        log.is_active = False

        machine.current_tooling_id = None

    await db.commit()
    await db.refresh(machine)
    return machine


async def get_maintenance_pool(
    db: AsyncSession,
    tooling_no: Optional[str] = None,
    customer_product_no: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Tooling]:
    """Get toolings in maintenance pool (state = MAINTENANCE)."""
    query = (
        select(Tooling)
        .options(
            joinedload(Tooling.parent),
            selectinload(Tooling.children),
        )
        .where(
            Tooling.is_deleted == False,
            Tooling.state == ToolingState.MAINTENANCE,
        )
    )

    if tooling_no:
        query = query.where(Tooling.tooling_no.ilike(f"%{tooling_no}%"))
    if customer_product_no:
        query = query.where(Tooling.customer_product_no.ilike(f"%{customer_product_no}%"))

    query = query.order_by(Tooling.updated_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def complete_maintenance(
    db: AsyncSession,
    tooling: Tooling,
    notes: Optional[str] = None,
) -> Tooling:
    """Complete tooling maintenance and return to available state."""
    if tooling.state != ToolingState.MAINTENANCE:
        raise ValueError(f"Tooling not in maintenance: {tooling.state.value}")

    if tooling.active_maintenance_id:
        log_result = await db.execute(
            select(ToolingMaintenanceLog).where(
                ToolingMaintenanceLog.id == tooling.active_maintenance_id
            )
        )
        log = log_result.scalar_one_or_none()
        if log:
            log.repair_end_time = datetime.utcnow()
            log.is_active = False
            log.notes = notes

    tooling.state = ToolingState.AVAILABLE
    tooling.active_maintenance_id = None

    await db.commit()
    await db.refresh(tooling)
    return tooling


async def mount_tooling(
    db: AsyncSession,
    tooling: Tooling,
    machine: Machine,
) -> Machine:
    """Mount a tooling to a machine."""
    if tooling.state not in (ToolingState.AVAILABLE, ToolingState.IN_USE):
        raise ValueError(f"Tooling not available: {tooling.state.value}")

    if machine.current_tooling_id:
        raise ValueError("Machine already has tooling mounted")

    tooling.state = ToolingState.IN_USE
    machine.current_tooling_id = tooling.id

    await db.commit()
    await db.refresh(machine)
    return machine


async def unmount_tooling(
    db: AsyncSession,
    machine: Machine,
) -> Machine:
    """Unmount tooling from a machine."""
    if not machine.current_tooling_id:
        raise ValueError("No tooling mounted on machine")

    tooling_result = await db.execute(
        select(Tooling).where(Tooling.id == machine.current_tooling_id)
    )
    tooling = tooling_result.scalar_one_or_none()

    if tooling:
        tooling.state = ToolingState.AVAILABLE

    machine.current_tooling_id = None

    await db.commit()
    await db.refresh(machine)
    return machine


async def update_tooling_state(
    db: AsyncSession,
    tooling: Tooling,
    state: ToolingState,
) -> Tooling:
    """Update tooling state."""
    tooling.state = state
    await db.commit()
    await db.refresh(tooling)
    return tooling
