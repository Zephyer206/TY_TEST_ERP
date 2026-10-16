"""Tooling (mold/die) and tooling maintenance models."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.machine import Machine


class ToolingState(str, PyEnum):
    """Tooling/mold status."""

    AVAILABLE = "available"  # Available for use
    IN_USE = "in_use"  # Currently mounted on a machine
    MAINTENANCE = "maintenance"  # Under repair
    CONVERTED = "converted"  # Modified/rebuilt
    SCRAPPED = "scrapped"  # Written off


class ToolingMaintenanceLog(Base):
    """Tooling maintenance log for tracking repairs."""

    __tablename__ = "tooling_maintenance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Machine that reported the fault
    machine_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Fault info
    fault_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fault_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Repair info
    repair_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repair_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    repair_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    repair_completed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    tooling: Mapped["Tooling"] = relationship("Tooling", back_populates="maintenance_logs")

    def __repr__(self) -> str:
        return f"<ToolingMaintenanceLog {self.id}>"


class Tooling(Base):
    """Tooling (mold/die) model - 匹配实际数据库结构."""

    __tablename__ = "tooling"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 基本信息
    tooling_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    tooling_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 模具信息
    mold_type: Mapped[str] = mapped_column(String(50), nullable=False, default='unknown')
    is_continuous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cavity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    process_step_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='DRAFT')

    # 材料和规格
    material: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    material_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spec_twph: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 压机和工艺
    press_tonnage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 多产品相关
    is_multi_product: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    product_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 其他
    ppap_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 生产统计
    shot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_shot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_maintenance_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 时间戳
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)

    maintenance_logs: Mapped[list[ToolingMaintenanceLog]] = relationship(
        "ToolingMaintenanceLog", back_populates="tooling", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tooling {self.tooling_number}>"


class ToolingPart(Base):
    """Association table between tooling and parts."""

    __tablename__ = "tooling_parts"
    __table_args__ = (
        UniqueConstraint("tooling_id", "part_id", "position", name="uq_tooling_parts_business_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
