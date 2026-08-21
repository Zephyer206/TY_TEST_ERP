"""Machine Tonnage Dictionary API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.machine_tonnage_dict import MachineTonnageDict

router = APIRouter(prefix="/machine-tonnages", tags=["Dictionary"])


class MachineTonnageCreate(BaseModel):
    tonnage: int
    machine_type: str = Field(max_length=50)
    display_name: str = Field(max_length=100)
    size_category: Optional[str] = Field(default=None, max_length=50)
    type_category: Optional[str] = Field(default=None, max_length=50)
    min_stroke: Optional[int] = None
    max_stroke: Optional[int] = None
    work_table_size: Optional[str] = Field(default=None, max_length=100)


class MachineTonnageUpdate(BaseModel):
    tonnage: Optional[int] = None
    machine_type: Optional[str] = Field(default=None, max_length=50)
    display_name: Optional[str] = Field(default=None, max_length=100)
    size_category: Optional[str] = Field(default=None, max_length=50)
    type_category: Optional[str] = Field(default=None, max_length=50)
    min_stroke: Optional[int] = None
    max_stroke: Optional[int] = None
    work_table_size: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None


class MachineTonnageResponse(BaseModel):
    id: int
    tonnage: int
    machine_type: str
    display_name: str
    size_category: Optional[str] = None
    type_category: Optional[str] = None
    min_stroke: Optional[int] = None
    max_stroke: Optional[int] = None
    work_table_size: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[MachineTonnageResponse])
async def list_machine_tonnages(
    db: DbSession,
    current_user: CurrentUser,
    tonnage: Optional[int] = Query(default=None),
    machine_type: Optional[str] = Query(default=None),
    size_category: Optional[str] = Query(default=None),
    type_category: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MachineTonnageResponse]:
    """List machine tonnages with optional filters."""
    q = select(MachineTonnageDict)

    if tonnage is not None:
        q = q.where(MachineTonnageDict.tonnage == tonnage)
    if machine_type:
        q = q.where(MachineTonnageDict.machine_type == machine_type)
    if size_category:
        q = q.where(MachineTonnageDict.size_category == size_category)
    if type_category:
        q = q.where(MachineTonnageDict.type_category == type_category)
    if is_active is not None:
        q = q.where(MachineTonnageDict.is_active == is_active)

    q = q.order_by(MachineTonnageDict.sort_order, MachineTonnageDict.tonnage).offset(skip).limit(limit)
    items = (await db.execute(q)).scalars().all()
    return [MachineTonnageResponse.model_validate(item) for item in items]


@router.post("", response_model=MachineTonnageResponse, status_code=status.HTTP_201_CREATED)
async def create_machine_tonnage(
    data: MachineTonnageCreate,
    db: DbSession,
    current_user: CurrentUser
) -> MachineTonnageResponse:
    """Create a new machine tonnage."""
    require_role(current_user, min_level=2)

    # Check for duplicate combination
    existing = (await db.execute(
        select(MachineTonnageDict).where(
            (MachineTonnageDict.tonnage == data.tonnage) &
            (MachineTonnageDict.machine_type == data.machine_type)
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="该机台吨位组合已存在")

    item = MachineTonnageDict(
        tonnage=data.tonnage,
        machine_type=data.machine_type,
        display_name=data.display_name,
        size_category=data.size_category,
        type_category=data.type_category,
        min_stroke=data.min_stroke,
        max_stroke=data.max_stroke,
        work_table_size=data.work_table_size,
        created_at=datetime.utcnow(),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return MachineTonnageResponse.model_validate(item)


@router.get("/{item_id}", response_model=MachineTonnageResponse)
async def get_machine_tonnage(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> MachineTonnageResponse:
    """Get a machine tonnage by ID."""
    item = await db.get(MachineTonnageDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="机台吨位不存在")
    return MachineTonnageResponse.model_validate(item)


@router.patch("/{item_id}", response_model=MachineTonnageResponse)
async def update_machine_tonnage(
    item_id: int,
    data: MachineTonnageUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> MachineTonnageResponse:
    """Update a machine tonnage."""
    require_role(current_user, min_level=2)

    item = await db.get(MachineTonnageDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="机台吨位不存在")

    # Check for duplicate if changing tonnage or machine_type
    if (data.tonnage or data.machine_type):
        new_tonnage = data.tonnage if data.tonnage is not None else item.tonnage
        new_machine_type = data.machine_type if data.machine_type else item.machine_type

        if new_tonnage != item.tonnage or new_machine_type != item.machine_type:
            existing = (await db.execute(
                select(MachineTonnageDict).where(
                    (MachineTonnageDict.tonnage == new_tonnage) &
                    (MachineTonnageDict.machine_type == new_machine_type) &
                    (MachineTonnageDict.id != item_id)
                )
            )).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="该机台吨位组合已存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return MachineTonnageResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine_tonnage(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> None:
    """Delete a machine tonnage."""
    require_role(current_user, min_level=2)

    item = await db.get(MachineTonnageDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="机台吨位不存在")

    await db.delete(item)
    await db.commit()
