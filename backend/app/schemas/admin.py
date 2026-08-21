"""Pydantic schemas for admin and context switch management with canonical LV1-LV4 system."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.admin import ContextSwitchType


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
    """Mapping of departments to role levels using canonical LV1-LV4 system."""

    department: str
    role_level: int
    role_name: str


# Predefined department role mappings with canonical LV1-LV4 levels
SESSION_EXPIRY_SECONDS = 3600  # 1 hour

# Context switch department role mappings:
# - LV1: warehouse, spray, production operators
# - LV2: technical staff, team leaders, business staff
# - LV3: department supervisors (not boss approval - that remains LV3 in main identity)
DEPT_ROLE_MAPPINGS = {
    "sales": {"role_level": 2, "role_name": "业务人员"},  # Business staff -> LV2
    "production": {"role_level": 1, "role_name": "生产操作工"},  # Production operator -> LV1
    "quality": {"role_level": 2, "role_name": "质检主管"},  # QC supervisor -> LV2
    "warehouse": {"role_level": 1, "role_name": "仓库管理员"},  # Warehouse staff -> LV1
    "design": {"role_level": 2, "role_name": "设计工程师"},  # Design engineer -> LV2
    "mold": {"role_level": 2, "role_name": "模具工程师"},  # Mold engineer -> LV2
    "packaging": {"role_level": 2, "role_name": "包装主管"},  # Packaging supervisor -> LV2
    "spray": {"role_level": 1, "role_name": "喷涂工"},  # Spray worker -> LV1
}
