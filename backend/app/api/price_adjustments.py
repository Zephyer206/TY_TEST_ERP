"""Price adjustment approval API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.price import PriceAdjustment
from app.schemas.price import (
    PriceAdjustmentCreate,
    PriceAdjustmentApprovalRequest,
    PriceAdjustmentResponse,
)

router = APIRouter(prefix="/price-adjustments", tags=["Price Adjustments"])


@router.post("", response_model=PriceAdjustmentResponse)
async def create_price_adjustment(
    adjustment: PriceAdjustmentCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> PriceAdjustment:
    """Create a new price adjustment request."""

    new_adjustment = PriceAdjustment(
        **adjustment.model_dump(),
        requested_by=current_user.id,
        status="pending"
    )

    db.add(new_adjustment)
    await db.commit()
    await db.refresh(new_adjustment)

    return new_adjustment


@router.get("", response_model=list[PriceAdjustmentResponse])
async def list_price_adjustments(
    db: DbSession,
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
) -> list[PriceAdjustment]:
    """Get price adjustment requests."""

    query = select(PriceAdjustment)

    if status:
        query = query.where(PriceAdjustment.status == status)

    query = query.order_by(desc(PriceAdjustment.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{adjustment_id}", response_model=PriceAdjustmentResponse)
async def get_price_adjustment(
    adjustment_id: int,
    db: DbSession,
) -> PriceAdjustment:
    """Get a specific price adjustment by ID."""

    result = await db.execute(
        select(PriceAdjustment).where(PriceAdjustment.id == adjustment_id)
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Price adjustment not found")

    return adjustment


@router.post("/{adjustment_id}/approve", response_model=PriceAdjustmentResponse)
async def approve_price_adjustment(
    adjustment_id: int,
    approval: PriceAdjustmentApprovalRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> PriceAdjustment:
    """Approve or reject a price adjustment request."""

    result = await db.execute(
        select(PriceAdjustment).where(PriceAdjustment.id == adjustment_id)
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Price adjustment not found")

    if adjustment.status != "pending":
        raise HTTPException(status_code=400, detail="Adjustment has already been reviewed")

    # Update adjustment status
    adjustment.status = "approved" if approval.approved else "rejected"
    adjustment.reviewed_by = current_user.id
    adjustment.reviewed_at = datetime.utcnow()
    adjustment.review_notes = approval.notes

    if approval.approved and adjustment.effective_date is None:
        # Set effective date to today if not specified
        from datetime import date
        adjustment.effective_date = date.today()

    await db.commit()
    await db.refresh(adjustment)

    # If approved, create corresponding price record
    if approval.approved:
        if adjustment.adjustment_type == "material":
            from app.models.price import CustomerMaterialPrice
            from datetime import date

            new_price = CustomerMaterialPrice(
                customer_id=adjustment.customer_id,
                material_id=adjustment.material_id,
                unit_price=adjustment.new_price,
                effective_date=adjustment.effective_date or date.today(),
                created_by=current_user.id
            )
            db.add(new_price)

        elif adjustment.adjustment_type == "treatment":
            from app.models.price import CustomerTreatmentPrice
            from datetime import date

            new_price = CustomerTreatmentPrice(
                customer_id=adjustment.customer_id,
                treatment_name=adjustment.treatment_name,
                rate=adjustment.new_price,
                effective_date=adjustment.effective_date or date.today(),
                created_by=current_user.id
            )
            db.add(new_price)

        await db.commit()

    return adjustment


@router.post("/{adjustment_id}/cancel", response_model=PriceAdjustmentResponse)
async def cancel_price_adjustment(
    adjustment_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> PriceAdjustment:
    """Cancel a pending price adjustment request."""

    result = await db.execute(
        select(PriceAdjustment).where(PriceAdjustment.id == adjustment_id)
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Price adjustment not found")

    if adjustment.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending adjustments can be cancelled")

    if adjustment.requested_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only cancel your own requests")

    adjustment.status = "cancelled"
    await db.commit()
    await db.refresh(adjustment)

    return adjustment
