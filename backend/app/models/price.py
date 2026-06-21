"""Price models - 匹配云端数据库结构."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceAdjustmentType(str, PyEnum):
    """Price adjustment type."""

    MANUAL = "manual"  # Manual price adjustment
    ANNUAL_REDUCTION = "annual_reduction"  # Annual price reduction
    CONTRACT_RENEWAL = "contract_renewal"  # Contract renewal adjustment


class PriceAccount(Base):
    """Price account - 匹配 prices 表."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Material info
    material_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    net_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    gross_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # Pricing
    material_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    scrap_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    surface_treatment_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    cost_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    material_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # Surface treatment (JSONB)
    surface_treatment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=[])

    # Notes
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PriceAccount {self.id}>"


# 以下模型在云端数据库中不存在，暂时注释
class AnnualPriceRecord(Base):
    """Annual price record - 占位符，实际表不存在."""
    __tablename__ = "annual_price_records_placeholder"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class PriceAdjustment(Base):
    """Price adjustment - 占位符，实际表不存在."""
    __tablename__ = "price_adjustments_placeholder"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
