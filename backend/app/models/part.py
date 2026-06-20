"""Part model for manufacturing parts."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.customer import Customer
    from src.models.price import PriceAccount
    from src.models.quote import Quote
    from src.models.sampling import SamplingTask
    from src.models.user import User


class PartState(str, PyEnum):
    """Part production state."""

    DRAFT = "draft"
    SAMPLING = "sampling"  # Sample production
    MASSPRODUCTION = "mass_production"
    OBSOLETE = "obsolete"


class Part(Base):
    """Part (finished product) model."""

    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    part_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Customer relationship
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    customer: Mapped["Customer"] = relationship("Customer", back_populates="parts")
    price_accounts: Mapped[list["PriceAccount"]] = relationship(
        "PriceAccount", back_populates="part"
    )
    sampling_tasks: Mapped[list["SamplingTask"]] = relationship(
        "SamplingTask", back_populates="part"
    )

    # Quote that created this part
    quote_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quotes.id"), nullable=True, index=True
    )
    quote: Mapped[Optional["Quote"]] = relationship("Quote")

    # State
    state: Mapped[PartState] = mapped_column(
        Enum(PartState), default=PartState.DRAFT, nullable=False, index=True
    )

    # Part identity
    customer_part_no: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    drawing_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Technical specs
    material: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thickness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    net_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tonnage: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Mold info (filled at fix)
    mold_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mold_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mold_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ppap_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Pricing snapshot (locked at fix)
    price_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Stock
    stock_pcs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Drawing path
    drawing_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Part {self.part_no}>"
