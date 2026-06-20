"""Business logic for quote management."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quote import FixPath, MoldFeeMode, NominationStatus, Quote, QuoteItem, QuoteState, SurfaceTreatment
from app.models.user import User
from app.schemas.quote import (
    BossApprovalUpdate,
    FixUpdate,
    PricingUpdate,
    QuoteCreate,
    TechApprovalUpdate,
    TechReviewUpdate,
)


def generate_quote_no(db: AsyncSession) -> str:
    """Generate a unique quote number."""
    import asyncio
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"QT-{prefix}-{now.strftime('%H%M%S')}"


async def create_quote(
    db: AsyncSession,
    data: QuoteCreate,
    creator: User,
) -> Quote:
    """Create a new quote with items."""
    quote_no = await generate_quote_no(db)

    quote = Quote(
        quote_no=quote_no,
        title=data.title,
        customer_id=data.customer_id,
        creator_id=creator.id,
        state=QuoteState.DRAFT,
        annual_usage=data.annual_usage,
        annual_avg_usage=data.annual_avg_usage,
    )
    db.add(quote)
    await db.flush()

    for item_data in data.items:
        item = QuoteItem(
            quote_id=quote.id,
            part_name=item_data.part_name,
            customer_part_no=item_data.customer_part_no,
            vehicle_model=item_data.vehicle_model,
            drawing_no=item_data.drawing_no,
            material=item_data.material,
            thickness=item_data.thickness,
            width=item_data.width,
            weight_kg=item_data.weight_kg,
            unit_price=item_data.unit_price,
            moq=item_data.moq,
            lead_time_days=item_data.lead_time_days,
        )
        db.add(item)

    await db.commit()
    await db.refresh(quote)
    return quote


async def get_quote_by_id(
    db: AsyncSession,
    quote_id: int,
) -> Optional[Quote]:
    """Get a quote by ID with items loaded."""
    result = await db.execute(
        select(Quote)
        .options(selectinload(Quote.items).selectinload(QuoteItem.surface_treatments))
        .where(Quote.id == quote_id, Quote.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_quote_no(
    db: AsyncSession,
    quote_no: str,
) -> Optional[Quote]:
    """Get a quote by quote number."""
    result = await db.execute(
        select(Quote)
        .options(selectinload(Quote.items).selectinload(QuoteItem.surface_treatments))
        .where(Quote.quote_no == quote_no, Quote.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def submit_for_tech_review(
    db: AsyncSession,
    quote: Quote,
) -> Quote:
    """Submit quote for technical review."""
    if quote.state != QuoteState.DRAFT:
        raise ValueError(f"Cannot submit from state: {quote.state.value}")

    quote.state = QuoteState.TECH_REVIEW
    quote.submitted_for_review_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


async def submit_tech_review(
    db: AsyncSession,
    quote: Quote,
    data: TechReviewUpdate,
    reviewer: User,
) -> Quote:
    """Process tech review (approve or reject).

    WAITING_FOR_TECH → TECH_APPROVED (approve) | TECH_REJECTED (reject)
    TECH_REVIEW → TECH_APPROVED (approve) | TECH_REJECTED (reject)
    """
    if quote.state not in (QuoteState.WAITING_FOR_TECH, QuoteState.TECH_REVIEW):
        raise ValueError(f"Not in tech review state: {quote.state.value}")

    if data.approved:
        quote.state = QuoteState.TECH_APPROVED
        for field, value in data.model_dump(exclude_unset=True).items():
            if field not in ("approved", "reject_reason") and value is not None:
                setattr(quote, field, value)
        quote.tech_reviewed_at = datetime.utcnow()
        quote.tech_reject_reason = None
    else:
        quote.state = QuoteState.TECH_REJECTED
        quote.tech_reject_reason = data.reject_reason
        quote.tech_reviewed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(quote)
    return quote


async def update_pricing(
    db: AsyncSession,
    quote: Quote,
    data: PricingUpdate,
    operator: User,
) -> tuple[Quote, bool]:
    """Update pricing fields (stamping, surface treatment, profit).

    Returns (quote, triggered_reapproval).
    - APPROVED state: price fields are editable, only final_price change triggers reapproval.
    - Other states: standard editable states.
    """
    if quote.state == QuoteState.APPROVED:
        current_final = _compute_final_price(quote)
        triggered = False

        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(quote, field, value)

        updated_final = _compute_final_price(quote)
        if current_final != updated_final:
            triggered = True
            quote.state = QuoteState.PENDING_BOSS
            quote.submitted_to_boss_at = datetime.utcnow()
    elif quote.state in (QuoteState.DRAFT, QuoteState.TECH_APPROVED, QuoteState.REJECTED):
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(quote, field, value)
    else:
        raise ValueError(f"Cannot update pricing in state: {quote.state.value}")

    await db.commit()
    await db.refresh(quote)
    return quote, triggered


def _compute_final_price(quote: Quote) -> Optional[Decimal]:
    """Compute current final price from quote fields."""
    if quote.final_price is not None:
        return quote.final_price
    total = Decimal("0")
    if quote.stamping_fee is not None:
        total += quote.stamping_fee
    if quote.surface_treatment_fee is not None:
        total += quote.surface_treatment_fee
    return total


async def submit_to_boss(
    db: AsyncSession,
    quote: Quote,
) -> Quote:
    """Submit quote to boss for approval."""
    if quote.state not in (QuoteState.DRAFT, QuoteState.TECH_REVIEW):
        raise ValueError(f"Cannot submit to boss from state: {quote.state.value}")

    quote.state = QuoteState.PENDING_BOSS
    quote.submitted_to_boss_at = datetime.utcnow()
    await db.commit()
    await db.refresh(quote)
    return quote


def _build_price_snapshot(quote: Quote) -> dict:
    """Build price snapshot from current quote fields."""
    return {
        "material_unit_price": None,  # Will be filled from part
        "surface_treatment_fee": float(quote.surface_treatment_fee or 0),
        "stamping_fee": float(quote.stamping_fee or 0),
        "mold_fee": float(quote.mold_fee or 0),
        "mold_fee_mode": quote.mold_fee_mode.value if quote.mold_fee_mode else None,
        "mold_fee_discount": quote.mold_fee_discount,
        "profit_margin": float(quote.profit_margin or 0),
        "snapshot_at": datetime.utcnow().isoformat(),
    }


async def boss_approve(
    db: AsyncSession,
    quote: Quote,
    data: BossApprovalUpdate,
    approver: User,
) -> Quote:
    """Process boss approval (approve or reject)."""
    if quote.state != QuoteState.PENDING_BOSS:
        raise ValueError(f"Not pending boss approval: {quote.state.value}")

    if data.approved:
        quote.state = QuoteState.APPROVED
        quote.boss_reviewed_at = datetime.utcnow()
        quote.reject_reason = None
        quote.price_snapshot = _build_price_snapshot(quote)
    else:
        quote.state = QuoteState.DRAFT
        quote.boss_reviewed_at = datetime.utcnow()
        quote.reject_reason = data.reject_reason

    await db.commit()
    await db.refresh(quote)
    return quote


async def fix_quote(
    db: AsyncSession,
    quote: Quote,
    data: FixUpdate,
    fixer: User,
) -> Quote:
    """Fix (confirm) a quote after boss approval.

    Writes final_price from FixUpdate (manual input).
    Sets nomination_status = FIXED.
    Creates Parts for each QuoteItem based on the fix_path.
    """
    if quote.state != QuoteState.APPROVED:
        raise ValueError(f"Not approved yet: {quote.state.value}")

    quote.state = QuoteState.FIXED
    quote.nomination_status = NominationStatus.FIXED
    quote.fix_path = data.fix_path
    quote.fixed_at = datetime.utcnow()
    if data.final_price is not None:
        quote.final_price = data.final_price

    from app.models.part import Part, PartState

    for item in quote.items:
        part_no = f"PT-{quote.id:06d}-{item.id:04d}"
        part = Part(
            part_no=part_no,
            part_name=item.part_name,
            customer_id=quote.customer_id,
            quote_id=quote.id,
            customer_part_no=item.customer_part_no,
            vehicle_model=item.vehicle_model,
            drawing_no=item.drawing_no,
            material=item.material,
            thickness=item.thickness,
            width=item.width,
            cavity_count=quote.cavity_count,
            tonnage=quote.tonnage,
            price_snapshot=quote.price_snapshot,
            state=PartState.SAMPLING if data.fix_path == FixPath.SAMPLE_FIRST else PartState.DRAFT,
        )
        db.add(part)

    await db.commit()
    await db.refresh(quote)
    return quote


async def revoke_nomination(
    db: AsyncSession,
    quote: Quote,
    revoke_reason: Optional[str],
    revoker: User,
) -> Quote:
    """Revoke nomination (fix) on a fixed quote.

    Quotes stays at APPROVED, nomination_status → REVOKED.
    An audit log entry records operator_id + operated_at.
    """
    if quote.state != QuoteState.FIXED:
        raise ValueError(f"Quote is not fixed: {quote.state.value}")
    if quote.nomination_status != NominationStatus.FIXED:
        raise ValueError(f"Nomination is not in FIXED state: {quote.nomination_status.value}")

    quote.state = QuoteState.APPROVED
    quote.nomination_status = NominationStatus.REVOKED
    quote.revoked_at = datetime.utcnow()
    quote.revoked_by = revoker.id
    quote.revoke_reason = revoke_reason

    await db.commit()
    await db.refresh(quote)
    return quote


async def add_surface_treatment(
    db: AsyncSession,
    quote_id: int,
    item_id: Optional[int],
    name: str,
    fee: Decimal,
    sequence: int = 1,
    notes: Optional[str] = None,
) -> SurfaceTreatment:
    """Add a surface treatment step to a quote item."""
    treatment = SurfaceTreatment(
        quote_id=quote_id,
        quote_item_id=item_id,
        name=name,
        fee=fee,
        sequence=sequence,
        notes=notes,
    )
    db.add(treatment)
    await db.commit()
    await db.refresh(treatment)
    return treatment
