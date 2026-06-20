"""Pydantic schemas for admin operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.admin import SwitchTargetRole


class ContextSwitchRequest(BaseModel):
    """Schema for admin context switch request."""

    target_role: SwitchTargetRole = Field(
        description="Role to switch to (operator/mold_engineer/supervisor/design_engineer/sales_manager)"
    )
    duration_minutes: int = Field(
        default=60, ge=5, le=480,
        description="Switch duration in minutes (5-480)"
    )
    reason: str = Field(max_length=500, description="Reason for context switch")


class ContextSwitchResponse(BaseModel):
    """Schema for context switch response."""

    switch_token: str
    switched_role_level: int
    switched_role_name: str
    original_role_level: int
    expires_at: datetime
    message: str


class SwitchBackResponse(BaseModel):
    """Schema for switch back response."""

    success: bool
    original_role_level: int
    switched_back_at: datetime
    message: str


class ContextStatusResponse(BaseModel):
    """Schema for current context status."""

    is_switched: bool
    current_role_level: int
    current_role_name: str
    original_role_level: Optional[int] = None
    original_role_name: Optional[str] = None
    switched_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    remaining_minutes: Optional[int] = None


class AdminAuditLogResponse(BaseModel):
    """Schema for admin audit log response."""

    id: int
    log_no: str
    admin_user_id: int
    operation: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    context_switch_id: Optional[int] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
