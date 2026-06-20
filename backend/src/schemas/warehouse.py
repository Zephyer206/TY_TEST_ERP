"""Pydantic schemas for warehouse and material batch management."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.warehouse import IQCResult, MaterialStatus


class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""

    code: str = Field(max_length=50)
    name: str = Field(max_length=200)
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    payment_terms: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class SupplierResponse(BaseModel):
    """Schema for supplier response."""

    id: int
    code: str
    name: str
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    payment_terms: Optional[str] = None
    rating: Optional[int] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchCreate(BaseModel):
    """Schema for creating a material batch."""

    material_grade: str = Field(max_length=100)
    material_type: Optional[str] = Field(default=None, max_length=50)
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_kg: float = Field(gt=0)
    supplier_id: Optional[int] = None
    purchase_order_no: Optional[str] = None
    invoice_no: Optional[str] = None
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    notes: Optional[str] = None


class MaterialBatchUpdate(BaseModel):
    """Schema for updating a material batch."""

    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    notes: Optional[str] = None


class IQCUpdate(BaseModel):
    """Schema for IQC result update."""

    result: IQCResult
    notes: Optional[str] = Field(default=None, max_length=500)


class SplitRequest(BaseModel):
    """Schema for splitting a material batch."""

    split_specs: list["SplitSpecItem"]


class SplitSpecItem(BaseModel):
    """Schema for a single split specification."""

    width: float = Field(gt=0)
    pieces: int = Field(ge=1, default=1)
    weight_kg: Optional[float] = Field(default=None, gt=0)
    position_index: int = Field(ge=0)
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None


class MaterialBatchResponse(BaseModel):
    """Schema for material batch response."""

    id: int
    batch_no: str
    qr_code: str
    material_grade: str
    material_type: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_kg: float
    original_weight_kg: float
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    purchase_order_no: Optional[str] = None
    invoice_no: Optional[str] = None
    unit_price: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    slit_width: Optional[float] = None
    slit_pieces: Optional[int] = None
    status: MaterialStatus
    iqc_result: Optional[IQCResult] = None
    iqc_by: Optional[int] = None
    iqc_at: Optional[datetime] = None
    iqc_notes: Optional[str] = None
    parent_id: Optional[int] = None
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    consumed_qty: float
    received_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchListResponse(BaseModel):
    """Schema for material batch list."""

    id: int
    batch_no: str
    qr_code: str
    material_grade: str
    material_type: Optional[str] = None
    weight_kg: float
    status: MaterialStatus
    supplier_name: Optional[str] = None
    warehouse_location: Optional[str] = None
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchChildResponse(BaseModel):
    """Schema for material batch child (split result)."""

    id: int
    child_batch_no: str
    qr_code: str
    parent_batch_id: int
    width: float
    weight_kg: float
    pieces: int
    position_index: int
    status: MaterialStatus
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SplitResultResponse(BaseModel):
    """Schema for split operation result."""

    parent_batch_id: int
    parent_batch_no: str
    parent_status: MaterialStatus
    children: list[MaterialBatchChildResponse]


class TraceEntry(BaseModel):
    """Schema for a single trace entry."""

    timestamp: datetime
    event_type: str
    description: str
    operator_id: Optional[int] = None
    reference_no: Optional[str] = None
    details: Optional[dict] = None


class TraceResponse(BaseModel):
    """Schema for batch trace response."""

    batch_id: int
    batch_no: str
    qr_code: str
    material_grade: str
    current_status: MaterialStatus
    original_weight_kg: float
    current_weight_kg: float
    entries: list[TraceEntry]


# Update forward references
SplitRequest.model_rebuild()
