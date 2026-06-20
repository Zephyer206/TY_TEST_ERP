"""Coating (spray painting) management models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.part import Part


class CoatingType(str, PyEnum):
    """Coating type."""

    POWDER = "powder"  # 粉末喷涂
    LIQUID = "liquid"  # 液体喷涂
    ELECTROPHORETIC = "electrophoretic"  # 电泳


class CoatingColor(str, PyEnum):
    """Coating color type."""

    WHITE = "white"
    BLACK = "black"
    GRAY = "gray"
    SILVER = "silver"
    CUSTOM = "custom"


class CoatingRecipe(Base):
    """Coating recipe model for managing spray painting formulas."""

    __tablename__ = "coating_recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Coating type
    coating_type: Mapped[CoatingType] = mapped_column(
        Enum(CoatingType), nullable=False
    )

    # Color
    color_type: Mapped[CoatingColor] = mapped_column(
        Enum(CoatingColor), default=CoatingColor.CUSTOM, nullable=False
    )
    color_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Recipe parameters
    primer_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    primer_thickness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # μm
    topcoat_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    topcoat_thickness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # μm

    # Process parameters
    spray_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # bar
    spray_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm
    spray_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mm/s
    curing_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # °C
    curing_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # minutes

    # Material consumption (per part)
    material_consumption: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg per part

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CoatingRecipe {self.recipe_no}>"


class CoatingRecord(Base):
    """Coating production record model."""

    __tablename__ = "coating_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Recipe used
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("coating_recipes.id"), nullable=False, index=True
    )
    recipe: Mapped["CoatingRecipe"] = relationship("CoatingRecipe")

    # Part processed
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, index=True
    )
    part: Mapped["Part"] = relationship("Part")

    # Production details
    processed_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    qualified_qty: Mapped[int] = mapped_column(Integer, nullable=False)  # 合格数量
    rejected_qty: Mapped[int] = mapped_column(Integer, default=0)  # 返工/报废数量

    # Material consumption
    material_used: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # kg

    # Operator
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Batch reference (for material traceability)
    batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    coating_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CoatingRecord {self.record_no}>"
