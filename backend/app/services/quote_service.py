"""Business logic for quote management."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quote import FixPath, NominationStatus, Quote, QuoteState
from app.models.user import User
from app.schemas.quote import (
    BossApprovalUpdate,
    FixUpdate,
    PricingUpdate,
    QuoteCreate,
    TechApprovalUpdate,
)


async def create_quote(db: AsyncSession, data: QuoteCreate, creator: User) -> Quote:
    """Create a new quote in DRAFT state."""
    from app.models.part import Part
    # Verify part exists
    part = await db.get(Part, data.part_id)
    if not part:
        raise ValueError(f"Part {data.part_id} not found")

    now = datetime.utcnow()
    serial = f"Q-{data.part_id}-{now.strftime('%Y%m')}-{now.strftime('%H%M%S')}"

    quote = Quote(
        part_id=data.part_id,
        quote_serial=serial,
        customer_id=data.customer_id,
        customer_product_no=data.customer_product_no,
        vehicle_model=data.vehicle_model,
        annual_usage=data.annual_usage or 0,
        approval_status=QuoteState.DRAFT,
        submitted_by=creator.id,
        created_at=now,
        updated_at=now,
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote


async def get_quote_by_id(db: AsyncSession, quote_id: int) -> Optional[Quote]:
    """Get a quote by ID with relationships loaded."""
    result = await db.execute(
        select(Quote)
        .options(
            selectinload(Quote.part),
            selectinload(Quote.creator),
            selectinload(Quote.customer),
        )
        .where(Quote.id == quote_id, Quote.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def submit_for_tech_review(db: AsyncSession, quote: Quote) -> Quote:
    if quote.approval_status not in (QuoteState.DRAFT, QuoteState.TECH_REJECTED):
        raise ValueError(f"Cannot submit from state: {quote.approval_status}")
    quote.approval_status = QuoteState.WAITING_FOR_TECH
    quote.submitted_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


async def submit_tech_review(
    db: AsyncSession, quote: Quote, data: TechApprovalUpdate, reviewer: User
) -> Quote:
    if quote.approval_status not in (QuoteState.WAITING_FOR_TECH, QuoteState.TECH_REVIEW):
        raise ValueError(f"Not in tech review state: {quote.approval_status}")
    if data.approved:
        quote.approval_status = QuoteState.TECH_APPROVED
        # write tech params if provided
        for field, value in data.model_dump(exclude_unset=True).items():
            if field not in ("approved", "reject_reason") and value is not None and hasattr(quote, field):
                setattr(quote, field, value)
        quote.rejection_reason = None
    else:
        quote.approval_status = QuoteState.TECH_REJECTED
        quote.rejection_reason = data.reject_reason
    quote.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


async def update_pricing(
    db: AsyncSession, quote: Quote, data: PricingUpdate, operator: User
) -> tuple[Quote, bool]:
    editable = {
        QuoteState.DRAFT, QuoteState.TECH_APPROVED, QuoteState.TECH_REJECTED,
        QuoteState.REJECTED, QuoteState.APPROVED,
    }
    if quote.approval_status not in editable:
        raise ValueError(f"Cannot update pricing in state: {quote.approval_status}")

    old_final = quote.final_price
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None and hasattr(quote, field):
            setattr(quote, field, value)
    quote.updated_at = datetime.utcnow()

    # If APPROVED and final_price changed → re-trigger boss approval
    triggered = False
    if quote.approval_status == QuoteState.APPROVED and old_final != quote.final_price:
        triggered = True
        quote.approval_status = QuoteState.PENDING_BOSS

    await db.commit()
    await db.refresh(quote)
    return quote, triggered


async def submit_to_boss(db: AsyncSession, quote: Quote) -> Quote:
    allowed = {QuoteState.DRAFT, QuoteState.TECH_APPROVED, QuoteState.REJECTED}
    if quote.approval_status not in allowed:
        raise ValueError(f"Cannot submit to boss from state: {quote.approval_status}")
    quote.approval_status = QuoteState.PENDING_BOSS
    quote.submitted_at = datetime.utcnow()
    quote.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


def _build_price_snapshot(quote: Quote) -> dict:
    return {
        "stamping_fee": float(quote.stamping_fee or 0),
        "surface_fee": float(quote.surface_fee or 0),
        "treatment_fee": float(quote.treatment_fee or 0),
        "mold_cost": float(quote.mold_cost or 0),
        "profit_margin": float(quote.profit_margin or 0),
        "snapshot_at": datetime.utcnow().isoformat(),
    }


async def boss_approve(
    db: AsyncSession, quote: Quote, data: BossApprovalUpdate, approver: User
) -> Quote:
    if quote.approval_status != QuoteState.PENDING_BOSS:
        raise ValueError(f"Not pending boss approval: {quote.approval_status}")
    if data.approved:
        quote.approval_status = QuoteState.APPROVED
        quote.approved_at = datetime.utcnow()
        quote.approved_by = approver.id
        quote.rejection_reason = None
        quote.price_snapshot = _build_price_snapshot(quote)
    else:
        quote.approval_status = QuoteState.DRAFT
        quote.rejection_reason = data.reject_reason
    quote.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


async def fix_quote(
    db: AsyncSession, quote: Quote, data: FixUpdate, fixer: User
) -> Quote:
    if quote.approval_status != QuoteState.APPROVED:
        raise ValueError(f"Not approved yet: {quote.approval_status}")
    quote.approval_status = QuoteState.FIXED
    quote.nomination_status = NominationStatus.FIXED
    quote.nomination_confirmed_at = datetime.utcnow()
    quote.nomination_confirmed_by = fixer.id
    if data.final_price is not None:
        quote.final_price = data.final_price
    quote.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


async def revoke_nomination(
    db: AsyncSession, quote: Quote, revoke_reason: Optional[str], revoker: User
) -> Quote:
    if quote.approval_status != QuoteState.FIXED:
        raise ValueError(f"Quote is not fixed: {quote.approval_status}")
    quote.approval_status = QuoteState.APPROVED
    quote.nomination_status = NominationStatus.REVOKED
    quote.nomination_confirmed_by = revoker.id
    quote.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote
