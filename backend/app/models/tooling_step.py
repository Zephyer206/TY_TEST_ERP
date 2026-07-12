"""Tooling step model for multi-step molds."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ToolingStep(Base):
    """Tooling step model - represents individual steps in multi-step molds."""

    __tablename__ = "tooling_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    tooling_id: Mapped[int] = mapped_column(
        ForeignKey("tooling.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    step_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    operation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ToolingStep {self.tooling_id}-{self.step_no}>"
