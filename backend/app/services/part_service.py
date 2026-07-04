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
        select(Part).where(Part.id == part_id)
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
        ).order_by(Part.created_at.desc())
    )
    return result.scalars().all()


async def update_part_state(
    db: AsyncSession,
    part: Part,
    new_state: PartState,
) -> Part:
    """Update part state."""
    part.part_status = new_state.value if hasattr(new_state, 'value') else new_state
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return part


async def transition_to_mass_production(
    db: AsyncSession,
    part: Part,
) -> Part:
    """Transition part from Sampling to MassProduction."""
    if part.part_status != PartState.SAMPLING:
        raise ValueError(f"Part must be in Sampling state, current: {part.part_status}")
    part.part_status = PartState.MASSPRODUCTION
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return part


async def transition_to_sampling(
    db: AsyncSession,
    part: Part,
) -> Part:
    """Transition part to Sampling state (for sample-first fix path)."""
    if part.part_status != PartState.DRAFT:
        raise ValueError(f"Part must be in Draft state, current: {part.part_status}")
    part.part_status = PartState.SAMPLING
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return part
