"""Pydantic schemas for production planning and reporting."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.production import PlanState, SessionState


class ProductionPlanCreate(BaseModel):
    """Schema for creating a production plan."""

    part_id: int
    total_qty: int = Field(ge=1)
    due_date: datetime
    priority: int = Field(default=1, ge=1, le=3)
    notes: Optional[str] = None


class ProductionPlanUpdate(BaseModel):
    """Schema for updating a production plan."""

    total_qty: Optional[int] = Field(default=None, ge=1)
    due_date: Optional[datetime] = None
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    notes: Optional[str] = None


class MachineAssignmentCreate(BaseModel):
    """Schema for assigning a machine to plan."""

    machine_id: int
    assigned_qty: int = Field(ge=0, default=0)
    is_primary: bool = False


class ProductionPlanResponse(BaseModel):
    """Schema for production plan response."""

    id: int
    plan_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    total_qty: int
    completed_qty: int
    priority: int
    due_date: datetime
    start_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    state: PlanState
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductionPlanListResponse(BaseModel):
    """Schema for production plan list."""

    id: int
    plan_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    total_qty: int
    completed_qty: int
    priority: int
    due_date: datetime
    state: PlanState
    progress_pct: float = 0.0
    is_overdue: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionStartRequest(BaseModel):
    """Schema for starting a production session."""

    plan_id: int
    machine_id: int
    material_batch_id: Optional[int] = None
    tooling_id: Optional[int] = None


class SessionStartResponse(BaseModel):
    """Schema for session start response."""

    session_id: int
    session_no: str
    plan_id: int
    machine_id: int
    material_validated: bool
    force_started: bool
    tooling_id: Optional[int] = None
    tooling_no: Optional[str] = None
    machine_matching: bool
    message: str


class ProductionReportCreate(BaseModel):
    """Schema for creating a production report."""

    session_id: int
    strokes: int = Field(ge=1)
    good_qty: int = Field(ge=0)
    reject_qty: int = Field(ge=0, default=0)
    reject_reasons: Optional[dict] = None
    operator_name: Optional[str] = None


class ProductionReportResponse(BaseModel):
    """Schema for production report response."""

    id: int
    report_no: str
    session_id: int
    strokes: int
    cavity_count: int
    output_qty: int
    good_qty: int
    reject_qty: int
    reject_reasons: Optional[dict] = None
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    reported_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    """Schema for production session response."""

    id: int
    session_no: str
    plan_id: int
    machine_id: int
    machine_no: Optional[str] = None
    material_batch_id: Optional[int] = None
    tooling_id: Optional[int] = None
    tooling_no: Optional[str] = None
    material_validated: bool
    force_started: bool
    state: SessionState
    total_strokes: int
    total_output: int
    total_good_qty: int
    started_at: datetime
    closed_at: Optional[datetime] = None
    process_flow_no: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SessionCloseRequest(BaseModel):
    """Schema for closing a production session."""

    notes: Optional[str] = None


class ProcessFlowCardResponse(BaseModel):
    """Schema for process flow card response."""

    id: int
    card_no: str
    session_id: int
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    machine_id: int
    machine_no: Optional[str] = None
    material_batch_id: Optional[int] = None
    material_lot_no: Optional[str] = None
    total_strokes: int
    total_output: int
    good_qty: int
    reject_qty: int
    production_start: datetime
    production_end: datetime
    duration_minutes: int
    status: str
    qr_code_path: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MachineAssignmentResponse(BaseModel):
    """Schema for machine assignment response."""

    id: int
    plan_id: int
    machine_id: int
    machine_no: Optional[str] = None
    machine_name: Optional[str] = None
    assigned_qty: int
    is_primary: bool
    assigned_at: datetime
    assigned_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
