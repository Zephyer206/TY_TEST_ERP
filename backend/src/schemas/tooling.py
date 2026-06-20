"""Pydantic schemas for tooling/mold management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.tooling import (
    ToolingCavityStatus,
    ToolingMaintenanceType,
    ToolingState,
)


class ToolingCreate(BaseModel):
    """Schema for creating a tooling."""

    tooling_no: str = Field(max_length=50)
    name: str = Field(max_length=200)
    tooling_type: Optional[str] = Field(default=None, max_length=50)
    customer_id: Optional[int] = None
    parent_id: Optional[int] = None
    cavity_count: Optional[int] = Field(default=None, ge=1)
    press_tonnage: Optional[float] = None
    spec_twph: Optional[str] = Field(default=None, max_length=100)
    ppap_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None


class ToolingUpdate(BaseModel):
    """Schema for updating a tooling."""

    name: Optional[str] = Field(default=None, max_length=200)
    tooling_type: Optional[str] = Field(default=None, max_length=50)
    customer_id: Optional[int] = None
    cavity_count: Optional[int] = Field(default=None, ge=1)
    press_tonnage: Optional[float] = None
    spec_twph: Optional[str] = Field(default=None, max_length=100)
    ppap_no: Optional[str] = Field(default=None, max_length=100)
    vehicle_model: Optional[str] = Field(default=None, max_length=100)
    state: Optional[ToolingState] = None
    cavity_status: Optional[ToolingCavityStatus] = None
    mounted_machine_id: Optional[int] = None
    notes: Optional[str] = None


class ToolingMountUpdate(BaseModel):
    """Schema for mounting/unmounting tooling to/from machine."""

    machine_id: int
    action: str = Field(pattern="^(mount|unmount)$")  # mount or unmount


class ToolingPartCreate(BaseModel):
    """Schema for associating tooling with part."""

    part_id: int
    is_primary: bool = False
    cavity_index: Optional[int] = None
    notes: Optional[str] = None


class ToolingMaintenanceCreate(BaseModel):
    """Schema for creating maintenance log entry."""

    tooling_id: int
    machine_id: Optional[int] = None
    maintenance_type: ToolingMaintenanceType
    fault_description: Optional[str] = None


class ToolingScanRequest(BaseModel):
    """Schema for scan request on machine (two-scan workflow)."""

    machine_id: int
    tooling_id: int
    scan_type: ToolingMaintenanceType = ToolingMaintenanceType.FIRST_SCAN
    notes: Optional[str] = Field(default=None, max_length=500)


class ToolingScanActionRequest(BaseModel):
    """Schema for second scan action selection."""

    action: str = Field(
        pattern="^(repair_complete|discard|remove_tooling|continue_repair)$",
        description="Action to take after second scan"
    )
    notes: Optional[str] = Field(default=None, max_length=500)
    fault_description: Optional[str] = Field(default=None, max_length=500)


class ToolingResponse(BaseModel):
    """Schema for tooling response."""

    id: int
    tooling_no: str
    name: str
    tooling_type: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    parent_id: Optional[int] = None
    parent_no: Optional[str] = None
    cavity_count: Optional[int] = None
    press_tonnage: Optional[float] = None
    spec_twph: Optional[str] = None
    ppap_no: Optional[str] = None
    vehicle_model: Optional[str] = None
    state: ToolingState
    cavity_status: ToolingCavityStatus
    mounted_machine_id: Optional[int] = None
    mounted_machine_no: Optional[str] = None
    designed_by: Optional[int] = None
    trial_completed_at: Optional[datetime] = None
    production_started_at: Optional[datetime] = None
    drawing_path: Optional[str] = None
    notes: Optional[str] = None
    children: list["ToolingChildResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolingChildResponse(BaseModel):
    """Schema for child tooling summary."""

    id: int
    tooling_no: str
    name: str
    tooling_type: Optional[str] = None
    cavity_count: Optional[int] = None
    state: ToolingState

    model_config = ConfigDict(from_attributes=True)


class ToolingListResponse(BaseModel):
    """Schema for tooling list summary."""

    id: int
    tooling_no: str
    name: str
    tooling_type: Optional[str] = None
    customer_name: Optional[str] = None
    cavity_count: Optional[int] = None
    press_tonnage: Optional[float] = None
    state: ToolingState
    cavity_status: ToolingCavityStatus
    mounted_machine_id: Optional[int] = None
    mounted_machine_no: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolingDetailResponse(ToolingResponse):
    """Schema for tooling detail with full info."""

    parts: list["ToolingPartResponse"] = []
    maintenance_logs: list["ToolingMaintenanceLogResponse"] = []


class ToolingPartResponse(BaseModel):
    """Schema for tooling-part association."""

    id: int
    tooling_id: int
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    is_primary: bool
    cavity_index: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolingMaintenanceLogResponse(BaseModel):
    """Schema for maintenance log response."""

    id: int
    tooling_id: int
    machine_id: Optional[int] = None
    maintenance_type: ToolingMaintenanceType
    first_scan_time: Optional[datetime] = None
    first_scan_by: Optional[int] = None
    first_scan_notes: Optional[str] = None
    second_scan_time: Optional[datetime] = None
    second_scan_by: Optional[int] = None
    second_scan_notes: Optional[str] = None
    action_taken: Optional[str] = None
    action_completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    fault_description: Optional[str] = None
    repair_result: Optional[str] = None
    fault_duration_minutes: Optional[int] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenancePoolResponse(BaseModel):
    """Schema for maintenance pool item."""

    id: int
    log_id: int
    tooling_id: int
    tooling_no: str
    tooling_name: str
    machine_id: Optional[int] = None
    machine_no: Optional[str] = None
    maintenance_type: ToolingMaintenanceType
    first_scan_time: Optional[datetime] = None
    fault_description: Optional[str] = None
    elapsed_minutes: Optional[int] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class MachineScanResponse(BaseModel):
    """Schema for machine scan response."""

    machine_id: int
    machine_no: str
    current_state: str
    current_tooling_id: Optional[int] = None
    current_tooling_no: Optional[str] = None
    scan_result: str
    message: str
    requires_second_scan: bool = False
    pending_log_id: Optional[int] = None


# Update forward references
ToolingResponse.model_rebuild()
ToolingDetailResponse.model_rebuild()
