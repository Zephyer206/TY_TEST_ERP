"""Pydantic schemas for admin and context switch management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.admin import ContextSwitchType


class SwitchContextRequest(BaseModel):
    """Schema for switching admin context."""

    department: str  # e.g., "sales", "production", "quality", "warehouse", "design"


class SwitchContextResponse(BaseModel):
    """Schema for context switch response."""

    success: bool
    message: str
    original_role_level: int
    original_dept: Optional[str] = None
    switched_to_role_level: int
    switched_to_dept: str
    session_key: Optional[str] = None
    expires_in_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SwitchBackResponse(BaseModel):
    """Schema for switch back response."""

    success: bool
    message: str
    restored_role_level: int

    model_config = ConfigDict(from_attributes=True)


class AdminContextInfo(BaseModel):
    """Schema for current context information."""

    user_id: int
    original_role_level: int
    original_dept: Optional[str] = None
    current_role_level: int
    current_dept: str
    is_switched: bool
    switch_type: Optional[ContextSwitchType] = None
    switched_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ContextSwitchRecordResponse(BaseModel):
    """Schema for context switch record."""

    id: int
    user_id: int
    original_role_level: int
    original_dept: Optional[str] = None
    switched_to_role_level: int
    switched_to_dept: str
    switch_type: ContextSwitchType
    is_active: bool
    switched_at: datetime
    switched_back_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DeptRoleMapping(BaseModel):
    """Mapping of departments to role levels."""

    department: str
    role_level: int
    role_name: str


# Predefined department role mappings
SESSION_EXPIRY_SECONDS = 3600  # 1 hour

DEPT_ROLE_MAPPINGS = {
    "sales": {"role_level": 5, "role_name": "业务经理"},
    "production": {"role_level": 3, "role_name": "生产主管"},
    "quality": {"role_level": 3, "role_name": "质检主管"},
    "warehouse": {"role_level": 3, "role_name": "仓库主管"},
    "design": {"role_level": 4, "role_name": "设计工程师"},
    "mold": {"role_level": 2, "role_name": "模具工程师"},
    "packaging": {"role_level": 3, "role_name": "包装主管"},
    "spray": {"role_level": 3, "role_name": "喷涂主管"},
}
