"""Treatment dictionary API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.price import TreatmentDict
from app.schemas.treatment import (
    TreatmentDictCreate,
    TreatmentDictUpdate,
    TreatmentDictResponse,
)

router = APIRouter(prefix="/treatments", tags=["Treatment Dictionary"])


@router.post("", response_model=TreatmentDictResponse)
async def create_treatment(
    treatment: TreatmentDictCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> TreatmentDict:
    """Create a new treatment in dictionary."""
    require_role(current_user, min_level=4)

    # Check for duplicate name
    existing = await db.execute(
        select(TreatmentDict).where(TreatmentDict.name == treatment.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Treatment with this name already exists")

    new_treatment = TreatmentDict(**treatment.model_dump())

    db.add(new_treatment)
    await db.commit()
    await db.refresh(new_treatment)

    return new_treatment


@router.get("", response_model=list[TreatmentDictResponse])
async def list_treatments(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
) -> list[TreatmentDict]:
    """Get all treatments from dictionary."""
    require_role(current_user, min_level=1)

    query = select(TreatmentDict)

    if is_active is not None:
        query = query.where(TreatmentDict.is_active == is_active)

    query = query.order_by(TreatmentDict.sort_order, TreatmentDict.name).offset(skip).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{treatment_id}", response_model=TreatmentDictResponse)
async def get_treatment(
    treatment_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TreatmentDict:
    """Get a specific treatment by ID."""
    require_role(current_user, min_level=1)

    result = await db.execute(
        select(TreatmentDict).where(TreatmentDict.id == treatment_id)
    )
    treatment = result.scalar_one_or_none()

    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")

    return treatment


@router.put("/{treatment_id}", response_model=TreatmentDictResponse)
async def update_treatment(
    treatment_id: int,
    treatment_update: TreatmentDictUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> TreatmentDict:
    """Update a treatment in dictionary."""
    require_role(current_user, min_level=4)

    result = await db.execute(
        select(TreatmentDict).where(TreatmentDict.id == treatment_id)
    )
    treatment = result.scalar_one_or_none()

    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")

    # Check name uniqueness if name is being changed
    if treatment_update.name and treatment_update.name != treatment.name:
        existing = await db.execute(
            select(TreatmentDict).where(TreatmentDict.name == treatment_update.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Treatment with this name already exists")

    # Update fields
    update_data = treatment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(treatment, field, value)

    await db.commit()
    await db.refresh(treatment)

    return treatment


@router.delete("/{treatment_id}")
async def delete_treatment(
    treatment_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete (deactivate) a treatment from dictionary."""
    require_role(current_user, min_level=4)

    result = await db.execute(
        select(TreatmentDict).where(TreatmentDict.id == treatment_id)
    )
    treatment = result.scalar_one_or_none()

    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")

    # Soft delete by deactivating
    treatment.is_active = False
    await db.commit()

    return {"message": "Treatment deactivated successfully"}
