"""Business logic for the canonical tooling model and machine maintenance flow."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.machine import Machine, MachineState
from app.models.tooling import Tooling, ToolingMaintenanceLog, ToolingState
from app.models.user import User


def _status_for_state(state: ToolingState) -> str:
    return {
        ToolingState.AVAILABLE: "active",
        ToolingState.IN_USE: "in_use",
        ToolingState.MAINTENANCE: "maintenance",
        ToolingState.CONVERTED: "converted",
        ToolingState.SCRAPPED: "scrapped",
    }[state]


def generate_tooling_number() -> str:
    now = datetime.utcnow()
    return f"TL-{now:%Y%m%d-%H%M%S%f}"


async def get_tooling_by_id(db: AsyncSession, tooling_id: int) -> Optional[Tooling]:
    result = await db.execute(
        select(Tooling)
        .options(selectinload(Tooling.maintenance_logs))
        .where(Tooling.id == tooling_id, Tooling.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_tooling(db: AsyncSession, **values) -> Tooling:
    values = {key: value for key, value in values.items() if value is not None}
    values.setdefault("tooling_number", generate_tooling_number())
    tooling = Tooling(**values)
    db.add(tooling)
    await db.commit()
    return await get_tooling_by_id(db, tooling.id)


async def get_toolings(
    db: AsyncSession,
    status: Optional[str] = None,
    tooling_number: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Tooling]:
    query = select(Tooling).where(Tooling.is_deleted == False)
    if status:
        query = query.where(Tooling.status == status)
    if tooling_number:
        query = query.where(Tooling.tooling_number.ilike(f"%{tooling_number.strip()}%"))
    query = query.order_by(Tooling.created_at.desc()).offset(skip).limit(limit)
    return (await db.execute(query)).scalars().all()


async def update_tooling(db: AsyncSession, tooling: Tooling, **values) -> Tooling:
    for field, value in values.items():
        if value is not None and hasattr(tooling, field):
            setattr(tooling, field, value)
    tooling.updated_at = datetime.utcnow()
    await db.commit()
    return await get_tooling_by_id(db, tooling.id)


async def report_fault(db: AsyncSession, machine: Machine, fault_reason: Optional[str], reporter: User) -> Machine:
    if machine.state == MachineState.FAULT:
        raise ValueError("Machine already has an active fault report")
    machine.state = MachineState.FAULT
    machine.fault_time = datetime.utcnow()
    machine.fault_reported_by = reporter.id
    machine.fault_reason = fault_reason
    await db.commit()
    await db.refresh(machine)
    return machine


async def _active_log(db: AsyncSession, tooling_id: int) -> Optional[ToolingMaintenanceLog]:
    result = await db.execute(
        select(ToolingMaintenanceLog).where(
            ToolingMaintenanceLog.tooling_id == tooling_id,
            ToolingMaintenanceLog.is_active == True,
        ).order_by(ToolingMaintenanceLog.created_at.desc())
    )
    return result.scalars().first()


async def first_scan(db: AsyncSession, machine: Machine, fault_reason: Optional[str] = None) -> Machine:
    if machine.state != MachineState.FAULT:
        raise ValueError(f"Machine not in fault state: {machine.state.value}")
    machine.state = MachineState.PENDING_CHECK
    machine.repair_start_time = datetime.utcnow()
    if machine.current_tooling_id:
        tooling = await db.get(Tooling, machine.current_tooling_id)
        if tooling:
            db.add(ToolingMaintenanceLog(
                tooling_id=tooling.id,
                machine_id=machine.id,
                fault_time=machine.fault_time or datetime.utcnow(),
                fault_reason=fault_reason or machine.fault_reason,
                repair_start_time=datetime.utcnow(),
                is_active=True,
            ))
            tooling.status = _status_for_state(ToolingState.MAINTENANCE)
    await db.commit()
    await db.refresh(machine)
    return machine


async def second_scan(db: AsyncSession, machine: Machine, action: str, operator: User) -> Machine:
    if machine.state != MachineState.PENDING_CHECK:
        raise ValueError(f"Machine not pending check: {machine.state.value}")
    if action not in ("complete", "dismount"):
        raise ValueError("Invalid action: complete or dismount")
    tooling_id = machine.current_tooling_id
    if tooling_id:
        tooling = await db.get(Tooling, tooling_id)
        log = await _active_log(db, tooling_id)
        if log:
            log.repair_end_time = datetime.utcnow()
            log.repair_completed_by = operator.id
            log.is_active = False
        if tooling:
            tooling.status = (
                _status_for_state(ToolingState.AVAILABLE)
                if action == "complete"
                else _status_for_state(ToolingState.MAINTENANCE)
            )
    machine.state = MachineState.IDLE if action == "dismount" else (
        MachineState.RUNNING if tooling_id else MachineState.IDLE
    )
    machine.repair_start_time = None
    if action == "dismount":
        machine.current_tooling_id = None
    await db.commit()
    await db.refresh(machine)
    return machine


async def get_maintenance_pool(
    db: AsyncSession,
    tooling_number: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Tooling]:
    query = select(Tooling).where(
        Tooling.is_deleted == False,
        Tooling.status == _status_for_state(ToolingState.MAINTENANCE),
    )
    if tooling_number:
        query = query.where(Tooling.tooling_number.ilike(f"%{tooling_number.strip()}%"))
    return (await db.execute(
        query.order_by(Tooling.updated_at.desc()).offset(skip).limit(limit)
    )).scalars().all()


async def complete_maintenance(db: AsyncSession, tooling: Tooling, notes: Optional[str] = None) -> Tooling:
    if tooling.status != _status_for_state(ToolingState.MAINTENANCE):
        raise ValueError(f"Tooling not in maintenance: {tooling.status}")
    log = await _active_log(db, tooling.id)
    if log:
        log.repair_end_time = datetime.utcnow()
        log.is_active = False
        log.notes = notes
    tooling.status = _status_for_state(ToolingState.AVAILABLE)
    tooling.updated_at = datetime.utcnow()
    await db.commit()
    return await get_tooling_by_id(db, tooling.id)


async def mount_tooling(db: AsyncSession, tooling: Tooling, machine: Machine) -> Machine:
    if tooling.status not in {
        _status_for_state(ToolingState.AVAILABLE),
        _status_for_state(ToolingState.IN_USE),
        "DRAFT",
    }:
        raise ValueError(f"Tooling not available: {tooling.status}")
    if machine.current_tooling_id:
        raise ValueError("Machine already has tooling mounted")
    tooling.status = _status_for_state(ToolingState.IN_USE)
    machine.current_tooling_id = tooling.id
    await db.commit()
    await db.refresh(machine)
    return machine


async def unmount_tooling(db: AsyncSession, machine: Machine) -> Machine:
    if not machine.current_tooling_id:
        raise ValueError("No tooling mounted on machine")
    tooling = await db.get(Tooling, machine.current_tooling_id)
    if tooling:
        tooling.status = _status_for_state(ToolingState.AVAILABLE)
    machine.current_tooling_id = None
    await db.commit()
    await db.refresh(machine)
    return machine


async def update_tooling_state(db: AsyncSession, tooling: Tooling, state: ToolingState) -> Tooling:
    tooling.status = _status_for_state(state)
    await db.commit()
    return await get_tooling_by_id(db, tooling.id)
