"""TWP specifications captured per part and tooling source record."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PartToolingSpec(Base):
    """A source-backed T/W/P option for one part-tooling combination.

    A single part can legitimately have multiple TWP tuples when the source
    workbook documents multiple mold sets or revisions.  ``is_primary`` is
    scoped to (part_id, tooling_id) so each tooling can have one primary spec.
    The list display uses the primary spec from the selected tooling only.
    """

    __tablename__ = "part_tooling_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True
    )
    spec_twph: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thickness: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    pitch: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_sheet: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
