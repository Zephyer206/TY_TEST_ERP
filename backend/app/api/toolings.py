"""Tooling management API using canonical tooling fields only."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.machine import Machine
from app.models.tooling import Tooling
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


def _to_response(tooling: Tooling) -> ToolingResponse:
    return ToolingResponse.model_validate(tooling, from_attributes=True)


def _to_list_response(tooling: Tooling) -> ToolingListResponse:
    return ToolingListResponse.model_validate(tooling, from_attributes=True)


@router.post("", response_model=ToolingResponse, status_code=status.HTTP_201_CREATED)
async def create_tooling(data: ToolingCreate, db: DbSession, current_user: CurrentUser) -> ToolingResponse:
    require_role(current_user, min_level=2)
    tooling = await tooling_service.create_tooling(db, **data.model_dump())
    return _to_response(tooling)


@router.get("", response_model=list[ToolingListResponse])
async def list_toolings(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    tooling_number: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ToolingListResponse]:
    toolings = await tooling_service.get_toolings(
        db, status=status_filter, tooling_number=tooling_number, skip=skip, limit=limit
    )
    return [_to_list_response(item) for item in toolings]


@router.get("/{tooling_id}", response_model=ToolingDetailResponse)
async def get_tooling(tooling_id: int, db: DbSession, current_user: CurrentUser) -> ToolingDetailResponse:
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")
    return ToolingDetailResponse.model_validate(tooling, from_attributes=True)


@router.patch("/{tooling_id}", response_model=ToolingResponse)
async def update_tooling(tooling_id: int, data: ToolingUpdate, db: DbSession, current_user: CurrentUser) -> ToolingResponse:
    require_role(current_user, min_level=2)
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")
    tooling = await tooling_service.update_tooling(db, tooling, **data.model_dump(exclude_unset=True))
    return _to_response(tooling)


@router.post("/{tooling_id}/mount/{machine_id}", response_model=ToolingResponse)
async def mount_tooling(tooling_id: int, machine_id: int, db: DbSession, current_user: CurrentUser) -> ToolingResponse:
    require_role(current_user, min_level=2)
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    machine = await db.get(Machine, machine_id)
    if not tooling or tooling.is_deleted:
        raise HTTPException(status_code=404, detail="Tooling not found")
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    try:
        await tooling_service.mount_tooling(db, tooling, machine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(tooling)


@router.post("/{tooling_id}/unmount", response_model=ToolingResponse)
async def unmount_tooling(tooling_id: int, db: DbSession, current_user: CurrentUser) -> ToolingResponse:
    require_role(current_user, min_level=2)
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")
    result = await db.execute(select(Machine).where(Machine.current_tooling_id == tooling_id))
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=400, detail="Tooling not mounted on any machine")
    try:
        await tooling_service.unmount_tooling(db, machine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(tooling)


@router.post("/{tooling_id}/complete-maintenance", response_model=ToolingResponse)
async def complete_maintenance(
    tooling_id: int,
    db: DbSession,
    current_user: CurrentUser,
    data: Optional[MaintenanceComplete] = None,
) -> ToolingResponse:
    require_role(current_user, min_level=2)
    tooling = await tooling_service.get_tooling_by_id(db, tooling_id)
    if not tooling:
        raise HTTPException(status_code=404, detail="Tooling not found")
    try:
        await tooling_service.complete_maintenance(db, tooling, data.notes if data else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(tooling)


@router.get("/maintenance-pool/list", response_model=list[ToolingListResponse])
async def get_maintenance_pool(
    db: DbSession,
    current_user: CurrentUser,
    tooling_number: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ToolingListResponse]:
    toolings = await tooling_service.get_maintenance_pool(
        db, tooling_number=tooling_number, skip=skip, limit=limit
    )
    return [_to_list_response(item) for item in toolings]
