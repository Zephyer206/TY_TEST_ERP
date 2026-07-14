"""Customer price history API endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.price import CustomerMaterialPrice, CustomerTreatmentPrice, PriceAccount, PriceAdjustment
from app.schemas.price import (
    CustomerMaterialPriceCreate,
    CustomerMaterialPriceResponse,
    CustomerTreatmentPriceCreate,
    CustomerTreatmentPriceResponse,
)
from app.schemas.customer_price import (
    CustomerPartsWithPricesResponse,
    CustomerPartPriceInfo,
    PriceAdjustmentInfo,
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


@router.get("/customers/{customer_id}/parts-with-prices", response_model=CustomerPartsWithPricesResponse)
async def get_customer_parts_with_prices(
    customer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CustomerPartsWithPricesResponse:
    """获取指定客户的所有零件及价格信息。

    - 零件集合从 part_customer_aliases 获取（不使用废弃的 parts.customer_id）
    - 按 part_id 去重，每个零件只返回一行
    - 同一零件的多个别名聚合到 aliases 数组中
    - 价格从 prices 表左连接获取，无价格时显示"暂无价格"
    - parts_count 返回去重后的零件数量（distinct part_id count）
    - 不伪造价格数据
    """
    # Get customer
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # Query all aliases for this customer via part_customer_aliases
    # LEFT JOIN prices to include parts without price accounts
    query = (
        select(
            Part.id,
            Part.internal_name,
            PartCustomerAlias.customer_part_no,
            PartCustomerAlias.customer_part_name,
            PartCustomerAlias.revision,
            Part.material_name,
            PriceAccount.id.label('price_account_id'),
            PriceAccount.material_unit_price,
            PriceAccount.scrap_price,
            PriceAccount.surface_treatment_cost,
            PriceAccount.material_cost,
        )
        .select_from(PartCustomerAlias)
        .join(Part, PartCustomerAlias.part_id == Part.id)
        .outerjoin(
            PriceAccount,
            (PriceAccount.part_id == Part.id) & (PriceAccount.customer_id == customer_id)
        )
        .where(PartCustomerAlias.customer_id == customer_id)
        .where(PartCustomerAlias.is_active == True)
        .order_by(Part.internal_name, PartCustomerAlias.customer_part_no)
    )

    result = await db.execute(query)
    rows = result.all()

    # Group by part_id and aggregate aliases
    from collections import defaultdict
    parts_dict = defaultdict(lambda: {
        'aliases': [],
        'internal_name': None,
        'material_name': None,
        'has_price_account': False,
        'material_unit_price': None,
        'scrap_price': None,
        'surface_treatment_cost': None,
        'material_cost': None,
    })

    for row in rows:
        part_data = parts_dict[row.id]

        # Add alias
        part_data['aliases'].append({
            'customer_part_no': row.customer_part_no,
            'customer_part_name': row.customer_part_name,
            'revision': row.revision,
        })

        # Set part-level fields (same for all aliases of this part)
        if part_data['internal_name'] is None:
            part_data['internal_name'] = row.internal_name
            part_data['material_name'] = row.material_name
            part_data['has_price_account'] = row.price_account_id is not None
            part_data['material_unit_price'] = float(row.material_unit_price) if row.material_unit_price else None
            part_data['scrap_price'] = float(row.scrap_price) if row.scrap_price else None
            part_data['surface_treatment_cost'] = float(row.surface_treatment_cost) if row.surface_treatment_cost else None
            part_data['material_cost'] = float(row.material_cost) if row.material_cost else None

    # Build response list - one row per part_id
    from app.schemas.customer_price import PartAlias

    parts_list = []
    for part_id, part_data in parts_dict.items():
        # Use first alias as primary display
        first_alias = part_data['aliases'][0]

        parts_list.append(CustomerPartPriceInfo(
            part_id=part_id,
            internal_name=part_data['internal_name'],
            customer_part_no=first_alias['customer_part_no'],
            customer_part_name=first_alias['customer_part_name'],
            aliases=[PartAlias(**alias) for alias in part_data['aliases']],
            material_name=part_data['material_name'],
            has_price_account=part_data['has_price_account'],
            material_unit_price=part_data['material_unit_price'],
            scrap_price=part_data['scrap_price'],
            surface_treatment_cost=part_data['surface_treatment_cost'],
            material_cost=part_data['material_cost'],
        ))

    return CustomerPartsWithPricesResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        customer_code=customer.customer_code,
        parts_count=len(parts_list),  # Count of distinct part_ids
        parts=parts_list,
    )


@router.get("/customers/{customer_id}/parts/{part_id}/price-history", response_model=list[PriceAdjustmentInfo])
async def get_part_price_history(
    customer_id: int,
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[PriceAdjustmentInfo]:
    """获取指定客户-零件组合的调价历史。

    从 price_adjustments 表查询，无记录时返回空列表（前端显示"暂无调价记录"）。
    """
    # Verify customer and part exist
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="零件不存在")

    # Query price adjustments
    query = (
        select(PriceAdjustment)
        .where(PriceAdjustment.customer_id == customer_id)
        .where(PriceAdjustment.part_id == part_id)
        .where(PriceAdjustment.adjustment_type == 'part')
        .order_by(PriceAdjustment.requested_at.desc())
    )

    result = await db.execute(query)
    adjustments = result.scalars().all()

    return [
        PriceAdjustmentInfo(
            id=adj.id,
            adjustment_type=adj.adjustment_type,
            old_price=float(adj.old_price) if adj.old_price else None,
            new_price=float(adj.new_price),
            reason=adj.reason,
            status=adj.status,
            requested_by=adj.requested_by,
            requested_at=adj.requested_at,
            reviewed_by=adj.reviewed_by,
            reviewed_at=adj.reviewed_at,
            review_notes=adj.review_notes,
            effective_date=adj.effective_date,
        )
        for adj in adjustments
    ]
