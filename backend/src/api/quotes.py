"""Quote API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.quote import Quote, QuoteItem, QuoteState, SurfaceTreatment
from app.models.user import User
from app.schemas.quote import (
    BossApprovalUpdate,
    FixUpdate,
    PricingUpdate,
    QuoteCreate,
    QuoteListResponse,
    QuoteResponse,
    QuoteUpdate,
    SurfaceTreatmentCreate,
    TechApprovalUpdate,
    TechReviewUpdate,
)
from app.services import quote_service

router = APIRouter(prefix="/quotes", tags=["Quotes"])


def _quote_to_response(quote: Quote) -> QuoteResponse:
    """Convert Quote model to response schema."""
    data = {
        "id": quote.id,
        "quote_no": quote.quote_no,
        "title": quote.title,
        "customer_id": quote.customer_id,
        "creator_id": quote.creator_id,
        "state": quote.state,
        "annual_usage": quote.annual_usage,
        "annual_avg_usage": quote.annual_avg_usage,
        # Technical
        "thickness_t": quote.thickness_t,
        "width_w": quote.width_w,
        "press_p": quote.press_p,
        "cavity_count": quote.cavity_count,
        "tonnage": quote.tonnage,
        "mold_fee": quote.mold_fee,
        "mold_fee_mode": quote.mold_fee_mode,
        "mold_fee_discount": quote.mold_fee_discount,
        # Pricing
        "stamping_fee": quote.stamping_fee,
        "surface_treatment_fee": quote.surface_treatment_fee,
        "profit_margin": quote.profit_margin,
        # Snapshot & path
        "price_snapshot": quote.price_snapshot,
        "fix_path": quote.fix_path,
        # Rejection
        "reject_reason": quote.reject_reason,
        "tech_reject_reason": quote.tech_reject_reason,
        # Timestamps
        "submitted_for_review_at": quote.submitted_for_review_at,
        "tech_reviewed_at": quote.tech_reviewed_at,
        "submitted_to_boss_at": quote.submitted_to_boss_at,
        "boss_reviewed_at": quote.boss_reviewed_at,
        "fixed_at": quote.fixed_at,
        # Creator
        "creator_name": quote.creator.full_name if quote.creator else None,
        # Items
        "items": [
            {
                "id": item.id,
                "quote_id": item.quote_id,
                "part_name": item.part_name,
                "customer_part_no": item.customer_part_no,
                "vehicle_model": item.vehicle_model,
                "drawing_no": item.drawing_no,
                "material": item.material,
                "thickness": item.thickness,
                "width": item.width,
                "weight_kg": item.weight_kg,
                "unit_price": item.unit_price,
                "moq": item.moq,
                "lead_time_days": item.lead_time_days,
                "surface_treatments": [
                    {
                        "id": st.id,
                        "quote_id": st.quote_id,
                        "quote_item_id": st.quote_item_id,
                        "sequence": st.sequence,
                        "name": st.name,
                        "fee": st.fee,
                        "notes": st.notes,
                    }
                    for st in (item.surface_treatments or [])
                ],
            }
            for item in (quote.items or [])
        ],
    }
    return QuoteResponse(**data)


@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(
    data: QuoteCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Create a new quote (role_level >= 5 required)."""
    require_role(current_user, min_level=5)

    quote = await quote_service.create_quote(db, data, current_user)
    return _quote_to_response(quote)


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Get quote by ID."""
    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return _quote_to_response(quote)


@router.get("", response_model=list[QuoteListResponse])
async def list_quotes(
    db: DbSession,
    current_user: CurrentUser,
    state: Optional[QuoteState] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[QuoteListResponse]:
    """List quotes with optional filters."""
    query = (
        select(Quote)
        .options(selectinload(Quote.creator))
        .where(Quote.is_deleted == False)
    )
    if state:
        query = query.where(Quote.state == state)
    if customer_id:
        query = query.where(Quote.customer_id == customer_id)

    query = query.order_by(Quote.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    quotes = result.scalars().all()

    return [
        QuoteListResponse(
            id=q.id,
            quote_no=q.quote_no,
            title=q.title,
            state=q.state,
            customer_id=q.customer_id,
            customer_name=q.customer.name if q.customer else None,
            creator_name=q.creator.full_name if q.creator else None,
            created_at=q.created_at,
            updated_at=q.updated_at,
        )
        for q in quotes
    ]


@router.patch("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: int,
    data: QuoteUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Update quote basic fields."""
    require_role(current_user, min_level=5)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.state not in (QuoteState.DRAFT, QuoteState.TECH_REVIEW, QuoteState.REJECTED):
        raise HTTPException(status_code=400, detail="Quote cannot be modified in current state")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(quote, field, value)

    await db.commit()
    await db.refresh(quote)
    return _quote_to_response(quote)


@router.post("/{quote_id}/submit-review", response_model=QuoteResponse)
async def submit_for_review(
    quote_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Submit quote for technical review."""
    require_role(current_user, min_level=4)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        quote = await quote_service.submit_for_tech_review(db, quote)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _quote_to_response(quote)


@router.post("/{quote_id}/pricing", response_model=QuoteResponse)
async def update_pricing(
    quote_id: int,
    data: PricingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Update pricing fields (stamping, surface treatment, profit)."""
    require_role(current_user, min_level=5)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        quote = await quote_service.update_pricing(db, quote, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _quote_to_response(quote)


@router.post("/{quote_id}/submit-boss", response_model=QuoteResponse)
async def submit_to_boss(
    quote_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Submit quote to boss for approval (role_level >= 5)."""
    require_role(current_user, min_level=5)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        quote = await quote_service.submit_to_boss(db, quote)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _quote_to_response(quote)


@router.post("/{quote_id}/tech-review", response_model=QuoteResponse)
async def tech_review(
    quote_id: int,
    data: TechApprovalUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Process technical review (approve or reject)."""
    require_role(current_user, min_level=4)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        quote = await quote_service.submit_tech_review(db, quote, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _quote_to_response(quote)


@router.post("/{quote_id}/boss-approve", response_model=QuoteResponse)
async def boss_approve(
    quote_id: int,
    data: BossApprovalUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Boss approval (role_level >= 9)."""
    require_role(current_user, min_level=9)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        quote = await quote_service.boss_approve(db, quote, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _quote_to_response(quote)


@router.post("/{quote_id}/fix", response_model=QuoteResponse)
async def fix_quote(
    quote_id: int,
    data: FixUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Fix (confirm) quote after boss approval."""
    require_role(current_user, min_level=5)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    try:
        quote = await quote_service.fix_quote(db, quote, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _quote_to_response(quote)


@router.post(
    "/{quote_id}/items/{item_id}/surface-treatments",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_surface_treatment(
    quote_id: int,
    item_id: int,
    data: SurfaceTreatmentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> QuoteResponse:
    """Add surface treatment to a quote item."""
    require_role(current_user, min_level=5)

    quote = await quote_service.get_quote_by_id(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    await quote_service.add_surface_treatment(
        db,
        quote_id=quote_id,
        item_id=item_id,
        name=data.name,
        fee=data.fee,
        sequence=data.sequence,
        notes=data.notes,
    )

    quote = await quote_service.get_quote_by_id(db, quote_id)
    return _quote_to_response(quote)
