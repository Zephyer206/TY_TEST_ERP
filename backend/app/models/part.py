"""Part model for manufacturing parts."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.price import PriceAccount
    from app.models.production import ProductionPlan
    from app.models.quote import Quote
    from app.models.sampling import SamplingTask
    from app.models.user import User


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
    part_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    internal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Customer relationship
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Drawing and spec
    drawing_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    spec_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # State
    status: Mapped[str] = mapped_column(
        String(50), default='待开发', nullable=True, index=True
    )
    part_status: Mapped[str] = mapped_column(
        String(50), default='DRAFT', nullable=False
    )
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    # Spray status
    spray_status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)
    spray_stamped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Part identity
    customer_product_no: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Material
    material_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Nomination
    nomination_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nomination_attachment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    nomination_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nomination_confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Sample judgment
    sample_judgment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Version
    version: Mapped[str] = mapped_column(String(50), default='V1.0', nullable=False)

    # Stock
    stock_pcs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(String(500), default='', nullable=True)

    # Mold info
    mold_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mold_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    press_tonnage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ppap_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    def __repr__(self) -> str:
        return f"<Part {self.part_number}>"
