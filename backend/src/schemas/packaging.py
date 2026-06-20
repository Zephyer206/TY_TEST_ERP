"""Pydantic schemas for packaging management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.packaging import InspectionResult, PackagingStatus


class PackagingScanRequest(BaseModel):
    """Schema for packaging scan request."""

    part_id: int
    quantity: int = Field(ge=1)
    box_barcode: str
    packaging_type: Optional[str] = None
    box_no: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    production_batch_no: Optional[str] = None
    process_flow_no: Optional[str] = None
    notes: Optional[str] = None


class PackagingInspectRequest(BaseModel):
    """Schema for packaging inspection request."""

    record_id: int
    inspected_qty: int = Field(ge=0)
    passed_qty: int = Field(ge=0)
    rejected_qty: int = Field(ge=0)
    visual_result: Optional[InspectionResult] = None
    inspection_notes: Optional[str] = None
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None


class PackagingRecordResponse(BaseModel):
    """Schema for packaging record response."""

    id: int
    record_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    production_batch_no: Optional[str] = None
    process_flow_no: Optional[str] = None
    quantity: int
    packaging_type: Optional[str] = None
    box_no: Optional[str] = None
    box_barcode: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    status: PackagingStatus
    visual_inspection_result: Optional[InspectionResult] = None
    visual_inspection_by: Optional[int] = None
    visual_inspection_at: Optional[datetime] = None
    inspected_qty: Optional[int] = None
    passed_qty: Optional[int] = None
    rejected_qty: Optional[int] = None
    inspection_notes: Optional[str] = None
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    stock_qty: int
    shipment_id: Optional[int] = None
    shipped_at: Optional[datetime] = None
    scanned_by: Optional[int] = None
    scanned_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PackagingRecordListResponse(BaseModel):
    """Schema for packaging record list."""

    id: int
    record_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    quantity: int
    box_barcode: Optional[str] = None
    status: PackagingStatus
    warehouse_location: Optional[str] = None
    scanned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryAdjustRequest(BaseModel):
    """Schema for inventory adjustment."""

    part_id: int
    warehouse_location: str
    quantity_change: int  # positive for add, negative for reduce
    reason: str
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None


class InventoryResponse(BaseModel):
    """Schema for inventory response."""

    id: int
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    warehouse_location: str
    shelf_location: Optional[str] = None
    quantity: int
    latest_batch_no: Optional[str] = None
    latest_production_date: Optional[datetime] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    """Schema for inventory transaction response."""

    id: int
    transaction_no: str
    part_id: int
    part_no: Optional[str] = None
    transaction_type: str
    quantity_before: int
    quantity_change: int
    quantity_after: int
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    warehouse_location: Optional[str] = None
    operated_by: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
