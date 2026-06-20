"""Business logic for process flow card generation."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.machine import Machine
from app.models.part import Part
from app.models.production import ProcessFlowCard
from app.models.user import User


async def get_process_flow_by_no(
    db: AsyncSession,
    card_no: str,
) -> Optional[ProcessFlowCard]:
    """Get process flow card by card number."""
    result = await db.execute(
        select(ProcessFlowCard)
        .options(
            selectinload(ProcessFlowCard.part),
            selectinload(ProcessFlowCard.machine),
            selectinload(ProcessFlowCard.session),
        )
        .where(ProcessFlowCard.card_no == card_no, ProcessFlowCard.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_process_flow_by_id(
    db: AsyncSession,
    card_id: int,
) -> Optional[ProcessFlowCard]:
    """Get process flow card by ID."""
    result = await db.execute(
        select(ProcessFlowCard)
        .options(
            selectinload(ProcessFlowCard.part),
            selectinload(ProcessFlowCard.machine),
            selectinload(ProcessFlowCard.session),
        )
        .where(ProcessFlowCard.id == card_id, ProcessFlowCard.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_process_flows(
    db: AsyncSession,
    part_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[ProcessFlowCard]:
    """Get process flow cards with filters."""
    query = (
        select(ProcessFlowCard)
        .options(
            selectinload(ProcessFlowCard.part),
            selectinload(ProcessFlowCard.machine),
        )
        .where(ProcessFlowCard.is_deleted == False)
    )

    if part_id:
        query = query.where(ProcessFlowCard.part_id == part_id)
    if machine_id:
        query = query.where(ProcessFlowCard.machine_id == machine_id)
    if status:
        query = query.where(ProcessFlowCard.status == status)
    if start_date:
        query = query.where(ProcessFlowCard.created_at >= start_date)
    if end_date:
        query = query.where(ProcessFlowCard.created_at <= end_date)

    query = query.order_by(ProcessFlowCard.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_process_flow_status(
    db: AsyncSession,
    card: ProcessFlowCard,
    new_status: str,
    updater: User,
) -> ProcessFlowCard:
    """Update process flow card status."""
    card.status = new_status
    await db.commit()
    await db.refresh(card)
    return card


async def get_process_flow_summary(
    db: AsyncSession,
    part_id: int,
    days: int = 30,
) -> dict:
    """Get summary statistics for process flow cards."""
    from datetime import timedelta
    from sqlalchemy import func

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get total counts
    total_result = await db.execute(
        select(func.count(ProcessFlowCard.id))
        .where(
            ProcessFlowCard.part_id == part_id,
            ProcessFlowCard.created_at >= start_date,
        )
    )
    total_count = total_result.scalar() or 0

    # Get total output
    output_result = await db.execute(
        select(func.sum(ProcessFlowCard.total_output))
        .where(
            ProcessFlowCard.part_id == part_id,
            ProcessFlowCard.created_at >= start_date,
        )
    )
    total_output = output_result.scalar() or 0

    # Get total good quantity
    good_result = await db.execute(
        select(func.sum(ProcessFlowCard.good_qty))
        .where(
            ProcessFlowCard.part_id == part_id,
            ProcessFlowCard.created_at >= start_date,
        )
    )
    total_good = good_result.scalar() or 0

    # Get total duration
    duration_result = await db.execute(
        select(func.sum(ProcessFlowCard.duration_minutes))
        .where(
            ProcessFlowCard.part_id == part_id,
            ProcessFlowCard.created_at >= start_date,
        )
    )
    total_duration = duration_result.scalar() or 0

    return {
        "part_id": part_id,
        "period_days": days,
        "total_cards": total_count,
        "total_output": total_output,
        "total_good_qty": total_good,
        "total_reject_qty": total_output - total_good,
        "total_duration_minutes": total_duration,
        "avg_good_rate": round(total_good / total_output * 100, 2) if total_output > 0 else 0,
    }
