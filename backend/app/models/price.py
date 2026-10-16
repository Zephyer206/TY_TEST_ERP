"""Price models - 匹配云端数据库结构."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

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
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

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

    # ``price_accounts`` was the original API name.  The canonical table is
    # ``prices``; keep the annual child relation here so the old API can be
    # served without introducing a second table or a second migration chain.
    annual_records: Mapped[list["PriceYear"]] = relationship(
        "PriceYear",
        back_populates="price_account",
        cascade="all, delete-orphan",
        order_by="PriceYear.year",
    )
    part: Mapped["Part"] = relationship(
        "Part",
        primaryjoin="foreign(PriceAccount.part_id) == Part.id",
        viewonly=True,
    )
    customer: Mapped[Optional["Customer"]] = relationship(
        "Customer",
        primaryjoin="foreign(PriceAccount.customer_id) == Customer.id",
        viewonly=True,
    )

    @property
    def material(self) -> Optional[str]:
        return self.material_name

    @material.setter
    def material(self, value: Optional[str]) -> None:
        self.material_name = value

    @property
    def net_weight_kg(self) -> Optional[Decimal]:
        return self.net_weight

    @net_weight_kg.setter
    def net_weight_kg(self, value: Optional[Decimal]) -> None:
        self.net_weight = value

    @property
    def gross_weight_kg(self) -> Optional[Decimal]:
        return self.gross_weight

    @gross_weight_kg.setter
    def gross_weight_kg(self, value: Optional[Decimal]) -> None:
        self.gross_weight = value

    @property
    def notes(self) -> Optional[str]:
        return self.remark

    @notes.setter
    def notes(self, value: Optional[str]) -> None:
        self.remark = value

    @property
    def reduction_pct(self) -> Decimal:
        # Annual reduction is a separate legacy table and is not part of the
        # canonical ``prices`` row.  Zero is the truthful compatibility value.
        return getattr(self, "_legacy_reduction_pct", Decimal("0"))

    @reduction_pct.setter
    def reduction_pct(self, value: Decimal) -> None:
        self._legacy_reduction_pct = Decimal(str(value))

    @property
    def base_price(self) -> Optional[Decimal]:
        return (
            getattr(self, "_legacy_base_price", None)
            or self.cost_override
            or self.material_cost
            or self.material_unit_price
        )

    @base_price.setter
    def base_price(self, value: Optional[Decimal]) -> None:
        self._legacy_base_price = value

    @property
    def current_price(self) -> Optional[Decimal]:
        if self.annual_records:
            return self.annual_records[-1].unit_price
        return getattr(self, "_legacy_current_price", None) or self.base_price

    @current_price.setter
    def current_price(self, value: Optional[Decimal]) -> None:
        self._legacy_current_price = value

    @property
    def price_year(self) -> Optional[int]:
        return self.annual_records[-1].year if self.annual_records else getattr(self, "_legacy_price_year", None)

    @price_year.setter
    def price_year(self, value: Optional[int]) -> None:
        self._legacy_price_year = value

    @property
    def is_active(self) -> bool:
        return getattr(self, "_legacy_is_active", True)

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._legacy_is_active = value

    @property
    def adjustments(self) -> list:
        """Transient legacy field; approval history is served separately."""
        return getattr(self, "_legacy_adjustments", [])

    @adjustments.setter
    def adjustments(self, value: list) -> None:
        self._legacy_adjustments = value

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

    @property
    def price_account_id(self) -> Optional[int]:
        return getattr(self, "_price_account_id", None)

    @price_account_id.setter
    def price_account_id(self, value: int) -> None:
        self._price_account_id = value

    @property
    def created_by(self) -> int:
        return self.requested_by

    @property
    def adjustment_reason(self) -> Optional[str]:
        return self.reason

    def __repr__(self) -> str:
        return f"<PriceAdjustment {self.id} {self.status}>"


class PriceYear(Base):
    """年度价格表 - maps price_years table."""

    __tablename__ = "price_years"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_id: Mapped[int] = mapped_column(
        ForeignKey("prices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    annual_sales: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    price_account: Mapped[PriceAccount] = relationship(
        "PriceAccount", back_populates="annual_records"
    )

    @property
    def price_account_id(self) -> int:
        return self.price_id

    @price_account_id.setter
    def price_account_id(self, value: int) -> None:
        self.price_id = value

    @property
    def annual_qty(self) -> Optional[int]:
        return self.annual_sales

    @annual_qty.setter
    def annual_qty(self, value: Optional[int]) -> None:
        self.annual_sales = value

    @property
    def notes(self) -> Optional[str]:
        return getattr(self, "_legacy_notes", None)

    @notes.setter
    def notes(self, value: Optional[str]) -> None:
        self._legacy_notes = value

    @property
    def created_by(self) -> Optional[int]:
        return self.operator_id

    @created_by.setter
    def created_by(self, value: Optional[int]) -> None:
        self.operator_id = value

    @property
    def created_at(self) -> datetime:
        return getattr(self, "_legacy_created_at", None) or self.updated_at

    @created_at.setter
    def created_at(self, value: datetime) -> None:
        self._legacy_created_at = value

    def __repr__(self) -> str:
        return f"<PriceYear {self.price_id}-{self.year}>"
