"""Tooling customer links model."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ToolingCustomerLink(Base):
    """Tooling customer link - represents relationships between tooling and customers."""

    __tablename__ = "tooling_customer_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False, default='user')
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ToolingCustomerLink T{self.tooling_id}-C{self.customer_id}>"
