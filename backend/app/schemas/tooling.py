"""Pydantic schemas for the canonical tooling model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolingBase(BaseModel):
    tooling_number: Optional[str] = Field(default=None, max_length=100)
    tooling_name: Optional[str] = Field(default=None, max_length=200)
    mold_type: str = Field(default="unknown", max_length=50)
    is_continuous: bool = False
    cavity_count: int = Field(default=1, ge=0)
    process_step_count: Optional[int] = Field(default=None, ge=0)
    status: str = Field(default="DRAFT", max_length=30)
    press_tonnage: Optional[str] = Field(default=None, max_length=50)
    ppap_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    remark: Optional[str] = None


class ToolingCreate(ToolingBase):
    pass


class ToolingUpdate(BaseModel):
    tooling_name: Optional[str] = Field(default=None, max_length=200)
    mold_type: Optional[str] = Field(default=None, max_length=50)
    is_continuous: Optional[bool] = None
    cavity_count: Optional[int] = Field(default=None, ge=0)
    process_step_count: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, max_length=30)
    press_tonnage: Optional[str] = Field(default=None, max_length=50)
    ppap_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    remark: Optional[str] = None


class ToolingMaintenanceLogResponse(BaseModel):
    id: int
    tooling_id: int
    machine_id: Optional[int] = None
    fault_time: datetime
    fault_reason: Optional[str] = None
    repair_plan: Optional[str] = None
    repair_start_time: Optional[datetime] = None
    repair_end_time: Optional[datetime] = None
    repair_completed_by: Optional[int] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ToolingResponse(ToolingBase):
    id: int
    is_deleted: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    maintenance_logs: list[ToolingMaintenanceLogResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ToolingDetailResponse(ToolingResponse):
    pass


class ToolingListResponse(BaseModel):
    id: int
    tooling_number: str
    tooling_name: Optional[str] = None
    mold_type: str
    is_continuous: bool
    cavity_count: int
    process_step_count: Optional[int] = None
    status: str
    press_tonnage: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class FaultReport(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class SecondScanAction(BaseModel):
    action: str = Field(..., pattern="^(complete|dismount)$")


class MaintenanceComplete(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=500)
