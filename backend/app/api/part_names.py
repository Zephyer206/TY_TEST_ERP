"""Part Name Dictionary API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.part_name_dict import PartNameDict

router = APIRouter(prefix="/part-names", tags=["Dictionary"])


class PartNameCreate(BaseModel):
    primary_category: str = Field(max_length=100, description="一级分类（必填）")
    secondary_category: Optional[str] = Field(default=None, max_length=100, description="二级分类（可选）")
    customer_part_name: Optional[str] = Field(default=None, max_length=200, description="三级分类-客户零件名称（可选）")
    remark: Optional[str] = Field(default=None, description="备注说明")


class PartNameUpdate(BaseModel):
    primary_category: Optional[str] = Field(default=None, max_length=100)
    secondary_category: Optional[str] = Field(default=None, max_length=100)
    customer_part_name: Optional[str] = Field(default=None, max_length=200)
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class PartNameResponse(BaseModel):
    id: int
    primary_category: str
    secondary_category: Optional[str] = None
    customer_part_name: Optional[str] = None
    remark: Optional[str] = None
    usage_count: int
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[PartNameResponse])
async def list_part_names(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    primary_category: Optional[str] = Query(default=None),
    secondary_category: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PartNameResponse]:
    """List part names with optional filters."""
    q = select(PartNameDict)

    if search:
        q = q.where(
            (PartNameDict.primary_category.ilike(f"%{search}%")) |
            (PartNameDict.secondary_category.ilike(f"%{search}%")) |
            (PartNameDict.customer_part_name.ilike(f"%{search}%"))
        )
    if primary_category:
        q = q.where(PartNameDict.primary_category == primary_category)
    if secondary_category:
        q = q.where(PartNameDict.secondary_category == secondary_category)
    if is_active is not None:
        q = q.where(PartNameDict.is_active == is_active)

    q = q.order_by(PartNameDict.primary_category, PartNameDict.secondary_category, PartNameDict.customer_part_name).offset(skip).limit(limit)
    items = (await db.execute(q)).scalars().all()
    return [PartNameResponse.model_validate(item) for item in items]


@router.post("", response_model=PartNameResponse, status_code=status.HTTP_201_CREATED)
async def create_part_name(
    data: PartNameCreate,
    db: DbSession,
    current_user: CurrentUser
) -> PartNameResponse:
    """Create a new part name."""
    require_role(current_user, min_level=2)

    # Check for duplicate (same primary, secondary, customer combination)
    existing = (await db.execute(
        select(PartNameDict).where(
            PartNameDict.primary_category == data.primary_category,
            PartNameDict.secondary_category == data.secondary_category,
            PartNameDict.customer_part_name == data.customer_part_name
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="相同的零件名称组合已存在")

    item = PartNameDict(
        primary_category=data.primary_category,
        secondary_category=data.secondary_category,
        customer_part_name=data.customer_part_name,
        remark=data.remark,
        created_at=datetime.utcnow(),
        created_by=current_user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return PartNameResponse.model_validate(item)


@router.get("/{item_id}", response_model=PartNameResponse)
async def get_part_name(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> PartNameResponse:
    """Get a part name by ID."""
    item = await db.get(PartNameDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="零件名称不存在")
    return PartNameResponse.model_validate(item)


@router.patch("/{item_id}", response_model=PartNameResponse)
async def update_part_name(
    item_id: int,
    data: PartNameUpdate,
    db: DbSession,
    current_user: CurrentUser
) -> PartNameResponse:
    """Update a part name."""
    require_role(current_user, min_level=2)

    item = await db.get(PartNameDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="零件名称不存在")

    # Check for duplicate if changing key fields
    update_dict = data.model_dump(exclude_unset=True)
    if any(k in update_dict for k in ['primary_category', 'secondary_category', 'customer_part_name']):
        check_primary = update_dict.get('primary_category', item.primary_category)
        check_secondary = update_dict.get('secondary_category', item.secondary_category)
        check_customer = update_dict.get('customer_part_name', item.customer_part_name)

        existing = (await db.execute(
            select(PartNameDict).where(
                PartNameDict.id != item_id,
                PartNameDict.primary_category == check_primary,
                PartNameDict.secondary_category == check_secondary,
                PartNameDict.customer_part_name == check_customer
            )
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="相同的零件名称组合已存在")

    for field, value in update_dict.items():
        setattr(item, field, value)

    item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return PartNameResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part_name(
    item_id: int,
    db: DbSession,
    current_user: CurrentUser
) -> None:
    """Delete a part name."""
    require_role(current_user, min_level=2)

    item = await db.get(PartNameDict, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="零件名称不存在")

    # Check if in use
    if item.usage_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该零件名称正在被 {item.usage_count} 条记录使用，无法删除"
        )

    await db.delete(item)
    await db.commit()

