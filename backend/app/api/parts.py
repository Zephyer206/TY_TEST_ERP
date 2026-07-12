"""Parts API endpoints - 匹配实际数据库字段."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.customer import Customer
from app.models.part import Part
from app.models.tooling import Tooling
from app.models.material_dict import MaterialDict
from app.schemas.part import PartCreate, PartResponse, PartUpdate

router = APIRouter(prefix="/parts", tags=["Parts"])


async def _to_resp(db, p: Part) -> PartResponse:
    customer = await db.get(Customer, p.customer_id) if p.customer_id else None
    return PartResponse(
        id=p.id,
        part_number=p.part_number,
        internal_name=p.internal_name,
        customer_id=p.customer_id,
        customer_name=customer.name if customer else None,
        customer_product_no=p.customer_product_no,
        vehicle_model=p.vehicle_model,
        material_name=p.material_name,
        part_status=p.part_status,
        stock_pcs=p.stock_pcs,
        mold_number=p.mold_number,
        mold_type=p.mold_type,
        press_tonnage=p.press_tonnage,
        ppap_no=p.ppap_no,
        remark=p.remark,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[PartResponse])
async def list_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PartResponse]:
    q = select(Part)
    if search:
        q = q.where(or_(
            Part.internal_name.ilike(f"%{search}%"),
            Part.part_number.ilike(f"%{search}%"),
            Part.mold_number.ilike(f"%{search}%"),
        ))
    if customer_id:
        q = q.where(Part.customer_id == customer_id)
    if part_status:
        q = q.where(Part.part_status == part_status)
    if material:
        q = q.where(Part.material_name.ilike(f"%{material}%"))
    q = q.order_by(Part.created_at.desc()).offset(skip).limit(limit)
    parts = (await db.execute(q)).scalars().all()

    # Batch load customers
    cust_ids = list({p.customer_id for p in parts if p.customer_id})
    customers = {}
    if cust_ids:
        customers = {c.id: c for c in (await db.execute(
            select(Customer).where(Customer.id.in_(cust_ids))
        )).scalars()}

    # Batch load tooling for cavity_count
    mold_numbers = list({p.mold_number for p in parts if p.mold_number})
    toolings = {}
    if mold_numbers:
        toolings = {t.tooling_no: t for t in (await db.execute(
            select(Tooling).where(Tooling.tooling_no.in_(mold_numbers))
        )).scalars()}

    # Batch load materials for full names
    material_ids = list({p.material_id for p in parts if p.material_id})
    materials = {}
    if material_ids:
        materials = {m.id: m for m in (await db.execute(
            select(MaterialDict).where(MaterialDict.id.in_(material_ids))
        )).scalars()}

    return [
        PartResponse(
            id=p.id, part_number=p.part_number, internal_name=p.internal_name,
            customer_id=p.customer_id,
            customer_name=customers[p.customer_id].name if p.customer_id in customers else None,
            customer_product_no=p.customer_product_no,
            customer_product_name=p.customer_product_name,
            vehicle_model=p.vehicle_model,
            material_name=p.material_name,
            material_name_full=materials[p.material_id].name if p.material_id in materials else None,
            part_status=p.part_status, stock_pcs=p.stock_pcs,
            mold_number=p.mold_number, mold_type=p.mold_type, press_tonnage=p.press_tonnage,
            ppap_no=p.ppap_no,
            spec_twph=p.spec_twph,
            thickness=p.thickness, width=p.width, pitch=p.pitch, height=p.height,
            gross_weight=p.gross_weight, net_weight=p.net_weight,
            part_position=p.part_position,
            cavity_count=str(toolings[p.mold_number].cavity_count) if p.mold_number in toolings and toolings[p.mold_number].cavity_count is not None else None,
            remark=p.remark, created_at=p.created_at, updated_at=p.updated_at,
        )
        for p in parts
    ]


@router.post("", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
async def create_part(data: PartCreate, db: DbSession, current_user: CurrentUser) -> PartResponse:
    require_role(current_user, min_level=4)
    existing = (await db.execute(select(Part).where(Part.part_number == data.part_number))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="零件编号已存在")
    part = Part(
        part_number=data.part_number,
        internal_name=data.internal_name,
        customer_id=data.customer_id,
        customer_product_no=data.customer_product_no,
        vehicle_model=data.vehicle_model,
        material_name=data.material_name,
        remark=data.remark,
        part_status="DRAFT",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return await _to_resp(db, part)


@router.get("/{part_id}", response_model=PartResponse)
async def get_part(part_id: int, db: DbSession, current_user: CurrentUser) -> PartResponse:
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return await _to_resp(db, part)


@router.patch("/{part_id}", response_model=PartResponse)
async def update_part(part_id: int, data: PartUpdate, db: DbSession, current_user: CurrentUser) -> PartResponse:
    require_role(current_user, min_level=4)
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return await _to_resp(db, part)


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part(part_id: int, db: DbSession, current_user: CurrentUser) -> None:
    require_role(current_user, min_level=4)
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    # 软删除：改状态
    part.part_status = "OBSOLETE"
    part.updated_at = datetime.utcnow()
    await db.commit()
