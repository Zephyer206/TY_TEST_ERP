"""Customer model."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    pass


class CustomerType(str, PyEnum):
    """Customer type enumeration."""

    OEM = "oem"  # Original Equipment Manufacturer
    TIER1 = "tier1"  # Tier 1 supplier
    TIER2 = "tier2"  # Tier 2 supplier
    DISTRIBUTOR = "distributor"
    END_USER = "end_user"
    OTHER = "other"


class CustomerStatus(str, PyEnum):
    """Customer status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PROSPECT = "prospect"
    BLOCKED = "blocked"


class Customer(Base):
    """Customer model."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType), default=CustomerType.OTHER, nullable=False
    )
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus), default=CustomerStatus.ACTIVE, nullable=False
    )

    # Contact info
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Address
    province: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Business info
    tax_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    bank_account: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Payment terms
    payment_days: Mapped[int] = mapped_column(Numeric(3), default=30)
    credit_limit: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    # Sales person
    sales_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    sales_user: Mapped[Optional["User"]] = relationship("User")
    quotes: Mapped[list["Quote"]] = relationship(
        "Quote", back_populates="customer"
    )
    parts: Mapped[list["Part"]] = relationship("Part", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.code}: {self.name}>"
