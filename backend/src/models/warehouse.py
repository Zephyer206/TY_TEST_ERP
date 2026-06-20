"""Warehouse and material batch models for inventory management."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class MaterialStatus(str, PyEnum):
    """Material batch status."""

    PENDING_IQC = "pending_iqc"  # Awaiting incoming quality check
    AVAILABLE = "available"  # Passed IQC, available for use
    IN_USE = "in_use"  # Currently allocated to production
    CONSUMED = "consumed"  # Fully consumed
    REJECTED = "rejected"  # Failed IQC
    SCRAPPED = "scrapped"  # Scrapped manually
    SPLIT = "split"  # Split into children


class IQCResult(str, PyEnum):
    """Incoming quality check result."""

    PASS = "pass"  # Passed IQC
    FAIL = "fail"  # Failed IQC
    CONDITIONAL = "conditional"  # Conditionally accepted


class Supplier(Base):
    """Supplier model for raw material vendors."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Contact info
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Business info
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Rating
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.code}: {self.name}>"


class MaterialBatch(Base):
    """Raw material batch model for inventory tracking."""

    __tablename__ = "material_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_no: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    qr_code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Material specs
    material_grade: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., SPCC, SECC
    material_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # coil, sheet, strip
    thickness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)  # current weight in kg
    original_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)  # original weight

    # Supplier
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True, index=True
    )
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")

    # Purchase info
    purchase_order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Dimensions after slitting
    slit_width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm
    slit_pieces: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[MaterialStatus] = mapped_column(
        Enum(MaterialStatus), default=MaterialStatus.PENDING_IQC, nullable=False, index=True
    )

    # IQC info
    iqc_result: Mapped[Optional[IQCResult]] = mapped_column(
        Enum(IQCResult), nullable=True
    )
    iqc_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    iqc_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    iqc_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parent reference (for split batches)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Location
    warehouse_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    shelf_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Consumption tracking
    consumed_qty: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    children: Mapped[list["MaterialBatch"]] = relationship(
        "MaterialBatch", back_populates="parent", foreign_keys=[parent_id]
    )
    parent: Mapped[Optional["MaterialBatch"]] = relationship(
        "MaterialBatch", remote_side=[id], back_populates="children"
    )

    def __repr__(self) -> str:
        return f"<MaterialBatch {self.batch_no}>"


class MaterialBatchChild(Base):
    """Child material batch from slitting operation."""

    __tablename__ = "material_batch_children"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_batch_no: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    qr_code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Parent reference
    parent_batch_id: Mapped[int] = mapped_column(
        ForeignKey("material_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_batch: Mapped["MaterialBatch"] = relationship("MaterialBatch")

    # Slit dimensions
    width: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    pieces: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Position in parent
    position_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status
    status: Mapped[MaterialStatus] = mapped_column(
        Enum(MaterialStatus), default=MaterialStatus.AVAILABLE, nullable=False
    )

    # Consumption
    consumed_qty: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    # Location
    warehouse_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    shelf_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<MaterialBatchChild {self.child_batch_no}>"


class MaterialConsumptionLog(Base):
    """Log for material consumption tracking."""

    __tablename__ = "material_consumption_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_batches.id"), nullable=True, index=True
    )
    child_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_batch_children.id"), nullable=True, index=True
    )

    # Consumption details
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "Production", "Sample"

    # Reference to production
    production_session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Operator
    consumed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<MaterialConsumptionLog {self.id}>"
