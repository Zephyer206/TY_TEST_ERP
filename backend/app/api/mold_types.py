"""Mold Type Dictionary API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.mold_type_dict import MoldTypeDict

router = APIRouter(prefix="/mold-types", tags=["Dictionary"])


class MoldTypeCreate(BaseModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=100)
    name_en: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    typical_lifecycle: Optional[int] = None
    complexity_level: Optional[str] = Field(default=None, max_length=50)
    typical_tonnage_range: Optional[str] = Field(default=None, max_length=100)


class MoldTypeUpdate(BaseModel):
    code: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, max_length=100)
    name_en: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    typical_lifecycle: Optional[int] = None
    complexity_level: Optional[str] = Field(default=None, max_length=50)
    typical_tonnage_range: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None


class MoldTypeResponse(BaseModel):
    id: int
    code: str
    name: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    typical_lifecycle: Optional[int] = None
    complexity_level: Optional[str] = None
    typical_tonnage_range: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[MoldTypeResponse])
async def list_mold_types(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    complexity_level: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MoldTypeResponse]:
    """List mold types with optional filters."""
    q = select(MoldTypeDict)

    if search:
        q = q.where(
            (MoldTypeDict.code.ilike(f"%{search}%")) |
            (MoldTypeDict.name.ilike(f"%{search}%"))
        )
    if complexity_level:
        q = q.where(MoldTypeDict.complexity_level == complexity_level)
    if is_active is not None:
        q = q.where(MoldTypeDict.is_active == is_active)

    q = q.order_by(MoldTypeDict.sort_order, MoldTypeDict.name).offset(skip).limit(limit)
    items = (await db.execute(q)).scalars().all()
    return [MoldTypeResponse.model_validate(item) for item in items]


@router.post("", response_model=MoldTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_mold_type(
    data: MoldTypeCreate,
    db: DbSession,
    current_user: CurrentUser
) -> MoldTypeResponse:
    """Create a new mold type."""
    require_role(current_user, min_level=4)

    # Check for duplicate code
    existing = (await db.execute(
        select(MoldTypeDict).where(MoldTypeDict.code == data.code)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="模具类型代码已存在")

    item = MoldTypeDict(
        code=data.code,
        name=data.name,
        name_en=data.name_en,
        description=data.description,
        typical_lifecycle=data.typical_lifecycle,
        complexity_level=data.complexity_level,
        typical_tonnage_range=data.typical_tonnage_range,
        created_at=datetime.utcnow(),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return MoldTypeResponse.model_validate(item)


@router.get("/{item_id}", response_model=MoldTypeResponse)
async def get_mold_type(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> MoldTypeResponse:
    """Get a mold type by ID."""
    item = await db.get(MoldTypeDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="模具类型不存在")
    return MoldTypeResponse.model_validate(item)


@router.patch("/{item_id}", response_model=MoldTypeResponse)
async def update_mold_type(
    item_id: int,
    data: MoldTypeUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> MoldTypeResponse:
    """Update a mold type."""
    require_role(current_user, min_level=4)

    item = await db.get(MoldTypeDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="模具类型不存在")

    # Check for duplicate code if changing
    if data.code and data.code != item.code:
        existing = (await db.execute(
            select(MoldTypeDict).where(MoldTypeDict.code == data.code)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="模具类型代码已存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return MoldTypeResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mold_type(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> None:
    """Delete a mold type."""
    require_role(current_user, min_level=4)

    item = await db.get(MoldTypeDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="模具类型不存在")

    await db.delete(item)
    await db.commit()
