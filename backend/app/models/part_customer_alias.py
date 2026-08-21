"""Part customer alias model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PartCustomerAlias(Base):
    """Part customer alias - customer-specific part numbers and names."""

    __tablename__ = "part_customer_aliases"
    __table_args__ = (
        CheckConstraint(
            "data_quality_status = 'pending_review' OR NULLIF(BTRIM(customer_part_no), '') IS NOT NULL",
            name="ck_part_customer_aliases_customer_part_no_nonempty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    customer_part_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    customer_part_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    revision: Mapped[str] = mapped_column(String(50), nullable=False, default='')
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Existing historical conflicts stay visible until a user confirms them.
    data_quality_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default='approved', server_default='approved'
    )
    data_quality_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PartCustomerAlias P{self.part_id}-C{self.customer_id}: {self.customer_part_no}>"
