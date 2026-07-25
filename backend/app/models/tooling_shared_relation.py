"""Auditable shared/common mold relations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ToolingSharedRelation(Base):
    """A source-backed relation between two existing tooling records."""

    __tablename__ = "tooling_shared_relations"
    __table_args__ = (
        CheckConstraint("tooling_id <> related_tooling_id", name="ck_tooling_shared_relations_distinct"),
        UniqueConstraint(
            "tooling_id",
            "related_tooling_id",
            "relation_type",
            name="uq_tooling_shared_relations_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tooling_id: Mapped[int] = mapped_column(ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True)
    related_tooling_id: Mapped[int] = mapped_column(ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="SHARED_MOLD")
    relation_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="set")
    source_sheet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(30), nullable=False, default="EXPLICIT_NOTE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
