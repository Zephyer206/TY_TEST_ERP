"""Coating (spray painting) models for surface treatment management."""

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


class RecipeStatus(str, PyEnum):
    """Coating recipe status."""

    ACTIVE = "active"  # Currently in use
    INACTIVE = "inactive"  # Archived or discontinued
    UNDER_REVIEW = "under_review"  # Being validated


class RecordStatus(str, PyEnum):
    """Coating record status."""

    PENDING = "pending"  # Created, not started
    IN_PROGRESS = "in_progress"  # Coating in progress
    COMPLETED = "completed"  # Successfully completed
    REJECTED = "rejected"  # Failed quality check


class CoatingRecipe(Base):
    """Coating recipe for spray painting operations."""

    __tablename__ = "coating_recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Color and type
    color_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    coating_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Spray Paint", "Powder Coat"

    # Process parameters (JSON for flexibility)
    process_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {
    #   "spray_pressure": 0.5,  # MPa
    #   "spray_distance": 20,   # cm
    #   "spray_speed": 30,      # cm/s
    #   "film_thickness": 60,   # um
    #   "cure_temp": 180,       # celsius
    #   "cure_time": 30,        # minutes
    # }

    # Material consumption (per unit)
    material_consumption: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {
    #   "paint_consumption_kg": 0.05,  # kg per part
    #   "solvent_consumption_kg": 0.01,
    # }

    # Cost
    coating_cost_per_part: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Quality standards
    quality_standards: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {
    #   "thickness_min": 50,   # um
    #   "thickness_max": 80,
    #   "adhesion_test": "pass",
    # }

    # Status
    status: Mapped[RecipeStatus] = mapped_column(
        Enum(RecipeStatus), default=RecipeStatus.ACTIVE, nullable=False, index=True
    )

    # Compatible parts (JSON array of part IDs or types)
    compatible_parts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CoatingRecipe {self.recipe_no}: {self.name}>"


class CoatingRecord(Base):
    """Coating operation record for tracking spray painting work."""

    __tablename__ = "coating_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Part reference
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Recipe used
    recipe_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("coating_recipes.id"), nullable=True, index=True
    )
    recipe: Mapped[Optional["CoatingRecipe"]] = relationship("CoatingRecipe")

    # Production reference
    production_batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    process_flow_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Work order barcode (scanned)
    work_order_barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Quantities
    input_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Material consumption
    paint_used_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    solvent_used_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_consumption_per_part: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Process parameters used
    actual_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus), default=RecordStatus.PENDING, nullable=False, index=True
    )

    # Quality check
    quality_check_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quality_check_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_check_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Equipment
    equipment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    booth_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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
        return f"<CoatingRecord {self.record_no}>"


class CoatingMaterialInventory(Base):
    """Coating material inventory tracking."""

    __tablename__ = "coating_material_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Material info
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)  # paint, solvent, etc.
    material_name: Mapped[str] = mapped_column(String(200), nullable=False)
    color_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Quantity
    current_qty_kg: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="kg", nullable=False)

    # Reorder
    reorder_point_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Supplier
    supplier_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Storage location
    warehouse_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Timestamps
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CoatingMaterialInventory {self.material_name}>"
