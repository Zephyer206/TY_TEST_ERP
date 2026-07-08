"""Customer price history API endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.price import CustomerMaterialPrice, CustomerTreatmentPrice
from app.schemas.price import (
    CustomerMaterialPriceCreate,
    CustomerMaterialPriceResponse,
    CustomerTreatmentPriceCreate,
    CustomerTreatmentPriceResponse,
)

router = APIRouter(prefix="/customer-prices", tags=["Customer Prices"])


@router.post("/materials", response_model=CustomerMaterialPriceResponse)
async def create_material_price(
    price: CustomerMaterialPriceCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CustomerMaterialPrice:
    """Create a new customer material price record."""

    new_price = CustomerMaterialPrice(
        **price.model_dump(),
        created_by=current_user.id
    )

    db.add(new_price)
    await db.commit()
    await db.refresh(new_price)

    return new_price


@router.get("/materials", response_model=list[CustomerMaterialPriceResponse])
async def list_material_prices(
    db: DbSession,
    customer_id: Optional[int] = Query(None),
    material_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
) -> list[CustomerMaterialPrice]:
    """Get customer material price history."""

    query = select(CustomerMaterialPrice)

    if customer_id:
        query = query.where(CustomerMaterialPrice.customer_id == customer_id)
    if material_id:
        query = query.where(CustomerMaterialPrice.material_id == material_id)

    query = query.order_by(desc(CustomerMaterialPrice.effective_date)).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/treatments", response_model=CustomerTreatmentPriceResponse)
async def create_treatment_price(
    price: CustomerTreatmentPriceCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CustomerTreatmentPrice:
    """Create a new customer treatment price record."""

    new_price = CustomerTreatmentPrice(
        **price.model_dump(),
        created_by=current_user.id
    )

    db.add(new_price)
    await db.commit()
    await db.refresh(new_price)

    return new_price


@router.get("/treatments", response_model=list[CustomerTreatmentPriceResponse])
async def list_treatment_prices(
    db: DbSession,
    customer_id: Optional[int] = Query(None),
    treatment_name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
) -> list[CustomerTreatmentPrice]:
    """Get customer treatment price history."""

    query = select(CustomerTreatmentPrice)

    if customer_id:
        query = query.where(CustomerTreatmentPrice.customer_id == customer_id)
    if treatment_name:
        query = query.where(CustomerTreatmentPrice.treatment_name == treatment_name)

    query = query.order_by(desc(CustomerTreatmentPrice.effective_date)).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/materials/latest")
async def get_latest_material_price(
    db: DbSession,
    customer_id: int = Query(...),
    material_id: int = Query(...),
    as_of_date: Optional[date] = Query(None),
) -> Optional[CustomerMaterialPriceResponse]:
    """Get the latest material price for a customer as of a specific date."""

    query = select(CustomerMaterialPrice).where(
        CustomerMaterialPrice.customer_id == customer_id,
        CustomerMaterialPrice.material_id == material_id
    )

    if as_of_date:
        query = query.where(CustomerMaterialPrice.effective_date <= as_of_date)

    query = query.order_by(desc(CustomerMaterialPrice.effective_date)).limit(1)

    result = await db.execute(query)
    price = result.scalar_one_or_none()

    if not price:
        raise HTTPException(status_code=404, detail="No price found for this customer-material combination")

    return price


@router.get("/treatments/latest")
async def get_latest_treatment_price(
    db: DbSession,
    customer_id: int = Query(...),
    treatment_name: str = Query(...),
    as_of_date: Optional[date] = Query(None),
) -> Optional[CustomerTreatmentPriceResponse]:
    """Get the latest treatment price for a customer as of a specific date."""

    query = select(CustomerTreatmentPrice).where(
        CustomerTreatmentPrice.customer_id == customer_id,
        CustomerTreatmentPrice.treatment_name == treatment_name
    )

    if as_of_date:
        query = query.where(CustomerTreatmentPrice.effective_date <= as_of_date)

    query = query.order_by(desc(CustomerTreatmentPrice.effective_date)).limit(1)

    result = await db.execute(query)
    price = result.scalar_one_or_none()

    if not price:
        raise HTTPException(status_code=404, detail="No price found for this customer-treatment combination")

    return price
