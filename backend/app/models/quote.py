"""Quote and QuoteItem models for sales quotation management."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.customer import Customer
    from src.models.user import User


class NominationStatus(str, PyEnum):
    """Nomination (fix) status enumeration."""

    UNFIXED = "unfixed"  # Not yet fixed
    FIXED = "fixed"  # Fixed (confirmed nomination)
    REVOKED = "revoked"  # Fix revoked by operator


class QuoteState(str, PyEnum):
    """Quote status enumeration (mirrors state machine)."""

    WAITING_FOR_TECH = "waiting_for_tech"  # 等待技术部填写T/W/P
    TECH_REVIEW = "tech_review"  # 技术审核中（已提交审核）
    TECH_APPROVED = "tech_approved"  # 技术审核通过，等待业务填写价格
    TECH_REJECTED = "tech_rejected"  # 技术部驳回
    DRAFT = "draft"  # 业务填写价格
    PENDING_BOSS = "pending_boss"  # 待老板审批
    APPROVED = "approved"  # 老板审批通过
    REJECTED = "rejected"  # 老板驳回
    FIXED = "fixed"  # 定点确认
    CANCELLED = "cancelled"


class MoldFeeMode(str, PyEnum):
    """Mold fee charging mode."""

    DIRECT = "direct"  # Direct charge
    AMORTIZED = "amortized"  # Amortized into unit price


class FixPath(str, PyEnum):
    """Customer fixation path after approval."""

    DIRECT_PRODUCTION = "direct_production"  # Direct mass production
    SAMPLE_FIRST = "sample_first"  # Sample production first


class Quote(Base):
    """Quote (quotation) model for customer pricing."""

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # Customer relationship
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    customer: Mapped["Customer"] = relationship("Customer", back_populates="quotes")

    # Creator
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id])

    # Quote status
    state: Mapped[QuoteState] = mapped_column(
        Enum(QuoteState), default=QuoteState.DRAFT, nullable=False, index=True
    )

    # Annual usage estimates
    annual_usage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_avg_usage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # --- Technical parameters (filled by tech engineer) ---
    thickness_t: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    width_w: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    press_p: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tonnage: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Mold fee
    mold_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    mold_fee_mode: Mapped[Optional[MoldFeeMode]] = mapped_column(
        Enum(MoldFeeMode), nullable=True
    )
    mold_fee_discount: Mapped[Optional[float]] = mapped_column(
        default=0.0
    )  # 0.0~1.0 discount rate

    # --- Pricing (filled by sales) ---
    stamping_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    surface_treatment_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    profit_margin: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )  # percentage

    # --- Price snapshot (locked after boss approval) ---
    price_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # --- Final price (locked after fix) ---
    final_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # --- Nomination (fix) status ---
    nomination_status: Mapped[NominationStatus] = mapped_column(
        Enum(NominationStatus), default=NominationStatus.UNFIXED, nullable=False, index=True
    )

    # --- Fix revocation tracking ---
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Revoked by (relationship, placed after revoked_by FK column)
    revoker: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by])

    # Fixation path
    fix_path: Mapped[Optional[FixPath]] = mapped_column(
        Enum(FixPath), nullable=True
    )

    # --- Rejection tracking ---
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tech_reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- State transition tracking ---
    submitted_for_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    tech_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_to_boss_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    boss_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fixed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    items: Mapped[list["QuoteItem"]] = relationship(
        "QuoteItem", back_populates="quote", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Quote {self.quote_no}>"


class QuoteItem(Base):
    """Quote item for individual parts in a quote."""

    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote: Mapped["Quote"] = relationship("Quote", back_populates="items")

    # Part identification
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_part_no: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Drawing reference
    drawing_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Technical specs for this item
    material: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thickness: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    width: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    # Unit pricing
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    moq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Minimum order qty
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<QuoteItem {self.part_name}>"


class SurfaceTreatment(Base):
    """Surface treatment record for multi-stage coating."""

    __tablename__ = "surface_treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quote_items.id", ondelete="CASCADE"), nullable=True, index=True
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<SurfaceTreatment {self.name}>"
