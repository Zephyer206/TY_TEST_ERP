"""Packaging and shipping models."""

from datetime import datetime
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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.part import Part
    from app.models.user import User


class PackagingStatus(str, PyEnum):
    """Packaging record status."""

    SCANNED = "scanned"  # Just scanned, pending inspection
    INSPECTING = "inspecting"  # Under inspection
    PASSED = "passed"  # Passed inspection, in stock
    REJECTED = "rejected"  # Failed inspection
    SHIPPED = "shipped"  # Already shipped
    RETURNED = "returned"  # Returned


class InspectionResult(str, PyEnum):
    """Visual inspection result."""

    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"


class PackagingRecord(Base):
    """Packaging record for tracking finished goods."""

    __tablename__ = "packaging_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Product lot info
    production_batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    process_flow_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Packaging details
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    packaging_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # box, pallet, etc.
    box_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Box barcode (scanned)
    box_barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Weight
    gross_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status
    status: Mapped[PackagingStatus] = mapped_column(
        Enum(PackagingStatus), default=PackagingStatus.SCANNED, nullable=False, index=True
    )

    # Visual inspection result
    visual_inspection_result: Mapped[Optional[InspectionResult]] = mapped_column(
        Enum(InspectionResult), nullable=True
    )
    visual_inspection_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    visual_inspection_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Inspection details
    inspected_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    passed_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rejected_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspection_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stock info
    warehouse_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    shelf_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Shipping info
    shipment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    shipped_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Operator
    scanned_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PackagingRecord {self.record_no}>"


class FinishedGoodsInventory(Base):
    """Finished goods inventory tracking."""

    __tablename__ = "finished_goods_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Location
    warehouse_location: Mapped[str] = mapped_column(String(200), nullable=False)
    shelf_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Inventory quantity
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Batch tracking
    latest_batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    latest_production_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<FinishedGoodsInventory part={self.part_id} loc={self.warehouse_location}>"


class InventoryTransaction(Base):
    """Inventory transaction log."""

    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Transaction type
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Types: STOCK_IN, STOCK_OUT, ADJUSTMENT, TRANSFER

    # Quantities
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference documents
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Location
    warehouse_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Operator
    operated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<InventoryTransaction {self.transaction_no}>"
