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


# ============= 新增：价格管理系统模型 (T011-T014) =============


class TreatmentDict(Base):
    """工序字典表 - T013."""

    __tablename__ = "treatment_dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    calc_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    default_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="元/件")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TreatmentDict {self.name}>"


class CustomerMaterialPrice(Base):
    """客户材料价格历史表 - T011."""

    __tablename__ = "customer_material_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    scrap_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    quote_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    quoted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CustomerMaterialPrice {self.customer_id}-{self.material_id}>"


class CustomerTreatmentPrice(Base):
    """客户工序价格历史表 - T012."""

    __tablename__ = "customer_treatment_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    treatment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    calc_mode_snapshot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    unit_snapshot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quote_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    quoted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CustomerTreatmentPrice {self.customer_id}-{self.treatment_id}>"


class PriceAdjustment(Base):
    """价格调整审批表 - matches price_adjustments table from migration."""

    __tablename__ = "price_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    part_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    material_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    treatment_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False)  # material / treatment / part
    old_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    new_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending / approved / rejected / cancelled
    requested_by: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PriceAdjustment {self.id} {self.status}>"
