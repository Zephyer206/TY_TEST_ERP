"""Customer price service - 客户价格历史查询服务."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import CustomerMaterialPrice, CustomerTreatmentPrice, TreatmentDict
from app.schemas.price import (
    CustomerMaterialPriceCreate,
    CustomerMaterialPriceResponse,
    CustomerTreatmentPriceCreate,
    CustomerTreatmentPriceResponse,
)


class CustomerPriceService:
    """客户价格历史服务."""

    @staticmethod
    async def get_material_price_history(
        db: AsyncSession,
        customer_id: int,
        material_id: int,
        limit: int = 3,
    ) -> list[CustomerMaterialPriceResponse]:
        """查询客户材料价格历史（最近 N 条）- US1."""
        query = (
            select(CustomerMaterialPrice)
            .where(
                CustomerMaterialPrice.customer_id == customer_id,
                CustomerMaterialPrice.material_id == material_id,
            )
            .order_by(desc(CustomerMaterialPrice.quoted_at))
            .limit(limit)
        )

        result = await db.execute(query)
        prices = result.scalars().all()

        return [CustomerMaterialPriceResponse.model_validate(p) for p in prices]

    @staticmethod
    async def get_material_suggested_price(
        db: AsyncSession,
        material_id: int,
    ) -> Optional[Decimal]:
        """获取材料字典中的默认价格（兜底值）- US1."""
        from app.models.material_dict import MaterialDict

        query = select(MaterialDict).where(MaterialDict.id == material_id)
        result = await db.execute(query)
        material = result.scalar_one_or_none()

        return material.default_price if material else None

    @staticmethod
    async def create_material_price(
        db: AsyncSession,
        data: CustomerMaterialPriceCreate,
        created_by: Optional[int] = None,
    ) -> CustomerMaterialPriceResponse:
        """创建客户材料价格历史记录 - US2."""
        price = CustomerMaterialPrice(
            customer_id=data.customer_id,
            material_id=data.material_id,
            unit_price=data.unit_price,
            scrap_price=data.scrap_price,
            quote_id=data.quote_id,
            quoted_at=datetime.utcnow(),
            created_by=created_by,
        )

        db.add(price)
        await db.flush()
        await db.refresh(price)

        return CustomerMaterialPriceResponse.model_validate(price)

    @staticmethod
    async def get_treatment_price_history(
        db: AsyncSession,
        customer_id: int,
        treatment_id: int,
        limit: int = 3,
    ) -> list[CustomerTreatmentPriceResponse]:
        """查询客户工序价格历史（最近 N 条）- US3."""
        query = (
            select(CustomerTreatmentPrice)
            .where(
                CustomerTreatmentPrice.customer_id == customer_id,
                CustomerTreatmentPrice.treatment_id == treatment_id,
            )
            .order_by(desc(CustomerTreatmentPrice.quoted_at))
            .limit(limit)
        )

        result = await db.execute(query)
        prices = result.scalars().all()

        return [CustomerTreatmentPriceResponse.model_validate(p) for p in prices]

    @staticmethod
    async def get_treatment_suggested_price(
        db: AsyncSession,
        treatment_id: int,
    ) -> Optional[dict]:
        """获取工序字典中的默认费率（兜底值）- US3."""
        query = select(TreatmentDict).where(TreatmentDict.id == treatment_id)
        result = await db.execute(query)
        treatment = result.scalar_one_or_none()

        if not treatment:
            return None

        return {
            "default_rate": treatment.default_rate,
            "calc_mode": treatment.calc_mode,
            "unit": treatment.unit,
        }

    @staticmethod
    async def create_treatment_price(
        db: AsyncSession,
        data: CustomerTreatmentPriceCreate,
        created_by: Optional[int] = None,
    ) -> CustomerTreatmentPriceResponse:
        """创建客户工序价格历史记录 - US4."""
        price = CustomerTreatmentPrice(
            customer_id=data.customer_id,
            treatment_id=data.treatment_id,
            unit_price=data.unit_price,
            calc_mode_snapshot=data.calc_mode_snapshot,
            unit_snapshot=data.unit_snapshot,
            quote_id=data.quote_id,
            quoted_at=datetime.utcnow(),
            created_by=created_by,
        )

        db.add(price)
        await db.flush()
        await db.refresh(price)

        return CustomerTreatmentPriceResponse.model_validate(price)
