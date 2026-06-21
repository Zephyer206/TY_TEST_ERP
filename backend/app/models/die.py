"""Die model - 匹配 dies 表结构."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Die(Base):
    """Die model - 匹配云端数据库 dies 表."""

    __tablename__ = "dies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mold_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    part_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mold_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    mold_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cavity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Lifecycle
    lifecycle_status: Mapped[str] = mapped_column(String(50), nullable=False, default='AVAILABLE')
    converted_to_mold_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Lifespan tracking
    lifespan_strokes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    current_strokes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=0)

    # Supplier info
    supplier: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional fields
    mold_set_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1)
    press_tonnage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_equipment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Technical specs
    thickness_mm: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    width_mm: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    pitch_mm: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    die_type: Mapped[str] = mapped_column(String(50), nullable=False, default='progressive')

    def __repr__(self) -> str:
        return f"<Die {self.mold_number}>"
