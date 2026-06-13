"""Business logic for process flow card generation."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.machine import Machine
from app.models.part import Part
from app.models.production import (
    ProcessFlowCard,
    ProcessFlowStatus,
    ProductionSession,
)
from app.models.tooling import Tooling


def generate_card_no() -> str:
    """Generate a unique process flow card number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"PFC-{prefix}-{now.strftime('%H%M%S')}"


async def generate_process_flow_card(
    db: AsyncSession,
    session: ProductionSession,
) -> ProcessFlowCard:
    """Generate a process flow card from a closed production session."""
    # Get related entities
    machine_result = await db.execute(
        select(Machine).where(Machine.id == session.machine_id)
    )
    machine = machine_result.scalar_one_or_none()

    part_result = await db.execute(
        select(Part).where(Part.id == session.part_id)
    )
    part = part_result.scalar_one_or_none()

    tooling = None
    if session.tooling_id:
        tooling_result = await db.execute(
            select(Tooling).where(Tooling.id == session.tooling_id)
        )
        tooling = tooling_result.scalar_one_or_none()

    # Get material batch number if available
    material_batch_no = None
    if session.material_batch_id:
        from app.models.warehouse import MaterialBatch

        batch_result = await db.execute(
            select(MaterialBatch).where(MaterialBatch.id == session.material_batch_id)
        )
        batch = batch_result.scalar_one_or_none()
        if batch:
            material_batch_no = batch.batch_no

    card_no = generate_card_no()

    card = ProcessFlowCard(
        card_no=card_no,
        session_id=session.id,
        part_id=session.part_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        material_batch_no=material_batch_no,
        planned_qty=session.total_output,
        actual_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        status=ProcessFlowStatus.COMPLETED,
        start_time=session.started_at,
        end_time=session.closed_at,
        operator_id=session.operator_id,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def get_process_flow_card(
    db: AsyncSession,
    card_id: int,
) -> Optional[ProcessFlowCard]:
    """Get a process flow card by ID."""
    result = await db.execute(
        select(ProcessFlowCard)
        .where(ProcessFlowCard.id == card_id)
    )
    return result.scalar_one_or_none()


async def get_process_flow_cards(
    db: AsyncSession,
    part_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    status: Optional[ProcessFlowStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[ProcessFlowCard]:
    """Get process flow cards with optional filters."""
    query = select(ProcessFlowCard).where(ProcessFlowCard.id > 0)

    if part_id:
        query = query.where(ProcessFlowCard.part_id == part_id)
    if machine_id:
        query = query.where(ProcessFlowCard.machine_id == machine_id)
    if status:
        query = query.where(ProcessFlowCard.status == status)

    query = query.order_by(ProcessFlowCard.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_card_status(
    db: AsyncSession,
    card: ProcessFlowCard,
    status: ProcessFlowStatus,
) -> ProcessFlowCard:
    """Update process flow card status."""
    card.status = status
    if status == ProcessFlowStatus.IN_PROGRESS and not card.start_time:
        card.start_time = datetime.utcnow()
    elif status == ProcessFlowStatus.COMPLETED and not card.end_time:
        card.end_time = datetime.utcnow()

    await db.commit()
    await db.refresh(card)
    return card
