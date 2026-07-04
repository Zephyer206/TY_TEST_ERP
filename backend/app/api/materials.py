"""Material Dictionary API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.material_dict import MaterialDict

router = APIRouter(prefix="/materials", tags=["Dictionary"])


class MaterialCreate(BaseModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=100)
    name_cn: Optional[str] = Field(default=None, max_length=100)
    density: Optional[float] = None
    thickness_range: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=50)
    standard: Optional[str] = Field(default=None, max_length=100)
    default_price: Optional[float] = None
    scrap_price: Optional[float] = None


class MaterialUpdate(BaseModel):
    code: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, max_length=100)
    name_cn: Optional[str] = Field(default=None, max_length=100)
    density: Optional[float] = None
    thickness_range: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=50)
    standard: Optional[str] = Field(default=None, max_length=100)
    default_price: Optional[float] = None
    scrap_price: Optional[float] = None
    is_active: Optional[bool] = None


class MaterialResponse(BaseModel):
    id: int
    code: str
    name: str
    name_cn: Optional[str] = None
    density: Optional[float] = None
    thickness_range: Optional[str] = None
    category: Optional[str] = None
    standard: Optional[str] = None
    default_price: Optional[float] = None
    scrap_price: Optional[float] = None
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[MaterialResponse])
async def list_materials(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MaterialResponse]:
    """List materials with optional filters."""
    q = select(MaterialDict)

    if search:
        q = q.where(
            (MaterialDict.code.ilike(f"%{search}%")) |
            (MaterialDict.name.ilike(f"%{search}%")) |
            (MaterialDict.name_cn.ilike(f"%{search}%"))
        )
    if category:
        q = q.where(MaterialDict.category == category)
    if is_active is not None:
        q = q.where(MaterialDict.is_active == is_active)

    q = q.order_by(MaterialDict.sort_order, MaterialDict.code).offset(skip).limit(limit)
    items = (await db.execute(q)).scalars().all()
    return [MaterialResponse.model_validate(item) for item in items]


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: MaterialCreate,
    db: DbSession,
    current_user: CurrentUser
) -> MaterialResponse:
    """Create a new material."""
    require_role(current_user, min_level=4)

    # Check for duplicate code
    existing = (await db.execute(
        select(MaterialDict).where(MaterialDict.code == data.code)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="材质代码已存在")

    item = MaterialDict(
        code=data.code,
        name=data.name,
        name_cn=data.name_cn,
        density=data.density,
        thickness_range=data.thickness_range,
        category=data.category,
        standard=data.standard,
        default_price=data.default_price,
        scrap_price=data.scrap_price,
        created_at=datetime.utcnow(),
        created_by=current_user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return MaterialResponse.model_validate(item)


@router.get("/{item_id}", response_model=MaterialResponse)
async def get_material(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> MaterialResponse:
    """Get a material by ID."""
    item = await db.get(MaterialDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="材质不存在")
    return MaterialResponse.model_validate(item)


@router.patch("/{item_id}", response_model=MaterialResponse)
async def update_material(
    item_id: int,
    data: MaterialUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> MaterialResponse:
    """Update a material."""
    require_role(current_user, min_level=4)

    item = await db.get(MaterialDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="材质不存在")

    # Check for duplicate code if changing
    if data.code and data.code != item.code:
        existing = (await db.execute(
            select(MaterialDict).where(MaterialDict.code == data.code)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="材质代码已存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return MaterialResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> None:
    """Delete a material."""
    require_role(current_user, min_level=4)

    item = await db.get(MaterialDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="材质不存在")

    await db.delete(item)
    await db.commit()
