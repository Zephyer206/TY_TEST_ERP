"""Part model for manufacturing parts."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.packaging import Inventory
    from app.models.price import PriceAccount
    from app.models.production import ProductionPlan
    from app.models.quote import Quote
    from app.models.sampling import SamplingTask
    from app.models.user import User


class PartState(str, PyEnum):
    """Part production state."""

    DRAFT = "DRAFT"
    SAMPLING = "SAMPLING"  # Sample production
    MASSPRODUCTION = "MASS_PRODUCTION"
    OBSOLETE = "OBSOLETE"


class Part(Base):
    """Part (finished product) model."""

    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint(
            "is_deleted OR NULLIF(BTRIM(internal_name), '') IS NOT NULL",
            name="ck_parts_internal_name_nonempty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    internal_part_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    internal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    customer_part_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    customer_part_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    process_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    process_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # Drawing and spec
    drawing_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    spec_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # State
    # Deprecated compatibility column remains in the database during the
    # archive migration; lifecycle is governed exclusively by part_status.
    part_status: Mapped[str] = mapped_column(
        String(50), default='DRAFT', nullable=False
    )
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    # Spray status
    spray_status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)
    spray_stamped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Part identity
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Material
    material_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    material_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # TWP规格字段
    spec_twph: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thickness: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    pitch: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    height: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    gross_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    net_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    part_position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
    inventory_records: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="part",
        lazy="selectin",
    )
    remark: Mapped[Optional[str]] = mapped_column(String(500), default='', nullable=True)

    # Mold identity and type are maintained by tooling/tooling_parts.
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
        return f"<Part {self.id}: {self.internal_name}>"


class PartBOM(Base):
    """Components used to assemble a part or installation package."""

    __tablename__ = "part_BOM"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_part_bom_quantity_positive"),
        CheckConstraint("parent_part_id <> component_part_id", name="ck_part_bom_no_self_reference"),
        UniqueConstraint(
            "parent_part_id",
            "component_part_id",
            "revision",
            name="uq_part_bom_component_revision",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="个")
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[str] = mapped_column(String(50), nullable=False, default="V1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
