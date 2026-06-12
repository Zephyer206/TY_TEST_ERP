"""Business logic for sampling task management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.part import Part, PartState
from app.models.sampling import SamplingTask, SamplingTaskState
from app.models.user import User


def generate_task_no(db: AsyncSession) -> str:
    """Generate a unique task number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"ST-{prefix}-{now.strftime('%H%M%S')}"


async def create_sampling_task(
    db: AsyncSession,
    part_id: int,
    customer_id: int,
    sample_qty: int,
    order_date: datetime,
    planned_completion_date: datetime,
    quote_id: Optional[int] = None,
) -> SamplingTask:
    """Create a new sampling task.

    Task starts in PENDING_APPROVAL state, waiting for boss confirmation.
    """
    task_no = generate_task_no(db)

    task = SamplingTask(
        task_no=task_no,
        part_id=part_id,
        customer_id=customer_id,
        quote_id=quote_id,
        sample_qty=sample_qty,
        order_date=order_date,
        planned_completion_date=planned_completion_date,
        state=SamplingTaskState.PENDING_APPROVAL,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_sampling_task_by_id(
    db: AsyncSession,
    task_id: int,
) -> Optional[SamplingTask]:
    """Get a sampling task by ID."""
    result = await db.execute(
        select(SamplingTask)
        .options(
            selectinload(SamplingTask.part),
            selectinload(SamplingTask.reviewer),
            selectinload(SamplingTask.approver),
        )
        .where(SamplingTask.id == task_id, SamplingTask.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_sampling_tasks(
    db: AsyncSession,
    state: Optional[SamplingTaskState] = None,
    part_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    is_urgent: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[SamplingTask]:
    """Get sampling tasks with optional filters."""
    query = (
        select(SamplingTask)
        .options(
            selectinload(SamplingTask.part),
            selectinload(SamplingTask.reviewer),
            selectinload(SamplingTask.approver),
        )
        .where(SamplingTask.is_deleted == False)
    )

    if state:
        query = query.where(SamplingTask.state == state)
    if part_id:
        query = query.where(SamplingTask.part_id == part_id)
    if customer_id:
        query = query.where(SamplingTask.customer_id == customer_id)
    if is_urgent is not None:
        query = query.where(SamplingTask.is_urgent == is_urgent)

    query = query.order_by(
        SamplingTask.is_urgent.desc(),
        SamplingTask.planned_completion_date.asc(),
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def get_sampling_kanban(
    db: AsyncSession,
    part_no: Optional[str] = None,
    customer_name: Optional[str] = None,
    state: Optional[SamplingTaskState] = None,
    planned_before: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[SamplingTask]:
    """Get sampling kanban data with filters.

    Shows all parts in SAMPLING state for tracking.
    """
    from app.models.part import Part

    query = (
        select(SamplingTask)
        .options(
            selectinload(SamplingTask.part),
            selectinload(SamplingTask.reviewer),
            selectinload(SamplingTask.approver),
        )
        .join(Part, SamplingTask.part_id == Part.id)
        .where(SamplingTask.is_deleted == False)
    )

    if state:
        query = query.where(SamplingTask.state == state)
    if part_no:
        query = query.where(Part.part_no.ilike(f"%{part_no}%"))
    if customer_name:
        query = query.where(SamplingTask.customer_id == customer_id)
    if planned_before:
        query = query.where(SamplingTask.planned_completion_date <= planned_before)

    query = query.order_by(
        SamplingTask.is_urgent.desc(),
        SamplingTask.planned_completion_date.asc(),
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def boss_approve(
    db: AsyncSession,
    task: SamplingTask,
    approved: bool,
    approver: User,
    notes: Optional[str] = None,
) -> SamplingTask:
    """Boss approval of sampling task.

    On approval: task moves to APPROVED, ready for production.
    On rejection: task is cancelled.
    """
    if task.state != SamplingTaskState.PENDING_APPROVAL:
        raise ValueError(f"Task not pending approval: {task.state.value}")

    if approved:
        task.state = SamplingTaskState.APPROVED
        task.approved_by = approver.id
        task.approved_at = datetime.utcnow()
    else:
        task.state = SamplingTaskState.CANCELLED
        task.cancel_reason = notes or "Rejected by boss"

    await db.commit()
    await db.refresh(task)
    return task


async def start_production(
    db: AsyncSession,
    task: SamplingTask,
) -> SamplingTask:
    """Start sampling production."""
    if task.state != SamplingTaskState.APPROVED:
        raise ValueError(f"Task not approved: {task.state.value}")

    task.state = SamplingTaskState.IN_PRODUCTION
    task.start_date = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


async def complete_production(
    db: AsyncSession,
    task: SamplingTask,
) -> SamplingTask:
    """Complete sampling production and move to review."""
    if task.state != SamplingTaskState.IN_PRODUCTION:
        raise ValueError(f"Task not in production: {task.state.value}")

    task.state = SamplingTaskState.PENDING_REVIEW
    task.actual_completion_date = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


async def submit_review(
    db: AsyncSession,
    task: SamplingTask,
    passed: bool,
    reviewer: User,
    notes: Optional[str] = None,
) -> SamplingTask:
    """Submit review result for sampling task.

    On pass: task moves to PASSED, part transitions to MassProduction.
    On fail: task moves to FAILED, part stays in SAMPLING state.
    """
    if task.state != SamplingTaskState.PENDING_REVIEW:
        raise ValueError(f"Task not pending review: {task.state.value}")

    task.review_notes = notes
    task.reviewer_id = reviewer.id

    if passed:
        task.state = SamplingTaskState.PASSED
        if task.part:
            task.part.state = PartState.MASSPRODUCTION
    else:
        task.state = SamplingTaskState.FAILED

    await db.commit()
    await db.refresh(task)
    return task


async def mark_urgent(
    db: AsyncSession,
    task: SamplingTask,
    is_urgent: bool,
) -> SamplingTask:
    """Toggle urgent flag on a sampling task."""
    task.is_urgent = is_urgent
    await db.commit()
    await db.refresh(task)
    return task


async def cancel_task(
    db: AsyncSession,
    task: SamplingTask,
    reason: str,
) -> SamplingTask:
    """Cancel a sampling task."""
    if task.state in (SamplingTaskState.PASSED, SamplingTaskState.CANCELLED):
        raise ValueError(f"Cannot cancel task in state: {task.state.value}")

    task.state = SamplingTaskState.CANCELLED
    task.cancel_reason = reason
    await db.commit()
    await db.refresh(task)
    return task
