"""Machine API endpoints including scan operations."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.machine import Machine, MachineState
from app.schemas.tooling import MachineScanResponse, ToolingScanActionRequest, ToolingScanRequest
from app.services import tooling_service

router = APIRouter(prefix="/machines", tags=["Machines"])


@router.get("", response_model=list[dict])
async def list_machines(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[MachineState] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    """List all machines with optional state filter."""
    query = select(Machine).where(Machine.is_deleted == False)

    if state:
        query = query.where(Machine.state == state)

    query = query.order_by(Machine.machine_no).offset(skip).limit(limit)
    result = await db.execute(query)
    machines = result.scalars().all()

    return [
        {
            "id": m.id,
            "machine_no": m.machine_no,
            "name": m.name,
            "machine_type": m.machine_type,
            "tonnage": m.tonnage,
            "state": m.state.value if m.state else None,
            "current_tooling_id": m.current_tooling_id,
            "location": m.location,
            "created_at": m.created_at,
        }
        for m in machines
    ]


@router.get("/{machine_id}", response_model=dict)
async def get_machine(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get machine details."""
    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    return {
        "id": machine.id,
        "machine_no": machine.machine_no,
        "name": machine.name,
        "machine_type": machine.machine_type,
        "tonnage": machine.tonnage,
        "max_stroke": machine.max_stroke,
        "bed_size": machine.bed_size,
        "state": machine.state.value if machine.state else None,
        "current_tooling_id": machine.current_tooling_id,
        "fault_time": machine.fault_time,
        "fault_reported_by": machine.fault_reported_by,
        "fault_reason": machine.fault_reason,
        "repair_start_time": machine.repair_start_time,
        "repairer_id": machine.repairer_id,
        "location": machine.location,
        "created_at": machine.created_at,
        "updated_at": machine.updated_at,
    }


@router.patch("/{machine_id}", response_model=dict)
async def update_machine(
    machine_id: int,
    data: dict,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Update machine fields."""
    require_role(current_user, min_level=4)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    # Only allow updating certain fields
    allowed_fields = ["name", "machine_type", "tonnage", "max_stroke", "bed_size", "location"]
    for field in allowed_fields:
        if field in data and data[field] is not None:
            setattr(machine, field, data[field])

    await db.commit()
    await db.refresh(machine)

    return {
        "id": machine.id,
        "machine_no": machine.machine_no,
        "name": machine.name,
        "machine_type": machine.machine_type,
        "tonnage": machine.tonnage,
        "state": machine.state.value if machine.state else None,
        "current_tooling_id": machine.current_tooling_id,
        "location": machine.location,
    }


@router.post("/{machine_id}/scan", response_model=MachineScanResponse)
async def process_machine_scan(
    machine_id: int,
    data: ToolingScanRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineScanResponse:
    """Process scan on machine for two-scan maintenance workflow.

    First scan: Reports fault, creates maintenance log
    Second scan: Shows action options
    """
    require_role(current_user, min_level=2)  # At least tech engineer

    # Get machine
    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    try:
        result = await tooling_service.process_machine_scan(db, data, current_user)
        return MachineScanResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scan/action", response_model=dict)
async def process_scan_action(
    log_id: int,
    data: ToolingScanActionRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Process second scan action selection.

    Actions:
    - repair_complete: Complete repair, return to production
    - discard: Scrap the tooling
    - remove_tooling: Remove from machine without scrapping
    - continue_repair: Continue repair (keep open)
    """
    require_role(current_user, min_level=2)  # At least tech engineer

    try:
        result = await tooling_service.process_scan_action(db, log_id, data, current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{machine_id}/report-fault", response_model=dict)
async def report_fault(
    machine_id: int,
    reason: str,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Report a fault on a machine."""
    require_role(current_user, min_level=3)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    machine.state = MachineState.FAULT
    machine.fault_time = datetime.utcnow()
    machine.fault_reported_by = current_user.get("id")
    machine.fault_reason = reason

    await db.commit()
    await db.refresh(machine)

    return {
        "machine_id": machine.id,
        "machine_no": machine.machine_no,
        "state": machine.state.value,
        "fault_time": machine.fault_time,
        "message": "故障已登记，等待扫码维修",
    }


@router.post("/{machine_id}/clear-fault", response_model=dict)
async def clear_fault(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Clear fault and return machine to idle."""
    require_role(current_user, min_level=3)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    machine.state = MachineState.IDLE
    machine.fault_time = None
    machine.fault_reported_by = None
    machine.fault_reason = None

    await db.commit()
    await db.refresh(machine)

    return {
        "machine_id": machine.id,
        "machine_no": machine.machine_no,
        "state": machine.state.value,
        "message": "故障已清除，机台恢复空闲",
    }
