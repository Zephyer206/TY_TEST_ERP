"""Sampling task API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.sampling import SamplingTask, SamplingTaskState
from app.schemas.sampling import (
    SamplingKanbanResponse,
    SamplingTaskApprove,
    SamplingTaskCancel,
    SamplingTaskCreate,
    SamplingTaskListResponse,
    SamplingTaskResponse,
    SamplingTaskReview,
    SamplingTaskUpdate,
)
from app.services import sampling_service

router = APIRouter(prefix="/sampling-tasks", tags=["Sampling Tasks"])


def _task_to_response(task: SamplingTask) -> SamplingTaskResponse:
    """Convert SamplingTask to response."""
    return SamplingTaskResponse(
        id=task.id,
        task_no=task.task_no,
        part_id=task.part_id,
        customer_id=task.customer_id,
        quote_id=task.quote_id,
        sample_qty=task.sample_qty,
        order_date=task.order_date,
        planned_completion_date=task.planned_completion_date,
        state=task.state,
        actual_completion_date=task.actual_completion_date,
        start_date=task.start_date,
        is_urgent=task.is_urgent,
        review_notes=task.review_notes,
        reviewer_id=task.reviewer_id,
        reviewer_name=task.reviewer.full_name if task.reviewer else None,
        cancel_reason=task.cancel_reason,
        approved_by=task.approved_by,
        approver_name=task.approver.full_name if task.approver else None,
        approved_at=task.approved_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", response_model=SamplingTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_sampling_task(
    data: SamplingTaskCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Create a new sampling task.

    Task starts in PENDING_APPROVAL state.
    """
    require_role(current_user, min_level=5)

    from app.models.part import Part, PartState

    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    task = await sampling_service.create_sampling_task(
        db,
        part_id=data.part_id,
        customer_id=data.customer_id,
        sample_qty=data.sample_qty,
        order_date=data.order_date,
        planned_completion_date=data.planned_completion_date,
        quote_id=data.quote_id,
    )
    return _task_to_response(task)


@router.get("/{task_id}", response_model=SamplingTaskResponse)
async def get_sampling_task(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Get sampling task by ID."""
    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")
    return _task_to_response(task)


@router.get("", response_model=list[SamplingTaskListResponse])
async def list_sampling_tasks(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[SamplingTaskState] = Query(default=None),
    part_id: Optional[int] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    is_urgent: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SamplingTaskListResponse]:
    """List sampling tasks with optional filters."""
    tasks = await sampling_service.get_sampling_tasks(
        db,
        state=state,
        part_id=part_id,
        customer_id=customer_id,
        is_urgent=is_urgent,
        skip=skip,
        limit=limit,
    )

    return [
        SamplingTaskListResponse(
            id=t.id,
            task_no=t.task_no,
            part_id=t.part_id,
            part_no=t.part.part_no if t.part else None,
            part_name=t.part.part_name if t.part else None,
            customer_id=t.customer_id,
            customer_name=t.customer.name if t.customer else None,
            state=t.state,
            sample_qty=t.sample_qty,
            order_date=t.order_date,
            planned_completion_date=t.planned_completion_date,
            actual_completion_date=t.actual_completion_date,
            is_urgent=t.is_urgent,
            created_at=t.created_at,
        )
        for t in tasks
    ]


@router.patch("/{task_id}", response_model=SamplingTaskResponse)
async def update_sampling_task(
    task_id: int,
    data: SamplingTaskUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Update sampling task fields."""
    require_role(current_user, min_level=5)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if hasattr(task, field):
            setattr(task, field, value)

    await db.commit()
    await db.refresh(task)
    return _task_to_response(task)


@router.post("/{task_id}/boss-approve", response_model=SamplingTaskResponse)
async def boss_approve_task(
    task_id: int,
    data: SamplingTaskApprove,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Boss approval of sampling task (role_level >= 9)."""
    require_role(current_user, min_level=9)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    try:
        task = await sampling_service.boss_approve(
            db, task, data.approved, current_user, data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _task_to_response(task)


@router.post("/{task_id}/start", response_model=SamplingTaskResponse)
async def start_production(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Start sampling production (after boss approval)."""
    require_role(current_user, min_level=3)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    try:
        task = await sampling_service.start_production(db, task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _task_to_response(task)


@router.post("/{task_id}/complete", response_model=SamplingTaskResponse)
async def complete_production(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Mark sampling production as complete, ready for review."""
    require_role(current_user, min_level=3)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    try:
        task = await sampling_service.complete_production(db, task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _task_to_response(task)


@router.post("/{task_id}/review", response_model=SamplingTaskResponse)
async def submit_review(
    task_id: int,
    data: SamplingTaskReview,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Submit review result (passed/failed).

    On pass: part transitions from SAMPLING to MASSPRODUCTION.
    """
    require_role(current_user, min_level=4)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    try:
        task = await sampling_service.submit_review(
            db, task, data.passed, current_user, data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _task_to_response(task)


@router.post("/{task_id}/urgent", response_model=SamplingTaskResponse)
async def toggle_urgent(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Toggle urgent flag on a sampling task."""
    require_role(current_user, min_level=5)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    task = await sampling_service.mark_urgent(db, task, not task.is_urgent)
    return _task_to_response(task)


@router.post("/{task_id}/cancel", response_model=SamplingTaskResponse)
async def cancel_task(
    task_id: int,
    data: SamplingTaskCancel,
    db: DbSession,
    current_user: CurrentUser,
) -> SamplingTaskResponse:
    """Cancel a sampling task."""
    require_role(current_user, min_level=5)

    task = await sampling_service.get_sampling_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Sampling task not found")

    try:
        task = await sampling_service.cancel_task(db, task, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _task_to_response(task)


@router.get("/kanban/sampling", response_model=list[SamplingKanbanResponse])
async def get_sampling_kanban(
    db: DbSession,
    current_user: CurrentUser,
    part_no: Optional[str] = Query(default=None),
    customer_name: Optional[str] = Query(default=None),
    state: Optional[SamplingTaskState] = Query(default=None),
    planned_before: Optional[datetime] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[SamplingKanbanResponse]:
    """Get sampling kanban data for tracking.

    Shows all parts in sampling phase with overdue detection.
    """
    tasks = await sampling_service.get_sampling_kanban(
        db,
        part_no=part_no,
        customer_name=customer_name,
        state=state,
        planned_before=planned_before,
        skip=skip,
        limit=limit,
    )

    now = datetime.utcnow()
    return [
        SamplingKanbanResponse(
            id=t.id,
            task_no=t.task_no,
            part_id=t.part_id,
            part_no=t.part.part_no if t.part else None,
            part_name=t.part.part_name if t.part else None,
            customer_id=t.customer_id,
            customer_name=t.customer.name if t.customer else None,
            state=t.state,
            sample_qty=t.sample_qty,
            order_date=t.order_date,
            planned_completion_date=t.planned_completion_date,
            is_urgent=t.is_urgent,
            is_overdue=t.planned_completion_date < now,
            created_at=t.created_at,
        )
        for t in tasks
    ]
