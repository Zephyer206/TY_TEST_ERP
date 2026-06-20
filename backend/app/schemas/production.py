"""Pydantic schemas for production planning and reporting."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.production import PlanStatus, ProcessFlowStatus, SessionStatus


class ProductionPlanBase(BaseModel):
    """Base schema for production plan."""

    part_id: int
    total_qty: int = Field(ge=1)
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    priority: int = Field(default=0, ge=0, le=1)
    notes: Optional[str] = None


class ProductionPlanCreate(ProductionPlanBase):
    """Schema for creating a production plan."""

    pass


class ProductionPlanUpdate(BaseModel):
    """Schema for updating a production plan."""

    total_qty: Optional[int] = Field(default=None, ge=1)
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    priority: Optional[int] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = None
    status: Optional[PlanStatus] = None


class MachineAssignmentCreate(BaseModel):
    """Schema for assigning a machine to a plan."""

    machine_id: int
    assigned_qty: int = Field(ge=1)


class ProductionPlanResponse(ProductionPlanBase):
    """Schema for production plan response."""

    id: int
    plan_no: str
    completed_qty: int
    status: PlanStatus
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductionPlanDetailResponse(ProductionPlanResponse):
    """Schema for production plan detail with assignments."""

    assignments: list["MachineAssignmentResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class MachineAssignmentResponse(BaseModel):
    """Schema for machine assignment response."""

    id: int
    plan_id: int
    machine_id: int
    machine_no: Optional[str] = None
    machine_name: Optional[str] = None
    assigned_qty: int
    completed_qty: int
    is_active: bool
    assigned_by: Optional[int] = None
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionStartRequest(BaseModel):
    """Schema for starting a production session."""

    machine_id: int
    part_id: int
    material_batch_id: Optional[int] = None
    plan_id: Optional[int] = None


class SessionStartWithMaterialRequest(BaseModel):
    """Schema for starting a session with material scan verification."""

    machine_id: int
    part_id: int
    material_batch_id: int
    plan_id: Optional[int] = None
    force_start: bool = Field(default=False, description="Force start even if material doesn't match")


class ProductionReportCreate(BaseModel):
    """Schema for creating a production report."""

    strokes: int = Field(ge=1)
    cavity_count: int = Field(default=1, ge=1)
    good_qty: int = Field(ge=0)
    reject_qty: int = Field(default=0, ge=0)
    material_used: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class ProductionSessionResponse(BaseModel):
    """Schema for production session response."""

    id: int
    session_no: str
    plan_id: Optional[int] = None
    machine_id: int
    tooling_id: Optional[int] = None
    part_id: int
    material_batch_id: Optional[int] = None
    status: SessionStatus
    started_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    total_strokes: int
    total_output: int
    good_qty: int
    reject_qty: int
    process_flow_id: Optional[int] = None
    operator_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductionSessionDetailResponse(ProductionSessionResponse):
    """Schema for production session detail with reports."""

    reports: list["ProductionReportResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class ProductionReportResponse(BaseModel):
    """Schema for production report response."""

    id: int
    session_id: int
    strokes: int
    cavity_count: int
    output: int
    good_qty: int
    reject_qty: int
    material_used: Optional[float] = None
    report_time: datetime
    operator_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessFlowCardResponse(BaseModel):
    """Schema for process flow card response."""

    id: int
    card_no: str
    session_id: int
    part_id: int
    part_no: Optional[str] = None
    machine_id: int
    machine_no: Optional[str] = None
    tooling_id: Optional[int] = None
    tooling_no: Optional[str] = None
    material_batch_no: Optional[str] = None
    planned_qty: int
    actual_output: int
    good_qty: int
    reject_qty: int
    status: ProcessFlowStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    operator_id: Optional[int] = None
    qr_code: Optional[str] = None
    qr_image_base64: Optional[str] = None
    inbound_time: Optional[datetime] = None
    inbound_operator_id: Optional[int] = None
    inbound_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialMatchResult(BaseModel):
    """Schema for material-machine match verification result."""

    is_match: bool
    message: str
    tooling_id: Optional[int] = None
    tooling_no: Optional[str] = None
    expected_material: Optional[str] = None
    actual_material: Optional[str] = None
