"""Pydantic schemas for packaging management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.packaging import PackagingStatus


class PackagingScanRequest(BaseModel):
    """Schema for packaging scan."""

    part_id: int
    package_qty: int = Field(ge=1)
    box_no: Optional[str] = None
    session_id: Optional[int] = None
    notes: Optional[str] = None


class PackagingInspectionRequest(BaseModel):
    """Schema for packaging inspection (全检)."""

    passed: bool
    notes: Optional[str] = Field(default=None, max_length=500)


class PackagingRecordResponse(BaseModel):
    """Schema for packaging record response."""

    id: int
    package_no: str
    part_id: int
    session_id: Optional[int] = None
    package_qty: int
    box_no: Optional[str] = None
    status: PackagingStatus
    inspected_by: Optional[int] = None
    inspected_at: Optional[datetime] = None
    inspection_notes: Optional[str] = None
    operator_id: Optional[int] = None
    notes: Optional[str] = None
    scanned_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryResponse(BaseModel):
    """Schema for inventory response."""

    id: int
    part_id: int
    stock_qty: int
    reserved_qty: int
    location: Optional[str] = None
    last_update_by: Optional[int] = None
    last_update_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryDetailResponse(InventoryResponse):
    """Schema for inventory detail with part info."""

    part_no: Optional[str] = None
    part_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InventoryAdjustmentRequest(BaseModel):
    """Schema for inventory adjustment."""

    quantity: int  # Positive or negative
    reason: str = Field(max_length=200)


class InventoryTransactionResponse(BaseModel):
    """Schema for inventory transaction response."""

    id: int
    part_id: int
    transaction_type: str
    quantity: int
    stock_before: int
    stock_after: int
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    reason: Optional[str] = None
    operator_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
