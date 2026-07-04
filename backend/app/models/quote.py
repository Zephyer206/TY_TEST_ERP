"""Quote model - 匹配云端数据库实际结构."""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base



class QuoteState(str, PyEnum):
    """Quote status enumeration — 匹配数据库大写值."""
    DRAFT = "DRAFT"
    WAITING_FOR_TECH = "WAITING_FOR_TECH"
    TECH_REVIEW = "TECH_REVIEW"
    TECH_APPROVED = "TECH_APPROVED"
    TECH_REJECTED = "TECH_REJECTED"
    PENDING_BOSS = "PENDING_BOSS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FIXED = "FIXED"
    CANCELLED = "CANCELLED"


class NominationStatus(str, PyEnum):
    UNFIXED = "unfixed"
    FIXED = "fixed"
    REVOKED = "revoked"


class MoldFeeMode(str, PyEnum):
    DIRECT = "direct"
    AMORTIZED = "amortized"


class FixPath(str, PyEnum):
    DIRECT_PRODUCTION = "direct_production"
    SAMPLE_FIRST = "sample_first"


class SurfaceTreatment(str, PyEnum):
    NONE = "none"
    ELECTROPLATE = "electroplate"
    POWDER_COATING = "powder_coating"
    PAINTING = "painting"


class Quote(Base):
    """Quote model - 匹配云端数据库 quotes 表结构."""

    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_serial: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    annual_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pricing_mode: Mapped[str] = mapped_column(String(50), nullable=False, default='independent')

    # 技术参数
    thickness: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    press_stroke: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    cavity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scrap_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0.1000)
    gross_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    # 材料快照
    snapshot_mat_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    snapshot_mat_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    snapshot_density: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    snapshot_scrap_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # 价格相关
    material_net_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    stamping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    surface_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    treatment_fee: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    profit_margin: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    final_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    unit_price_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    material_cost_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    final_price_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    override_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=[])

    # 审批流程 — approval_status 是实际字段名
    approval_status: Mapped[str] = mapped_column(String(50), nullable=False, default='DRAFT')
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_quote_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 定点相关
    nomination_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nomination_attachment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    nomination_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nomination_confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 模具相关
    mold_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0.00)
    machine_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    press_tonnage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mold_life: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mold_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mold_discount_mode: Mapped[str] = mapped_column(String(50), nullable=True, default='direct')
    mold_discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True, default=1.0)

    # 其他
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    die_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    customer_product_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    inspection_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    packaging_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    sdr_drawing_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    material_utilization: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    annual_avg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    lifecycle_years: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    treatment_items: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Quote {self.quote_serial or self.id}>"
