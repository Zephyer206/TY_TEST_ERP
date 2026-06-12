"""Business logic for part management."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.part import Part, PartState


async def get_part_by_id(
    db: AsyncSession,
    part_id: int,
) -> Optional[Part]:
    """Get a part by ID."""
    result = await db.execute(
        select(Part).where(Part.id == part_id, Part.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_parts_by_customer(
    db: AsyncSession,
    customer_id: int,
) -> Sequence[Part]:
    """Get all parts for a customer."""
    result = await db.execute(
        select(Part).where(
            Part.customer_id == customer_id,
            Part.is_deleted == False,
        ).order_by(Part.created_at.desc())
    )
    return result.scalars().all()


async def update_part_state(
    db: AsyncSession,
    part: Part,
    new_state: PartState,
) -> Part:
    """Update part state."""
    part.state = new_state
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return part


async def transition_to_mass_production(
    db: AsyncSession,
    part: Part,
) -> Part:
    """Transition part from Sampling to MassProduction."""
    if part.state != PartState.SAMPLING:
        raise ValueError(f"Part must be in Sampling state, current: {part.state.value}")

    part.state = PartState.MASSPRODUCTION
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return part


async def transition_to_sampling(
    db: AsyncSession,
    part: Part,
) -> Part:
    """Transition part to Sampling state (for sample-first fix path)."""
    if part.state != PartState.DRAFT:
        raise ValueError(f"Part must be in Draft state, current: {part.state.value}")

    part.state = PartState.SAMPLING
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return part
