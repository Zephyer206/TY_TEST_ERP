"""Tooling/Mold management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.tooling import Tooling, ToolingState
from app.schemas.tooling import (
    MaintenanceComplete,
    ToolingCreate,
    ToolingDetailResponse,
    ToolingListResponse,
    ToolingResponse,
    ToolingUpdate,
)
from app.services import tooling_service

router = APIRouter(prefix="/toolings", tags=["Tooling"])


def _tooling_to_response(tooling: Tooling) -> ToolingResponse:
    """Convert Tooling to response."""
    return ToolingResponse(
        id=tooling.id,
        tooling_no=tooling.tooling_no,
        name=tooling.name,
        customer_product_no=tooling.customer_product_no,
        cavity_count=tooling.cavity_count,
        tonnage=tooling.tonnage,
        ppap_no=tooling.ppap_no,
        vehicle_model=tooling.vehicle_model,
        spec_data=tooling.spec_data,
        parent_id=tooling.parent_id,
        state=tooling.state,
        drawing_path=tooling.drawing_path,
        sdr_drawing_path=tooling.sdr_drawing_path,
        active_maintenance_id=tooling.active_maintenance_id,
        is_deleted=tooling.is_deleted,
        created_at=tooling.created_at,
        updated_at=tooling.updated_at,
    )


def _tooling_detail_to_response(tooling: Tooling) -> ToolingDetailResponse:
    """Convert Tooling to detail response with parent-child and logs."""
    children = [_tooling_to_response(c) for c in tooling.children] if tooling.children else []
    parent = _tooling_to_response(tooling.parent) if tooling.parent else None

    logs = []
    if tooling.maintenance_logs:
        for log in tooling.maintenance_logs:
            logs.append(
                {
                    "id": log.id,
                    "tooling_id": log.tooling_id,
                    "machine_id": log.machine_id,
                    "fault_time": log.fault_time,
                    "fault_reason": log.fault_reason,
                    "repair_plan": log.repair_plan,
                    "repair_start_time": log.repair_start_time,
                    "repair_end_time": log.repair_end_time,
                    "repair_completed_by": log.repair_completed_by,
                    "is_active": log.is_active,
                    "notes": log.notes,
                    "created_at": log.created_at,
                }
            )

    return ToolingDetailResponse(
        id=tooling.id,
        tooling_no=tooling.tooling_no,
        name=tooling.name,
        customer_product_no=tooling.customer_product_no,
        cavity_count=tooling.cavity_count,
        tonnage=tooling.tonnage,
        ppap_no=tooling.ppap_no,
        vehicle_model=tooling.vehicle_model,
        spec_data=tooling.spec_data,
        parent_id=tooling.parent_id,
        state=tooling.state,
        drawing_path=tooling.drawing_path,
        sdr_drawing_path=tooling.sdr_drawing_path,
        active_maintenance_id=tooling.active_maintenance_id,
        is_deleted=tooling.is_deleted,
        created_at=tooling.created_at,
        updated_at=tooling.updated_at,
        children=children,
        parent=parent,
        maintenance_logs=logs,
    )


@router.post("", response_model=ToolingResponse, status_code=status.HTTP_201_CREATED)
async def create_tooling(
    data: ToolingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingResponse:
    """Create a new tooling/mold record.

    Tooling starts in AVAILABLE state.
    """
    require_role(current_user, min_level=4)

    tooling = await tooling_service.create_tooling(
        db,
        name=data.name,
        customer_product_no=data.customer_product_no,
        cavity_count=data.cavity_count,
        tonnage=data.tonnage,
        ppap_no=data.ppap_no,
        vehicle_model=data.vehicle_model,
        spec_data=data.spec_data,
        parent_id=data.parent_id,
    )
    return _tooling_to_response(tooling)


@router.get("/{tooling_id}", response_model=ToolingDetailResponse)
async def get_tooling(
    tooling_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingDetailResponse:
    """Get tooling details with parent-child relationships and maintenance logs."""
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")
    return _tooling_detail_to_response(tooling)


@router.get("", response_model=list[ToolingListResponse])
async def list_toolings(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[ToolingState] = Query(default=None),
    customer_product_no: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ToolingListResponse]:
    """List toolings with optional filters."""
    toolings = await tooling_service.get_toolings(
        db,
        state=state,
        customer_product_no=customer_product_no,
        skip=skip,
        limit=limit,
    )

    return [
        ToolingListResponse(
            id=t.id,
            tooling_no=t.tooling_no,
            name=t.name,
            customer_product_no=t.customer_product_no,
            state=t.state,
            cavity_count=t.cavity_count,
            tonnage=t.tonnage,
            parent_id=t.parent_id,
            created_at=t.created_at,
        )
        for t in toolings
    ]


@router.patch("/{tooling_id}", response_model=ToolingResponse)
async def update_tooling(
    tooling_id: int,
    data: ToolingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingResponse:
    """Update tooling basic info."""
    require_role(current_user, min_level=4)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    tooling = await tooling_service.update_tooling(
        db,
        tooling,
        name=data.name,
        customer_product_no=data.customer_product_no,
        cavity_count=data.cavity_count,
        tonnage=data.tonnage,
        ppap_no=data.ppap_no,
        vehicle_model=data.vehicle_model,
        spec_data=data.spec_data,
    )
    return _tooling_to_response(tooling)


@router.post("/{tooling_id}/mount/{machine_id}", response_model=ToolingResponse)
async def mount_tooling(
    tooling_id: int,
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingResponse:
    """Mount a tooling to a machine."""
    require_role(current_user, min_level=3)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    from app.models.machine import Machine

    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    try:
        tooling = await tooling_service.mount_tooling(db, tooling, machine)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _tooling_to_response(tooling)


@router.post("/{tooling_id}/unmount", response_model=ToolingResponse)
async def unmount_tooling(
    tooling_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingResponse:
    """Unmount tooling from its current machine."""
    require_role(current_user, min_level=3)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    from app.models.machine import Machine

    result = await db.execute(
        select(Machine).where(Machine.current_tooling_id == tooling_id)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=400, detail="Tooling not mounted on any machine")

    try:
        machine = await tooling_service.unmount_tooling(db, machine)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _tooling_to_response(tooling)


@router.post("/{tooling_id}/complete-maintenance", response_model=ToolingResponse)
async def complete_maintenance(
    tooling_id: int,
    db: DbSession,
    current_user: CurrentUser,
    data: Optional[MaintenanceComplete] = None,
) -> ToolingResponse:
    """Complete tooling maintenance and return to available state."""
    require_role(current_user, min_level=2)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    notes = data.notes if data else None
    try:
        tooling = await tooling_service.complete_maintenance(db, tooling, notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _tooling_to_response(tooling)


@router.get("/maintenance-pool/list", response_model=list[ToolingListResponse])
async def get_maintenance_pool(
    db: DbSession,
    current_user: CurrentUser,
    tooling_no: Optional[str] = Query(default=None),
    customer_product_no: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ToolingListResponse]:
    """Get toolings in maintenance pool (state = MAINTENANCE)."""
    toolings = await tooling_service.get_maintenance_pool(
        db,
        tooling_no=tooling_no,
        customer_product_no=customer_product_no,
        skip=skip,
        limit=limit,
    )

    return [
        ToolingListResponse(
            id=t.id,
            tooling_no=t.tooling_no,
            name=t.name,
            customer_product_no=t.customer_product_no,
            state=t.state,
            cavity_count=t.cavity_count,
            tonnage=t.tonnage,
            parent_id=t.parent_id,
            created_at=t.created_at,
        )
        for t in toolings
    ]
