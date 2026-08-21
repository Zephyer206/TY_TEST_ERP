"""Machine management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.machine import Machine, MachineState
from app.services import tooling_service
from app.services import machine_service

router = APIRouter(prefix="/machines", tags=["Machines"])


class MachineResponse(BaseModel):
    """Schema for machine response."""

    id: int
    machine_no: str
    name: str
    machine_type: Optional[str] = None
    tonnage: Optional[float] = None
    max_stroke: Optional[float] = None
    bed_size: Optional[str] = None
    state: MachineState
    current_tooling_id: Optional[int] = None
    fault_time: Optional[str] = None
    fault_reported_by: Optional[int] = None
    fault_reason: Optional[str] = None
    repair_start_time: Optional[str] = None
    repairer_id: Optional[int] = None
    location: Optional[str] = None
    is_deleted: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


def _machine_to_response(machine: Machine) -> MachineResponse:
    """Convert Machine to response."""
    return MachineResponse(
        id=machine.id,
        machine_no=machine.machine_no,
        name=machine.name,
        machine_type=machine.machine_type,
        tonnage=machine.tonnage,
        max_stroke=machine.max_stroke,
        bed_size=machine.bed_size,
        state=machine.state,
        current_tooling_id=machine.current_tooling_id,
        fault_time=machine.fault_time.isoformat() if machine.fault_time else None,
        fault_reported_by=machine.fault_reported_by,
        fault_reason=machine.fault_reason,
        repair_start_time=machine.repair_start_time.isoformat() if machine.repair_start_time else None,
        repairer_id=machine.repairer_id,
        location=machine.location,
        is_deleted=machine.is_deleted,
        created_at=machine.created_at.isoformat(),
        updated_at=machine.updated_at.isoformat(),
    )


@router.get("/{machine_id}", response_model=MachineResponse)
async def get_machine(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineResponse:
    """Get machine by ID."""
    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    return _machine_to_response(machine)


@router.get("", response_model=list[MachineResponse])
async def list_machines(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[MachineState] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MachineResponse]:
    """List machines with optional state filter."""
    query = select(Machine).where(Machine.is_deleted == False)

    if state:
        query = query.where(Machine.state == state)

    query = query.order_by(Machine.machine_no).offset(skip).limit(limit)

    result = await db.execute(query)
    machines = result.scalars().all()
    return [_machine_to_response(m) for m in machines]


class FaultReportRequest(BaseModel):
    """Schema for reporting a machine fault."""

    reason: Optional[str] = None


@router.post("/{machine_id}/fault", response_model=MachineResponse)
async def report_fault(
    machine_id: int,
    data: FaultReportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineResponse:
    """Report a fault on a machine.

    Machine enters FAULT state, waiting for first scan confirmation.
    Requires LV2 (supervisor/maintenance manager).
    """
    require_role(current_user, min_level=2)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    try:
        machine = await tooling_service.report_fault(
            db, machine, data.reason, current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _machine_to_response(machine)


class FirstScanRequest(BaseModel):
    """Schema for first scan on a faulty machine."""

    fault_reason: Optional[str] = None


@router.post("/{machine_id}/scan", response_model=MachineResponse)
async def machine_scan(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
    scan_type: str = Query(..., description="Scan type: 'first' or 'second'"),
    action: Optional[str] = Query(default=None, description="Action for second scan: 'complete' or 'dismount'"),
    fault_reason: Optional[str] = Query(default=None, description="Fault reason for first scan"),
) -> MachineResponse:
    """Process scan on a machine.

    Two-scan repair process:
    - First scan (scan_type=first): Machine enters PENDING_CHECK state, maintenance log created
    - Second scan (scan_type=second, action=complete): Complete repair, machine returns to IDLE/RUNNING
    - Second scan (scan_type=second, action=dismount): Dismount tooling, machine returns to IDLE
    """
    require_role(current_user, min_level=2)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    try:
        if scan_type == "first":
            if machine.state != MachineState.FAULT:
                raise HTTPException(
                    status_code=400,
                    detail=f"Machine must be in FAULT state for first scan, current: {machine.state.value}"
                )
            machine = await tooling_service.first_scan(db, machine, fault_reason)
        elif scan_type == "second":
            if not action:
                raise HTTPException(status_code=400, detail="Action required for second scan: 'complete' or 'dismount'")
            machine = await tooling_service.second_scan(db, machine, action, current_user)
        else:
            raise HTTPException(status_code=400, detail="Invalid scan_type. Must be 'first' or 'second'")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _machine_to_response(machine)


@router.post("/{machine_id}/repair/complete", response_model=MachineResponse)
async def complete_repair(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineResponse:
    """Complete machine repair (alternative endpoint for completing without scan)."""
    require_role(current_user, min_level=2)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if machine.state != MachineState.PENDING_CHECK:
        raise HTTPException(
            status_code=400,
            detail=f"Machine must be in PENDING_CHECK state, current: {machine.state.value}"
        )

    try:
        machine = await tooling_service.second_scan(db, machine, "complete", current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _machine_to_response(machine)


@router.post("/{machine_id}/repair/dismount", response_model=MachineResponse)
async def dismount_and_repair(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineResponse:
    """Dismount tooling and enter repair mode."""
    require_role(current_user, min_level=2)

    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if machine.state != MachineState.PENDING_CHECK:
        raise HTTPException(
            status_code=400,
            detail=f"Machine must be in PENDING_CHECK state, current: {machine.state.value}"
        )

    try:
        machine = await tooling_service.second_scan(db, machine, "dismount", current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _machine_to_response(machine)


# ── US3: Machine QR Code ─────────────────────────────────────────────────────

class MachineQRResponse(BaseModel):
    """Schema for machine QR code generation response."""

    machine_id: int
    machine_no: str
    name: str
    machine_type: Optional[str] = None
    tonnage: Optional[float] = None
    location: Optional[str] = None
    state: str
    qr_content: str
    qr_image_base64: str

    class Config:
        from_attributes = True


class MachineScanResponse(BaseModel):
    """Schema for machine scan response."""

    machine_id: int
    machine_no: str
    name: str
    machine_type: Optional[str] = None
    tonnage: Optional[float] = None
    max_stroke: Optional[float] = None
    bed_size: Optional[str] = None
    state: str
    location: Optional[str] = None
    current_tooling_id: Optional[int] = None
    fault_time: Optional[str] = None
    fault_reason: Optional[str] = None
    repair_start_time: Optional[str] = None
    repairer_id: Optional[int] = None
    qr_content: str
    qr_image_base64: str
    scan_history: list

    class Config:
        from_attributes = True


@router.post("/{machine_id}/generate-qr", response_model=MachineQRResponse)
async def generate_machine_qr(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineQRResponse:
    """Generate QR code for a machine.

    Returns the machine info plus qr_content and qr_image_base64 for label printing.
    """
    try:
        result = await machine_service.generate_machine_qr(db, machine_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return MachineQRResponse(**result)


@router.get("/scan/{machine_id}", response_model=MachineScanResponse)
async def scan_machine(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MachineScanResponse:
    """Scan machine QR code to get full status and scan history.

    Records the scan event in qr_scan_logs. Returns machine info,
    qr_content, qr_image_base64, and recent scan history.
    """
    try:
        result = await machine_service.get_machine_scan_result(
            db, machine_id, operator_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    machine = result["machine"]

    scan_history = []
    for log in result["scan_history"]:
        scan_history.append({
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        })

    return MachineScanResponse(
        machine_id=machine.id,
        machine_no=machine.machine_no,
        name=machine.name,
        machine_type=machine.machine_type,
        tonnage=machine.tonnage,
        max_stroke=machine.max_stroke,
        bed_size=machine.bed_size,
        state=machine.state.value if machine.state else None,
        location=machine.location,
        current_tooling_id=machine.current_tooling_id,
        fault_time=machine.fault_time.isoformat() if machine.fault_time else None,
        fault_reason=machine.fault_reason,
        repair_start_time=machine.repair_start_time.isoformat() if machine.repair_start_time else None,
        repairer_id=machine.repairer_id,
        qr_content=result["qr_content"],
        qr_image_base64=result["qr_image_base64"],
        scan_history=scan_history,
    )
