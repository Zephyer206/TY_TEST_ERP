"""Price adjustment approval API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.price import CustomerMaterialPrice, CustomerTreatmentPrice, PriceAdjustment, TreatmentDict
from app.schemas.price import (
    CustomerPriceAdjustmentApprovalRequest,
    CustomerPriceAdjustmentCreate,
    CustomerPriceAdjustmentResponse,
)

router = APIRouter(prefix="/price-adjustments", tags=["Price Adjustments"])


@router.post("", response_model=CustomerPriceAdjustmentResponse)
async def create_price_adjustment(
    adjustment: CustomerPriceAdjustmentCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> PriceAdjustment:
    """Create a new price adjustment request."""
    require_role(current_user, min_level=2)

    new_adjustment = PriceAdjustment(
        **adjustment.model_dump(),
        requested_by=current_user.id,
        status="pending"
    )

    db.add(new_adjustment)
    await db.commit()
    await db.refresh(new_adjustment)

    return new_adjustment


@router.get("", response_model=list[CustomerPriceAdjustmentResponse])
async def list_price_adjustments(
    db: DbSession,
    current_user: CurrentUser,
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
) -> list[PriceAdjustment]:
    """Get price adjustment requests."""
    require_role(current_user, min_level=2)

    query = select(PriceAdjustment)

    if customer_id is not None:
        query = query.where(PriceAdjustment.customer_id == customer_id)
    if status:
        query = query.where(PriceAdjustment.status == status)

    query = query.order_by(desc(PriceAdjustment.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{adjustment_id}", response_model=CustomerPriceAdjustmentResponse)
async def get_price_adjustment(
    adjustment_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PriceAdjustment:
    """Get a specific price adjustment by ID."""
    require_role(current_user, min_level=2)

    result = await db.execute(
        select(PriceAdjustment).where(PriceAdjustment.id == adjustment_id)
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Price adjustment not found")

    return adjustment


@router.post("/{adjustment_id}/approve", response_model=CustomerPriceAdjustmentResponse)
async def approve_price_adjustment(
    adjustment_id: int,
    approval: CustomerPriceAdjustmentApprovalRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> PriceAdjustment:
    """Approve or reject a price adjustment request."""
    require_role(current_user, min_level=3)

    result = await db.execute(
        select(PriceAdjustment)
        .where(PriceAdjustment.id == adjustment_id)
        .with_for_update()
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=404, detail="Price adjustment not found")

    if adjustment.status != "pending":
        raise HTTPException(status_code=400, detail="Adjustment has already been reviewed")

    # Update adjustment status
    adjustment.status = approval.status
    adjustment.reviewed_by = current_user.id
    adjustment.reviewed_at = datetime.utcnow()
    adjustment.review_notes = approval.rejection_reason

    if approval.status == "approved" and adjustment.effective_date is None:
        # Set effective date to today if not specified
        adjustment.effective_date = datetime.utcnow()

    # If approved, create the corresponding customer price history in the same
    # transaction as the approval state change.
    if approval.status == "approved":
        if adjustment.adjustment_type == "material":
            if adjustment.material_id is None:
                raise HTTPException(status_code=422, detail="material_id is required for material adjustments")
            new_price = CustomerMaterialPrice(
                customer_id=adjustment.customer_id,
                material_id=adjustment.material_id,
                unit_price=adjustment.new_price,
                quoted_at=adjustment.effective_date or datetime.utcnow(),
                created_by=current_user.id
            )
            db.add(new_price)

        elif adjustment.adjustment_type == "treatment":
            if not adjustment.treatment_name:
                raise HTTPException(status_code=422, detail="treatment_name is required for treatment adjustments")
            treatment_result = await db.execute(
                select(TreatmentDict).where(TreatmentDict.name == adjustment.treatment_name)
            )
            treatment = treatment_result.scalar_one_or_none()
            if treatment is None:
                raise HTTPException(status_code=422, detail="Treatment not found")

            new_price = CustomerTreatmentPrice(
                customer_id=adjustment.customer_id,
                treatment_id=treatment.id,
                unit_price=adjustment.new_price,
                calc_mode_snapshot=treatment.calc_mode,
                unit_snapshot=treatment.unit,
                quoted_at=adjustment.effective_date or datetime.utcnow(),
                created_by=current_user.id
            )
            db.add(new_price)

    await db.commit()
    await db.refresh(adjustment)

    return adjustment


@router.post("/{adjustment_id}/cancel", response_model=CustomerPriceAdjustmentResponse)
async def cancel_price_adjustment(
    adjustment_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> PriceAdjustment:
    """Cancel a pending price adjustment request."""
    require_role(current_user, min_level=2)

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
