"""Pydantic schemas for quality inspection and release management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.quality import ExemptionType, InspectionResult


class FirstPieceInspectionBase(BaseModel):
    """Base schema for first piece inspection."""

    part_id: int
    session_id: Optional[int] = None
    inspected_qty: int = Field(ge=1)
    dimension_ok: bool = False
    dimension_notes: Optional[str] = None
    appearance_ok: bool = False
    appearance_notes: Optional[str] = None
    function_ok: bool = False
    function_notes: Optional[str] = None
    notes: Optional[str] = None


class FirstPieceInspectionCreate(FirstPieceInspectionBase):
    """Schema for creating first piece inspection."""

    result: InspectionResult


class FirstPieceInspectionResponse(BaseModel):
    """Schema for first piece inspection response."""

    id: int
    inspection_no: str
    part_id: int
    session_id: Optional[int] = None
    inspected_qty: int
    inspected_by: Optional[int] = None
    dimension_ok: bool
    dimension_notes: Optional[str] = None
    appearance_ok: bool
    appearance_notes: Optional[str] = None
    function_ok: bool
    function_notes: Optional[str] = None
    result: InspectionResult
    notes: Optional[str] = None
    inspected_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OQCInspectionBase(BaseModel):
    """Base schema for OQC inspection."""

    part_id: int
    shipment_qty: int = Field(ge=1)
    order_no: Optional[str] = None
    sample_size: int = Field(ge=1)
    aql_level: Optional[str] = None
    major_defects: int = Field(default=0, ge=0)
    minor_defects: int = Field(default=0, ge=0)
    critical_defects: int = Field(default=0, ge=0)
    notes: Optional[str] = None


class OQCInspectionCreate(OQCInspectionBase):
    """Schema for creating OQC inspection."""

    result: InspectionResult


class OQCInspectionResponse(BaseModel):
    """Schema for OQC inspection response."""

    id: int
    inspection_no: str
    part_id: int
    shipment_qty: int
    order_no: Optional[str] = None
    sample_size: int
    inspected_by: Optional[int] = None
    aql_level: Optional[str] = None
    major_defects: int
    minor_defects: int
    critical_defects: int
    result: InspectionResult
    notes: Optional[str] = None
    inspected_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QAExemptionBase(BaseModel):
    """Base schema for QA exemption."""

    part_id: int
    exemption_type: ExemptionType
    issue_description: str
    affected_qty: int = Field(ge=1)
    notes: Optional[str] = None


class QAExemptionCreate(QAExemptionBase):
    """Schema for creating QA exemption."""

    pass


class QAExemptionApprove(BaseModel):
    """Schema for approving a QA exemption."""

    exemption_reason: str = Field(max_length=500)


class QAExemptionResponse(BaseModel):
    """Schema for QA exemption response."""

    id: int
    exemption_no: str
    part_id: int
    exemption_type: ExemptionType
    issue_description: str
    affected_qty: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    exemption_reason: Optional[str] = None
    is_approved: bool
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatrolInspectionBase(BaseModel):
    """Base schema for patrol inspection."""

    machine_id: Optional[int] = None
    session_id: Optional[int] = None
    dimension_check: bool = False
    appearance_check: bool = False
    process_parameter_check: bool = False
    sample_size: int = Field(default=0, ge=0)
    defect_count: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    corrective_action: Optional[str] = None


class PatrolInspectionCreate(PatrolInspectionBase):
    """Schema for creating patrol inspection."""

    result: InspectionResult


class PatrolInspectionResponse(BaseModel):
    """Schema for patrol inspection response."""

    id: int
    inspection_no: str
    machine_id: Optional[int] = None
    session_id: Optional[int] = None
    inspected_by: Optional[int] = None
    dimension_check: bool
    appearance_check: bool
    process_parameter_check: bool
    sample_size: int
    defect_count: int
    result: InspectionResult
    notes: Optional[str] = None
    corrective_action: Optional[str] = None
    action_taken_by: Optional[int] = None
    inspected_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
