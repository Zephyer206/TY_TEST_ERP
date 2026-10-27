"""Pydantic schemas for warehouse and material batch management."""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.warehouse import BatchStatus, IQCResult, ScanOperation, ScanType
from app.services.qr_service import generate_material_batch_qr_base64


class MaterialBatchBase(BaseModel):
    """Base schema for material batch."""

    material_id: Optional[int] = None
    supplier_id: Optional[int] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    length: Optional[float] = None
    gross_weight: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    po_no: Optional[str] = None


class MaterialBatchCreate(MaterialBatchBase):
    """Schema for creating a material batch."""

    pass


class IQCUpdate(BaseModel):
    """Schema for IQC inspection result."""

    result: IQCResult
    notes: Optional[str] = Field(default=None, max_length=500)


class BatchSplitRequest(BaseModel):
    """Schema for splitting a material batch."""

    splits: list["SplitItem"]


class SplitItem(BaseModel):
    """Schema for a split item."""

    width: Optional[float] = None
    length: Optional[float] = None
    weight: float = Field(gt=0, allow_inf_nan=False)


class BatchConsumeRequest(BaseModel):
    """Schema for consuming material from batch."""

    weight: float = Field(gt=0, allow_inf_nan=False)
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    notes: Optional[str] = None


class BatchScrapRequest(BaseModel):
    """Schema for scrapping remaining material."""

    reason: str = Field(max_length=500)


class MaterialBatchResponse(MaterialBatchBase):
    """Schema for material batch response."""

    id: int
    batch_no: str
    qr_code: Optional[str] = None
    net_weight: Optional[float] = None
    current_weight: float
    status: BatchStatus
    iqc_result: Optional[IQCResult] = None
    iqc_time: Optional[datetime] = None
    iqc_by: Optional[int] = None
    iqc_notes: Optional[str] = None
    parent_batch_id: Optional[int] = None
    received_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchDetailResponse(MaterialBatchResponse):
    """Schema for material batch detail with material info."""

    material_name: Optional[str] = None
    material_grade: Optional[str] = None
    supplier_name: Optional[str] = None
    children: list["MaterialBatchChildResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchChildResponse(BaseModel):
    """Schema for material batch child response."""

    id: int
    child_batch_no: str
    child_qr_code: Optional[str] = None
    width: Optional[float] = None
    length: Optional[float] = None
    current_weight: float
    status: BatchStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchTransactionResponse(BaseModel):
    """Schema for batch transaction response."""

    id: int
    batch_id: int
    batch_no: str
    transaction_type: str
    quantity_change: float
    weight_after: float
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    operator_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchTraceResponse(BaseModel):
    """Schema for batch trace response."""

    batch: MaterialBatchDetailResponse
    transactions: list[BatchTransactionResponse]


class SupplierBase(BaseModel):
    """Base schema for supplier."""

    name: str
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class SupplierCreate(SupplierBase):
    """Schema for creating a supplier."""

    pass


class SupplierResponse(SupplierBase):
    """Schema for supplier response."""

    id: int
    supplier_no: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialBase(BaseModel):
    """Base schema for material."""

    name: str
    grade: str
    thickness: Optional[float] = None
    width: Optional[float] = None
    weight_per_unit: Optional[float] = None
    unit: str = "kg"
    supplier_id: Optional[int] = None


class MaterialCreate(MaterialBase):
    """Schema for creating a material."""

    pass


class MaterialResponse(MaterialBase):
    """Schema for material response."""

    id: int
    material_no: str
    supplier_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── QR Scan Log ─────────────────────────────────────────────────────────────

class QRScanLogCreate(BaseModel):
    """Schema for creating a QR scan log entry."""

    scan_type: ScanType
    entity_id: int
    entity_no: Optional[str] = None
    operation: ScanOperation
    notes: Optional[str] = None


class QRScanLogResponse(BaseModel):
    """Schema for QR scan log response."""

    id: int
    scan_type: ScanType
    entity_id: int
    entity_no: Optional[str] = None
    operator_id: Optional[int] = None
    operation: ScanOperation
    notes: Optional[str] = None
    scanned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchScanResponse(BaseModel):
    """Schema for material batch scan result (T012)."""

    id: int
    batch_no: str
    qr_code: Optional[str] = None
    qr_image_base64: Optional[str] = None
    material_id: Optional[int] = None
    material_name: Optional[str] = None
    material_grade: Optional[str] = None
    supplier_name: Optional[str] = None
    thickness: Optional[float] = None
    width: Optional[float] = None
    length: Optional[float] = None
    gross_weight: float
    current_weight: float
    status: BatchStatus
    iqc_result: Optional[IQCResult] = None
    iqc_time: Optional[datetime] = None
    received_at: Optional[datetime] = None
    created_at: datetime
    parent_batch_id: Optional[int] = None
    parent_batch_no: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MaterialBatchChildScanResponse(BaseModel):
    """Schema for child batch scan result (T016)."""

    child_batch: MaterialBatchScanResponse
    parent_batch: MaterialBatchScanResponse
    sibling_batches: list["MaterialBatchScanResponse"] = []

    model_config = ConfigDict(from_attributes=True)


# ── Finished goods inventory workspace ──────────────────────────────────────

class FinishedGoodsInventoryItem(BaseModel):
    id: int
    part_id: int
    internal_part_no: Optional[str] = None
    part_name: Optional[str] = None
    customer_part_no: Optional[str] = None
    customer_part_name: Optional[str] = None
    customer_name: Optional[str] = None
    stock_qty: int
    reserved_qty: int
    available_qty: int
    last_month_shipped_qty: int = 0
    last_3_month_shipped_qty: int = 0
    location: Optional[str] = None
    last_update_at: datetime


class FinishedGoodsLedgerDay(BaseModel):
    day: date
    incoming_qty: int
    outgoing_qty: int
    net_qty: int
    closing_qty: int


class FinishedGoodsLedgerSummary(BaseModel):
    opening_stock: int
    total_incoming: int
    total_outgoing: int
    closing_stock: int
    from_date: date
    to_date: date


class FinishedGoodsLedgerPage(BaseModel):
    inventory_id: int
    part_id: int
    summary: FinishedGoodsLedgerSummary
    days: list[FinishedGoodsLedgerDay]
    entries: list["FinishedGoodsLedgerTransaction"] = Field(default_factory=list)


class FinishedGoodsLedgerTransaction(BaseModel):
    id: int
    occurred_at: datetime
    transaction_type: str
    quantity: int
    stock_before: int
    stock_after: int
    reason: Optional[str] = None
    reference_type: Optional[str] = None
    operator_id: Optional[int] = None
    affects_stock: bool = True


class FinishedGoodsLedgerEntry(BaseModel):
    transaction_type: Literal['incoming', 'outgoing']
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    occurred_on: Optional[date] = None
    affects_stock: bool = True


class FinishedGoodsInventoryReconcile(BaseModel):
    physical_stock: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=200)
    occurred_on: Optional[date] = None


class FinishedGoodsInventorySummary(BaseModel):
    inventory_rows: int
    total_stock: int
    total_reserved: int
    total_available: int
    missing_location_rows: int
    review_rows: int
    batch_id: Optional[int] = None


class FinishedGoodsInventoryPage(BaseModel):
    items: list[FinishedGoodsInventoryItem]
    total: int
    page: int
    page_size: int
    summary: FinishedGoodsInventorySummary


class FinishedGoodsReviewItem(BaseModel):
    id: int
    batch_id: int
    source_sheet: str
    source_row: int
    customer_part_no: Optional[str] = None
    customer_part_name: Optional[str] = None
    closing_qty: Optional[float] = None
    location: Optional[str] = None
    validation_errors: list[str]
    missing_part: bool


class FinishedGoodsReviewPage(BaseModel):
    items: list[FinishedGoodsReviewItem]
    total: int
    page: int
    page_size: int
    batch_id: Optional[int] = None
    categories: dict[str, int]


class FinishedGoodsLocationUpdate(BaseModel):
    location: Optional[str] = Field(default=None, max_length=100)


class FinishedGoodsReviewResolve(BaseModel):
    part_id: int = Field(gt=0)
    location: Optional[str] = Field(default=None, max_length=100)
    stock_qty: Optional[int] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)
