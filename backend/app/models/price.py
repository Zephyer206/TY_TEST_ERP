"""Price account, annual price record, and price adjustment models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.part import Part
    from app.models.user import User


class PriceAdjustmentType(str, PyEnum):
    """Price adjustment type."""

    MANUAL = "manual"  # Manual price adjustment
    ANNUAL_REDUCTION = "annual_reduction"  # Annual price reduction
    CONTRACT_RENEWAL = "contract_renewal"  # Contract renewal adjustment


class PriceAccount(Base):
    """Price account for a specific part + customer combination."""

    __tablename__ = "price_accounts"
    __table_args__ = (
        UniqueConstraint("part_id", "customer_id", name="uq_part_customer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part", back_populates="price_accounts")
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    customer: Mapped["Customer"] = relationship("Customer")

    # Basic pricing info
    material: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    net_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    material_unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    scrap_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )  # 废料价

    # Annual reduction settings
    base_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )  # 基价（首次定点价格）
    reduction_pct: Mapped[float] = mapped_column(
        Numeric(5, 4), default=0.0
    )  # 年降比例 0.0~1.0

    # Current computed price
    current_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    price_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    annual_records: Mapped[list["AnnualPriceRecord"]] = relationship(
        "AnnualPriceRecord", back_populates="price_account", cascade="all, delete-orphan"
    )
    adjustments: Mapped[list["PriceAdjustment"]] = relationship(
        "PriceAdjustment", back_populates="price_account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PriceAccount {self.id}>"


class AnnualPriceRecord(Base):
    """Annual price record for a price account."""

    __tablename__ = "annual_price_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    price_account_id: Mapped[int] = mapped_column(
        ForeignKey("price_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_account: Mapped["PriceAccount"] = relationship(
        "PriceAccount", back_populates="annual_records"
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    annual_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 年销量
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    creator: Mapped[Optional["User"]] = relationship("User")

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AnnualPriceRecord {self.year}: {self.unit_price}>"


class PriceAdjustment(Base):
    """Manual price adjustment log."""

    __tablename__ = "price_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    price_account_id: Mapped[int] = mapped_column(
        ForeignKey("price_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_account: Mapped["PriceAccount"] = relationship(
        "PriceAccount", back_populates="adjustments"
    )

    old_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    adjustment_type: Mapped[PriceAdjustmentType] = mapped_column(
        Enum(PriceAdjustmentType), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    creator: Mapped["User"] = relationship("User")

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PriceAdjustment {self.old_price} -> {self.new_price}>"
