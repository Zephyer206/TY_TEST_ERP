"""Pydantic schemas for quality control management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.quality import (
    FirstPieceStatus,
    InspectionResult,
    OQCResult,
)


class FirstPieceInspectionCreate(BaseModel):
    """Schema for creating a first piece inspection."""

    part_id: int
    process_flow_id: Optional[int] = None
    dimension_check: Optional[dict] = None
    surface_check: Optional[dict] = None
    material_check: Optional[dict] = None
    result: FirstPieceStatus
    reject_reasons: Optional[str] = None
    rework_required: bool = False
    notes: Optional[str] = None
    attachment_paths: Optional[dict] = None
    batch_size: Optional[int] = None
    sample_size: Optional[int] = None


class FirstPieceInspectionUpdate(BaseModel):
    """Schema for updating a first piece inspection."""

    dimension_check: Optional[dict] = None
    surface_check: Optional[dict] = None
    material_check: Optional[dict] = None
    result: Optional[FirstPieceStatus] = None
    reject_reasons: Optional[str] = None
    rework_required: Optional[bool] = None
    notes: Optional[str] = None
    attachment_paths: Optional[dict] = None


class FirstPieceInspectionResponse(BaseModel):
    """Schema for first piece inspection response."""

    id: int
    inspection_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    process_flow_id: Optional[int] = None
    dimension_check: Optional[dict] = None
    surface_check: Optional[dict] = None
    material_check: Optional[dict] = None
    result: FirstPieceStatus
    reject_reasons: Optional[str] = None
    rework_required: bool
    inspector_id: Optional[int] = None
    inspected_at: Optional[datetime] = None
    notes: Optional[str] = None
    attachment_paths: Optional[dict] = None
    batch_size: Optional[int] = None
    sample_size: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OQCInspectionCreate(BaseModel):
    """Schema for creating an OQC inspection."""

    part_id: int
    shipment_id: Optional[int] = None
    inspected_qty: int = Field(ge=1)
    passed_qty: int = Field(ge=0)
    failed_qty: int = Field(ge=0)
    defect_types: Optional[dict] = None
    defect_positions: Optional[dict] = None
    result: OQCResult
    sample_size: Optional[int] = None
    sampling_plan: Optional[str] = None
    notes: Optional[str] = None
    attachment_paths: Optional[dict] = None


class OQCInspectionResponse(BaseModel):
    """Schema for OQC inspection response."""

    id: int
    inspection_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    shipment_id: Optional[int] = None
    inspected_qty: int
    passed_qty: int
    failed_qty: int
    defect_types: Optional[dict] = None
    defect_positions: Optional[dict] = None
    result: OQCResult
    inspector_id: Optional[int] = None
    inspected_at: Optional[datetime] = None
    sample_size: Optional[int] = None
    sampling_plan: Optional[str] = None
    notes: Optional[str] = None
    attachment_paths: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QAExemptionCreate(BaseModel):
    """Schema for creating a QA exemption request."""

    part_id: int
    related_inspection_id: Optional[int] = None
    related_inspection_type: Optional[str] = None
    defect_description: str
    quantity_affected: int = Field(ge=1)
    reason: str
    impact_assessment: Optional[str] = None
    customer_notification_required: bool = False
    batch_no: Optional[str] = None


class QAExemptionApprove(BaseModel):
    """Schema for approving/rejecting a QA exemption."""

    approved: bool
    notes: Optional[str] = Field(default=None, max_length=500)
    expires_at: Optional[datetime] = None


class QAExemptionResponse(BaseModel):
    """Schema for QA exemption response."""

    id: int
    exemption_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    related_inspection_id: Optional[int] = None
    related_inspection_type: Optional[str] = None
    defect_description: str
    quantity_affected: int
    reason: str
    impact_assessment: Optional[str] = None
    customer_notification_required: bool
    status: str
    requested_by: Optional[int] = None
    requested_at: Optional[datetime] = None
    request_notes: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    expires_at: Optional[datetime] = None
    batch_no: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatrolInspectionCreate(BaseModel):
    """Schema for creating a patrol inspection."""

    machine_id: Optional[int] = None
    production_session_id: Optional[int] = None
    check_points: Optional[dict] = None
    check_results: Optional[dict] = None
    result: InspectionResult
    issues_found: Optional[dict] = None
    severity: Optional[str] = None
    corrective_action: Optional[str] = None
    action_required: bool = False
    notes: Optional[str] = None


class PatrolInspectionResponse(BaseModel):
    """Schema for patrol inspection response."""

    id: int
    inspection_no: str
    machine_id: Optional[int] = None
    production_session_id: Optional[int] = None
    check_points: Optional[dict] = None
    check_results: Optional[dict] = None
    result: InspectionResult
    issues_found: Optional[dict] = None
    severity: Optional[str] = None
    corrective_action: Optional[str] = None
    action_required: bool
    inspector_id: Optional[int] = None
    inspected_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
