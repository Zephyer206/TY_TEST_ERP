"""Business logic for tooling/mold management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.machine import Machine, MachineState
from app.models.part import Part
from app.models.tooling import (
    Tooling,
    ToolingCavityStatus,
    ToolingMaintenanceLog,
    ToolingMaintenanceType,
    ToolingPart,
    ToolingState,
)
from app.models.user import User
from app.schemas.tooling import (
    ToolingCreate,
    ToolingMountUpdate,
    ToolingPartCreate,
    ToolingScanActionRequest,
    ToolingScanRequest,
    ToolingUpdate,
)


def generate_tooling_no(db: AsyncSession) -> str:
    """Generate a unique tooling number."""
    now = datetime.utcnow()
    prefix = now.strftime("%y%m")
    return f"TL-{prefix}-{now.strftime('%H%M%S')}"


async def create_tooling(
    db: AsyncSession,
    data: ToolingCreate,
    creator: User,
) -> Tooling:
    """Create a new tooling record."""
    tooling_no = generate_tooling_no(db)

    tooling = Tooling(
        tooling_no=tooling_no if not data.tooling_no else data.tooling_no,
        name=data.name,
        tooling_type=data.tooling_type,
        customer_id=data.customer_id,
        parent_id=data.parent_id,
        cavity_count=data.cavity_count,
        press_tonnage=data.press_tonnage,
        spec_twph=data.spec_twph,
        ppap_no=data.ppap_no,
        vehicle_model=data.vehicle_model,
        state=ToolingState.DESIGNING,
        cavity_status=ToolingCavityStatus.OK,
        notes=data.notes,
    )
    if data.tooling_no:
        tooling.tooling_no = data.tooling_no

    db.add(tooling)
    await db.commit()
    await db.refresh(tooling)
    return tooling


async def get_tooling_by_id(
    db: AsyncSession,
    tooling_id: int,
    include_details: bool = False,
) -> Optional[Tooling]:
    """Get tooling by ID with optional related data."""
    query = select(Tooling).where(Tooling.id == tooling_id, Tooling.is_deleted == False)

    if include_details:
        query = query.options(
            selectinload(Tooling.children),
            selectinload(Tooling.customer),
            selectinload(Tooling.mounted_machine),
        )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_tooling_by_no(
    db: AsyncSession,
    tooling_no: str,
) -> Optional[Tooling]:
    """Get tooling by tooling number."""
    result = await db.execute(
        select(Tooling)
        .options(selectinload(Tooling.children))
        .where(Tooling.tooling_no == tooling_no, Tooling.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_toolings(
    db: AsyncSession,
    state: Optional[ToolingState] = None,
    customer_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    cavity_status: Optional[ToolingCavityStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Tooling]:
    """Get toolings with optional filters."""
    query = (
        select(Tooling)
        .options(
            selectinload(Tooling.customer),
            selectinload(Tooling.mounted_machine),
        )
        .where(Tooling.is_deleted == False)
    )

    if state:
        query = query.where(Tooling.state == state)
    if customer_id:
        query = query.where(Tooling.customer_id == customer_id)
    if machine_id:
        query = query.where(Tooling.mounted_machine_id == machine_id)
    if cavity_status:
        query = query.where(Tooling.cavity_status == cavity_status)

    query = query.order_by(Tooling.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_tooling(
    db: AsyncSession,
    tooling: Tooling,
    data: ToolingUpdate,
) -> Tooling:
    """Update tooling fields."""
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None and hasattr(tooling, field):
            setattr(tooling, field, value)

    await db.commit()
    await db.refresh(tooling)
    return tooling


async def mount_tooling(
    db: AsyncSession,
    tooling: Tooling,
    data: ToolingMountUpdate,
    operator: User,
) -> Tooling:
    """Mount or unmount tooling from machine."""
    if data.action == "mount":
        # Validate machine exists and is idle or has the tooling already
        result = await db.execute(
            select(Machine).where(Machine.id == data.machine_id)
        )
        machine = result.scalar_one_or_none()
        if not machine:
            raise ValueError("Machine not found")

        tooling.mounted_machine_id = machine.id
        tooling.state = ToolingState.PRODUCTION

        # Update machine state
        if machine.current_tooling_id != tooling.id:
            machine.current_tooling_id = tooling.id
            machine.state = MachineState.IDLE

    else:  # unmount
        tooling.mounted_machine_id = None

        # Update machine state
        if tooling.mounted_machine_id:
            result = await db.execute(
                select(Machine).where(Machine.id == tooling.mounted_machine_id)
            )
            machine = result.scalar_one_or_none()
            if machine and machine.current_tooling_id == tooling.id:
                machine.current_tooling_id = None
                machine.state = MachineState.IDLE

    await db.commit()
    await db.refresh(tooling)
    return tooling


async def associate_part(
    db: AsyncSession,
    tooling_id: int,
    data: ToolingPartCreate,
) -> ToolingPart:
    """Associate a part with a tooling."""
    tooling_part = ToolingPart(
        tooling_id=tooling_id,
        part_id=data.part_id,
        is_primary=data.is_primary,
        cavity_index=data.cavity_index,
        notes=data.notes,
    )
    db.add(tooling_part)
    await db.commit()
    await db.refresh(tooling_part)
    return tooling_part


async def get_tooling_parts(
    db: AsyncSession,
    tooling_id: int,
) -> Sequence[ToolingPart]:
    """Get all parts associated with a tooling."""
    result = await db.execute(
        select(ToolingPart)
        .options(selectinload(ToolingPart.part))
        .where(ToolingPart.tooling_id == tooling_id, ToolingPart.is_deleted == False)
    )
    return result.scalars().all()


async def get_maintenance_logs(
    db: AsyncSession,
    tooling_id: int,
    open_only: bool = False,
) -> Sequence[ToolingMaintenanceLog]:
    """Get maintenance logs for a tooling."""
    query = (
        select(ToolingMaintenanceLog)
        .where(
            ToolingMaintenanceLog.tooling_id == tooling_id,
            ToolingMaintenanceLog.is_deleted == False,
        )
        .order_by(ToolingMaintenanceLog.created_at.desc())
    )

    if open_only:
        query = query.where(ToolingMaintenanceLog.status == "open")

    result = await db.execute(query)
    return result.scalars().all()


async def process_machine_scan(
    db: AsyncSession,
    data: ToolingScanRequest,
    operator: User,
) -> dict:
    """Process scan on machine for two-scan maintenance workflow.

    First scan: Reports fault, starts maintenance log
    Second scan: Shows action options (repair complete, discard, etc.)
    """
    # Get machine
    result = await db.execute(
        select(Machine).where(Machine.id == data.machine_id)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise ValueError("Machine not found")

    # Get tooling
    tooling_result = await db.execute(
        select(Tooling).where(Tooling.id == data.tooling_id)
    )
    tooling = tooling_result.scalar_one_or_none()
    if not tooling:
        raise ValueError("Tooling not found")

    # Check for open maintenance log
    open_log_result = await db.execute(
        select(ToolingMaintenanceLog)
        .where(
            ToolingMaintenanceLog.tooling_id == tooling.id,
            ToolingMaintenanceLog.machine_id == machine.id,
            ToolingMaintenanceLog.status == "open",
        )
        .order_by(ToolingMaintenanceLog.first_scan_time.desc())
    )
    open_log = open_log_result.scalar_one_or_none()

    if data.scan_type == ToolingMaintenanceType.FIRST_SCAN:
        if open_log:
            raise ValueError("There is already an open maintenance log for this tooling on this machine")

        # Create new maintenance log with first scan
        log = ToolingMaintenanceLog(
            tooling_id=tooling.id,
            machine_id=machine.id,
            maintenance_type=ToolingMaintenanceType.FIRST_SCAN,
            first_scan_time=datetime.utcnow(),
            first_scan_by=operator.id,
            first_scan_notes=data.notes,
            fault_description=data.notes,
            status="open",
        )
        db.add(log)

        # Update machine state to indicate repair needed
        machine.state = MachineState.PENDING_CHECK

        # Update tooling cavity status
        tooling.cavity_status = ToolingCavityStatus.REPAIRING

        await db.commit()
        await db.refresh(log)

        return {
            "machine_id": machine.id,
            "machine_no": machine.machine_no,
            "current_state": machine.state.value,
            "current_tooling_id": tooling.id,
            "current_tooling_no": tooling.tooling_no,
            "scan_result": "first_scan_registered",
            "message": "维修工单已登记，请进行维修",
            "requires_second_scan": True,
            "pending_log_id": log.id,
        }

    else:  # SECOND_SCAN
        if not open_log:
            raise ValueError("No open maintenance log found. Please perform first scan first.")

        # Update log with second scan
        open_log.second_scan_time = datetime.utcnow()
        open_log.second_scan_by = operator.id
        open_log.second_scan_notes = data.notes

        await db.commit()
        await db.refresh(open_log)

        return {
            "machine_id": machine.id,
            "machine_no": machine.machine_no,
            "current_state": machine.state.value,
            "current_tooling_id": tooling.id,
            "current_tooling_no": tooling.tooling_no,
            "scan_result": "second_scan_registered",
            "message": "请选择操作：维修完成/报废/拆模/继续维修",
            "requires_second_scan": False,
            "pending_log_id": open_log.id,
        }


async def process_scan_action(
    db: AsyncSession,
    log_id: int,
    data: ToolingScanActionRequest,
    operator: User,
) -> dict:
    """Process second scan action selection.

    Actions:
    - repair_complete: Complete repair, return to production
    - discard: Scrap the tooling
    - remove_tooling: Remove from machine without scrapping
    - continue_repair: Continue repair (keep open)
    """
    result = await db.execute(
        select(ToolingMaintenanceLog).where(ToolingMaintenanceLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise ValueError("Maintenance log not found")

    if log.status != "open":
        raise ValueError("Maintenance log is not open")

    # Get tooling
    tooling_result = await db.execute(
        select(Tooling).where(Tooling.id == log.tooling_id)
    )
    tooling = tooling_result.scalar_one_or_none()

    # Get machine
    machine_result = await db.execute(
        select(Machine).where(Machine.id == log.machine_id)
    )
    machine = machine_result.scalar_one_or_none()

    if data.action == "repair_complete":
        # Complete repair
        log.action_taken = "repair_complete"
        log.action_completed_at = datetime.utcnow()
        log.completed_by = operator.id
        log.repair_result = data.notes
        log.status = "completed"

        if tooling:
            tooling.cavity_status = ToolingCavityStatus.OK
            tooling.state = ToolingState.PRODUCTION

        if machine:
            machine.state = MachineState.IDLE

        message = "维修完成，模具已恢复"

    elif data.action == "discard":
        # Scrap tooling
        log.action_taken = "discard"
        log.action_completed_at = datetime.utcnow()
        log.completed_by = operator.id
        log.repair_result = data.notes
        log.status = "completed"

        if tooling:
            tooling.state = ToolingState.SCRAPPED
            tooling.mounted_machine_id = None
            tooling.cavity_status = ToolingCavityStatus.REPAIRING

        if machine:
            machine.current_tooling_id = None
            machine.state = MachineState.IDLE

        message = "模具已报废"

    elif data.action == "remove_tooling":
        # Remove from machine
        log.action_taken = "remove_tooling"
        log.action_completed_at = datetime.utcnow()
        log.completed_by = operator.id
        log.repair_result = data.notes
        log.status = "completed"

        if tooling:
            tooling.mounted_machine_id = None
            tooling.cavity_status = ToolingCavityStatus.REPAIRING

        if machine:
            machine.current_tooling_id = None
            machine.state = MachineState.IDLE

        message = "模具已从机台拆下"

    else:  # continue_repair
        log.action_taken = "continue_repair"
        log.fault_description = data.fault_description or data.notes
        message = "继续维修中"

    # Calculate duration
    if log.first_scan_time and log.action_completed_at:
        duration = (log.action_completed_at - log.first_scan_time).total_seconds() / 60
        log.fault_duration_minutes = int(duration)

    await db.commit()
    await db.refresh(log)

    return {
        "machine_id": machine.id if machine else None,
        "machine_no": machine.machine_no if machine else None,
        "tooling_id": tooling.id if tooling else None,
        "tooling_no": tooling.tooling_no if tooling else None,
        "log_id": log.id,
        "action": log.action_taken,
        "message": message,
        "duration_minutes": log.fault_duration_minutes,
    }


async def get_maintenance_pool(
    db: AsyncSession,
    status: Optional[str] = None,
    tooling_no: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[dict]:
    """Get maintenance pool (待修池) list."""
    query = (
        select(
            ToolingMaintenanceLog,
            Tooling.tooling_no,
            Tooling.name,
            Machine.machine_no,
        )
        .join(Tooling, ToolingMaintenanceLog.tooling_id == Tooling.id)
        .outerjoin(Machine, ToolingMaintenanceLog.machine_id == Machine.id)
        .where(
            ToolingMaintenanceLog.is_deleted == False,
            ToolingMaintenanceLog.status.in_(["open", "in_progress"]) if status == "open" else True,
        )
        .order_by(ToolingMaintenanceLog.first_scan_time.asc())
    )

    if tooling_no:
        query = query.where(Tooling.tooling_no.ilike(f"%{tooling_no}%"))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    now = datetime.utcnow()
    pool_items = []
    for row in rows:
        log = row[0]
        tooling_no_val = row[1]
        tooling_name = row[2]
        machine_no = row[3]

        elapsed = None
        if log.first_scan_time:
            elapsed = int((now - log.first_scan_time).total_seconds() / 60)

        pool_items.append({
            "id": log.id,
            "log_id": log.id,
            "tooling_id": log.tooling_id,
            "tooling_no": tooling_no_val,
            "tooling_name": tooling_name,
            "machine_id": log.machine_id,
            "machine_no": machine_no,
            "maintenance_type": log.maintenance_type,
            "first_scan_time": log.first_scan_time,
            "fault_description": log.fault_description,
            "elapsed_minutes": elapsed,
            "status": log.status,
        })

    return pool_items
