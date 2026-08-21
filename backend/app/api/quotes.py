"""Quote API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.quote import Quote, QuoteState
from app.models.user import User
from app.schemas.quote import (
    BossApprovalUpdate,
    FixUpdate,
    PricingUpdate,
    QuoteCreate,
    QuoteListResponse,
    QuoteResponse,
    QuoteUpdate,
    RevokeNominationUpdate,
    TechApprovalUpdate,
)
from app.services import quote_service

router = APIRouter(prefix="/quotes", tags=["Quotes"])


async def _enrich(db, q: Quote) -> dict:
    """Load part/creator/customer for a quote row."""
    part = await db.get(Part, q.part_id) if q.part_id else None
    creator = await db.get(User, q.submitted_by) if q.submitted_by else None
    customer = await db.get(Customer, q.customer_id) if q.customer_id else None
    alias_query = select(PartCustomerAlias).where(
        PartCustomerAlias.part_id == q.part_id,
        PartCustomerAlias.is_active == True,
        PartCustomerAlias.data_quality_status == "approved",
    ) if q.part_id else None
    if alias_query is not None and q.customer_id:
        alias_query = alias_query.where(PartCustomerAlias.customer_id == q.customer_id)
    alias = (await db.execute(alias_query.order_by(PartCustomerAlias.id))).scalars().first() if alias_query is not None else None
    return dict(part=part, creator=creator, customer=customer, alias=alias)


async def _to_response(db, q: Quote) -> QuoteResponse:
    e = await _enrich(db, q)
    part, creator, customer, alias = e["part"], e["creator"], e["customer"], e["alias"]
    return QuoteResponse(
        id=q.id,
        quote_no=q.quote_serial or f"Q-{q.id}",
        part_id=q.part_id,
        part_name=part.internal_name if part else None,
        customer_part_no=alias.customer_part_no if alias else None,
        customer_id=q.customer_id,
        customer_name=customer.name if customer else None,
        customer_product_no=q.customer_product_no,
        vehicle_model=q.vehicle_model,
        annual_usage=q.annual_usage,
        approval_status=q.approval_status,
        nomination_status=q.nomination_status,
        rejection_reason=q.rejection_reason,
        price_snapshot=q.price_snapshot,
        thickness=float(q.thickness) if q.thickness else None,
        width=float(q.width) if q.width else None,
        press_stroke=float(q.press_stroke) if q.press_stroke else None,
        cavity_count=q.cavity_count,
        press_tonnage=q.press_tonnage,
        mold_cost=q.mold_cost,
        mold_discount_mode=q.mold_discount_mode,
        mold_discount_rate=float(q.mold_discount_rate) if q.mold_discount_rate else None,
        stamping_fee=q.stamping_fee,
        surface_fee=q.surface_fee,
        treatment_fee=q.treatment_fee,
        profit_margin=q.profit_margin,
        final_price=q.final_price,
        submitted_at=q.submitted_at,
        approved_at=q.approved_at,
        nomination_confirmed_at=q.nomination_confirmed_at,
        creator_name=creator.real_name if creator else None,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


@router.get("", response_model=list[QuoteListResponse])
async def list_quotes(
    db: DbSession,
    current_user: CurrentUser,
    approval_status: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[QuoteListResponse]:
    query = select(Quote).where(Quote.is_deleted == False)
    if approval_status:
        query = query.where(Quote.approval_status == approval_status)
    if customer_id:
        query = query.where(Quote.customer_id == customer_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.outerjoin(Part, Quote.part_id == Part.id).outerjoin(
            PartCustomerAlias,
            (PartCustomerAlias.part_id == Part.id)
            & (PartCustomerAlias.customer_id == Quote.customer_id)
            & (PartCustomerAlias.is_active == True)
            & (PartCustomerAlias.data_quality_status == "approved"),
        ).outerjoin(Customer, Quote.customer_id == Customer.id).where(
            or_(
                Quote.quote_serial.ilike(term),
                Quote.customer_product_no.ilike(term),
                PartCustomerAlias.customer_part_no.ilike(term),
                Part.internal_name.ilike(term),
                Customer.name.ilike(term),
            )
        )
    query = query.order_by(Quote.created_at.desc()).offset(skip).limit(limit)
    rows = (await db.execute(query)).scalars().all()

    # Batch load related entities
    part_ids = list({r.part_id for r in rows if r.part_id})
    creator_ids = list({r.submitted_by for r in rows if r.submitted_by})
    cust_ids = list({r.customer_id for r in rows if r.customer_id})

    parts = {p.id: p for p in (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars()}
    creators = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(creator_ids)))).scalars()}
    customers = {c.id: c for c in (await db.execute(select(Customer).where(Customer.id.in_(cust_ids)))).scalars()}
    aliases = (await db.execute(select(PartCustomerAlias).where(
        PartCustomerAlias.part_id.in_(part_ids),
        PartCustomerAlias.is_active == True,
        PartCustomerAlias.data_quality_status == "approved",
    ).order_by(PartCustomerAlias.id))).scalars().all()
    alias_by_part_customer = {(a.part_id, a.customer_id): a for a in aliases}

    return [
        QuoteListResponse(
            id=q.id,
            quote_no=q.quote_serial or f"Q-{q.id}",
            part_name=parts.get(q.part_id, None) and parts[q.part_id].internal_name or "",
            customer_part_no=(alias_by_part_customer.get((q.part_id, q.customer_id)).customer_part_no
                              if alias_by_part_customer.get((q.part_id, q.customer_id)) else None),
            customer_id=q.customer_id,
            customer_name=customers[q.customer_id].name if q.customer_id in customers else None,
            customer_product_no=q.customer_product_no,
            vehicle_model=q.vehicle_model,
            final_price=q.final_price,
            approval_status=q.approval_status,
            nomination_status=q.nomination_status,
            creator_name=creators[q.submitted_by].real_name if q.submitted_by in creators else None,
            created_at=q.created_at,
            updated_at=q.updated_at,
        )
        for q in rows
    ]


@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(data: QuoteCreate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Create quote - LV2: business staff."""
    require_role(current_user, min_level=2)
    quote = await quote_service.create_quote(db, data, current_user)
    return await _to_response(db, quote)


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(quote_id: int, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    return await _to_response(db, q)


@router.patch("/{quote_id}", response_model=QuoteResponse)
async def update_quote(quote_id: int, data: QuoteUpdate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Update quote - LV2: business staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(q, field, value)
    from datetime import datetime
    q.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(q)
    return await _to_response(db, q)


@router.post("/{quote_id}/submit-review", response_model=QuoteResponse)
async def submit_for_review(quote_id: int, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Submit for tech review - LV2: technical staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q = await quote_service.submit_for_tech_review(db, q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)


@router.post("/{quote_id}/tech-review", response_model=QuoteResponse)
async def tech_review(quote_id: int, data: TechApprovalUpdate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Tech review approval - LV2: technical staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q = await quote_service.submit_tech_review(db, q, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)


@router.post("/{quote_id}/pricing", response_model=QuoteResponse)
async def update_pricing(quote_id: int, data: PricingUpdate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Update pricing - LV2: business staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q, _ = await quote_service.update_pricing(db, q, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)


@router.post("/{quote_id}/submit-boss", response_model=QuoteResponse)
async def submit_to_boss(quote_id: int, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Submit to boss - LV2: business staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q = await quote_service.submit_to_boss(db, q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)


@router.post("/{quote_id}/boss-approve", response_model=QuoteResponse)
async def boss_approve(quote_id: int, data: BossApprovalUpdate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Boss final approval - LV3: boss only."""
    require_role(current_user, min_level=3)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q = await quote_service.boss_approve(db, q, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)


@router.post("/{quote_id}/fix", response_model=QuoteResponse)
async def fix_quote(quote_id: int, data: FixUpdate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Fix quote - LV2: business staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q = await quote_service.fix_quote(db, q, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)


@router.post("/{quote_id}/revoke-nomination", response_model=QuoteResponse)
async def revoke_nomination(quote_id: int, data: RevokeNominationUpdate, db: DbSession, current_user: CurrentUser) -> QuoteResponse:
    """Revoke nomination - LV2: business staff."""
    require_role(current_user, min_level=2)
    q = await db.get(Quote, quote_id)
    if not q or q.is_deleted:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        q = await quote_service.revoke_nomination(db, q, data.revoke_reason, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _to_response(db, q)
