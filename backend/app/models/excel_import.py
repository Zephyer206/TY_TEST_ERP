"""Excel import models for traceability."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportBatch(Base):
    """Import batch - tracks each Excel import operation."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_sheets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_sheets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='PENDING')
    imported_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ImportBatch {self.id}: {self.file_name}>"


class ExcelImportRow(Base):
    """Excel import row - tracks each row from imported Excel files."""

    __tablename__ = "excel_import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_sheet: Mapped[str] = mapped_column(String(200), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Parsed fields
    parsed_customer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    parsed_customer_part_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    parsed_customer_part_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    parsed_internal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    parsed_tooling_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parsed_mold_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parsed_is_continuous: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    parsed_process_step_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parsed_cavity_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parsed_material: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parsed_thickness: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    parsed_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    parsed_pitch: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    parsed_gross_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    parsed_net_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    parsed_position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Validation
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default='PENDING')
    validation_errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution
    resolved_customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_part_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_tooling_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_alias_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ExcelImportRow {self.id}: {self.source_sheet}[{self.source_row}]>"
