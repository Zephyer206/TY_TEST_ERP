"""Tooling/Mold API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.tooling import Tooling, ToolingCavityStatus, ToolingState
from app.schemas.tooling import (
    MaintenancePoolResponse,
    ToolingCreate,
    ToolingDetailResponse,
    ToolingListResponse,
    ToolingMountUpdate,
    ToolingPartCreate,
    ToolingPartResponse,
    ToolingResponse,
    ToolingScanActionRequest,
    ToolingScanRequest,
    ToolingUpdate,
)
from app.services import tooling_service

router = APIRouter(prefix="/toolings", tags=["Toolings"])


def _tooling_to_response(tooling: Tooling, include_children: bool = False) -> ToolingResponse:
    """Convert Tooling model to response."""
    children_data = []
    if include_children and tooling.children:
        children_data = [
            {
                "id": c.id,
                "tooling_no": c.tooling_no,
                "name": c.name,
                "tooling_type": c.tooling_type,
                "cavity_count": c.cavity_count,
                "state": c.state,
            }
            for c in tooling.children
        ]

    return ToolingResponse(
        id=tooling.id,
        tooling_no=tooling.tooling_no,
        name=tooling.name,
        tooling_type=tooling.tooling_type,
        customer_id=tooling.customer_id,
        customer_name=tooling.customer.name if tooling.customer else None,
        parent_id=tooling.parent_id,
        parent_no=tooling.parent.tooling_no if tooling.parent else None,
        cavity_count=tooling.cavity_count,
        press_tonnage=tooling.press_tonnage,
        spec_twph=tooling.spec_twph,
        ppap_no=tooling.ppap_no,
        vehicle_model=tooling.vehicle_model,
        state=tooling.state,
        cavity_status=tooling.cavity_status,
        mounted_machine_id=tooling.mounted_machine_id,
        mounted_machine_no=tooling.mounted_machine.machine_no if tooling.mounted_machine else None,
        designed_by=tooling.designed_by,
        trial_completed_at=tooling.trial_completed_at,
        production_started_at=tooling.production_started_at,
        drawing_path=tooling.drawing_path,
        notes=tooling.notes,
        children=children_data,
        created_at=tooling.created_at,
        updated_at=tooling.updated_at,
    )


@router.post("", response_model=ToolingResponse, status_code=status.HTTP_201_CREATED)
async def create_tooling(
    data: ToolingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingResponse:
    """Create a new tooling record (requires role_level >= 4)."""
    require_role(current_user, min_level=4)

    tooling = await tooling_service.create_tooling(db, data, current_user)
    return _tooling_to_response(tooling)


@router.get("/{tooling_id}", response_model=ToolingDetailResponse)
async def get_tooling(
    tooling_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingDetailResponse:
    """Get tooling detail with parts and maintenance logs."""
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id, include_details=True)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    # Get parts
    parts_result = await tooling_service.get_tooling_parts(db, tooling_id)
    parts_data = []
    for p in parts_result:
        parts_data.append(ToolingPartResponse(
            id=p.id,
            tooling_id=p.tooling_id,
            part_id=p.part_id,
            part_no=p.part.part_no if p.part else None,
            part_name=p.part.part_name if p.part else None,
            is_primary=p.is_primary,
            cavity_index=p.cavity_index,
            notes=p.notes,
            created_at=p.created_at,
        ))

    # Get maintenance logs
    logs = await tooling_service.get_maintenance_logs(db, tooling_id)

    return ToolingDetailResponse(
        **ToolingResponse(
            id=tooling.id,
            tooling_no=tooling.tooling_no,
            name=tooling.name,
            tooling_type=tooling.tooling_type,
            customer_id=tooling.customer_id,
            customer_name=tooling.customer.name if tooling.customer else None,
            parent_id=tooling.parent_id,
            parent_no=tooling.parent.tooling_no if tooling.parent else None,
            cavity_count=tooling.cavity_count,
            press_tonnage=tooling.press_tonnage,
            spec_twph=tooling.spec_twph,
            ppap_no=tooling.ppap_no,
            vehicle_model=tooling.vehicle_model,
            state=tooling.state,
            cavity_status=tooling.cavity_status,
            mounted_machine_id=tooling.mounted_machine_id,
            mounted_machine_no=tooling.mounted_machine.machine_no if tooling.mounted_machine else None,
            designed_by=tooling.designed_by,
            trial_completed_at=tooling.trial_completed_at,
            production_started_at=tooling.production_started_at,
            drawing_path=tooling.drawing_path,
            notes=tooling.notes,
            children=[],
            created_at=tooling.created_at,
            updated_at=tooling.updated_at,
        ).model_dump(),
        parts=parts_data,
        maintenance_logs=[
            {
                "id": log.id,
                "tooling_id": log.tooling_id,
                "machine_id": log.machine_id,
                "maintenance_type": log.maintenance_type,
                "first_scan_time": log.first_scan_time,
                "first_scan_by": log.first_scan_by,
                "first_scan_notes": log.first_scan_notes,
                "second_scan_time": log.second_scan_time,
                "second_scan_by": log.second_scan_by,
                "second_scan_notes": log.second_scan_notes,
                "action_taken": log.action_taken,
                "action_completed_at": log.action_completed_at,
                "completed_by": log.completed_by,
                "fault_description": log.fault_description,
                "repair_result": log.repair_result,
                "fault_duration_minutes": log.fault_duration_minutes,
                "status": log.status,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    )


@router.get("", response_model=list[ToolingListResponse])
async def list_toolings(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[ToolingState] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    cavity_status: Optional[ToolingCavityStatus] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ToolingListResponse]:
    """List toolings with optional filters."""
    toolings = await tooling_service.get_toolings(
        db,
        state=state,
        customer_id=customer_id,
        machine_id=machine_id,
        cavity_status=cavity_status,
        skip=skip,
        limit=limit,
    )

    return [
        ToolingListResponse(
            id=t.id,
            tooling_no=t.tooling_no,
            name=t.name,
            tooling_type=t.tooling_type,
            customer_name=t.customer.name if t.customer else None,
            cavity_count=t.cavity_count,
            press_tonnage=t.press_tonnage,
            state=t.state,
            cavity_status=t.cavity_status,
            mounted_machine_id=t.mounted_machine_id,
            mounted_machine_no=t.mounted_machine.machine_no if t.mounted_machine else None,
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
    """Update tooling fields."""
    require_role(current_user, min_level=4)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    tooling = await tooling_service.update_tooling(db, tooling, data)
    return _tooling_to_response(tooling, include_children=True)


@router.post("/{tooling_id}/mount", response_model=ToolingResponse)
async def mount_tooling(
    tooling_id: int,
    data: ToolingMountUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingResponse:
    """Mount or unmount tooling to/from machine."""
    require_role(current_user, min_level=3)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    try:
        tooling = await tooling_service.mount_tooling(db, tooling, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _tooling_to_response(tooling)


@router.post("/{tooling_id}/parts", response_model=ToolingPartResponse, status_code=status.HTTP_201_CREATED)
async def associate_part(
    tooling_id: int,
    data: ToolingPartCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolingPartResponse:
    """Associate a part with a tooling."""
    require_role(current_user, min_level=4)

    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")

    part = await tooling_service.associate_part(db, tooling_id, data)
    return ToolingPartResponse(
        id=part.id,
        tooling_id=part.tooling_id,
        part_id=part.part_id,
        part_no=None,  # Would need to fetch
        part_name=None,
        is_primary=part.is_primary,
        cavity_index=part.cavity_index,
        notes=part.notes,
        created_at=part.created_at,
    )


@router.get("/maintenance-pool", response_model=list[MaintenancePoolResponse])
async def get_maintenance_pool(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[str] = Query(default=None),
    tooling_no: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[MaintenancePoolResponse]:
    """Get maintenance pool (待修池) list."""
    pool = await tooling_service.get_maintenance_pool(
        db,
        status=status,
        tooling_no=tooling_no,
        skip=skip,
        limit=limit,
    )

    return [
        MaintenancePoolResponse(
            id=item["id"],
            log_id=item["log_id"],
            tooling_id=item["tooling_id"],
            tooling_no=item["tooling_no"],
            tooling_name=item["tooling_name"],
            machine_id=item["machine_id"],
            machine_no=item["machine_no"],
            maintenance_type=item["maintenance_type"],
            first_scan_time=item["first_scan_time"],
            fault_description=item["fault_description"],
            elapsed_minutes=item["elapsed_minutes"],
            status=item["status"],
        )
        for item in pool
    ]
