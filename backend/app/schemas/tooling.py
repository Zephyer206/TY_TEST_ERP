"""Pydantic schemas for tooling/mold management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.tooling import ToolingState


class ToolingBase(BaseModel):
    """Base schema for tooling."""

    name: str
    customer_product_no: Optional[str] = None
    cavity_count: Optional[int] = None
    tonnage: Optional[float] = None
    ppap_no: Optional[str] = None
    vehicle_model: Optional[str] = None
    spec_data: Optional[str] = None
    parent_id: Optional[int] = None


class ToolingCreate(ToolingBase):
    """Schema for creating a tooling."""

    pass


class ToolingUpdate(BaseModel):
    """Schema for updating tooling info."""

    name: Optional[str] = None
    customer_product_no: Optional[str] = None
    cavity_count: Optional[int] = None
    tonnage: Optional[float] = None
    ppap_no: Optional[str] = None
    vehicle_model: Optional[str] = None
    spec_data: Optional[str] = None


class ToolingMaintenanceLogResponse(BaseModel):
    """Schema for maintenance log response."""

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
    """Schema for tooling response."""

    id: int
    tooling_no: str
    state: ToolingState
    parent_id: Optional[int] = None
    drawing_path: Optional[str] = None
    sdr_drawing_path: Optional[str] = None
    active_maintenance_id: Optional[int] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolingDetailResponse(ToolingResponse):
    """Schema for tooling detail with parent-child and maintenance logs."""

    children: list["ToolingResponse"] = []
    parent: Optional["ToolingResponse"] = None
    maintenance_logs: list[ToolingMaintenanceLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ToolingListResponse(BaseModel):
    """Schema for tooling list (summary)."""

    id: int
    tooling_no: str
    name: str
    customer_product_no: Optional[str] = None
    state: ToolingState
    cavity_count: Optional[int] = None
    tonnage: Optional[float] = None
    parent_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FaultReport(BaseModel):
    """Schema for reporting a machine fault."""

    reason: Optional[str] = Field(default=None, max_length=500)


class SecondScanAction(BaseModel):
    """Schema for second scan action."""

    action: str = Field(..., pattern="^(complete|dismount)$")


class MaintenanceComplete(BaseModel):
    """Schema for completing tooling maintenance."""

    notes: Optional[str] = Field(default=None, max_length=500)
