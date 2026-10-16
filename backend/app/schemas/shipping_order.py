"""Schemas for shipping orders."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShippingLineBase(BaseModel):
    customer_part_no: str = Field(min_length=1, max_length=150, alias="customer_part_no")
    part_id: Optional[int] = None
    part_customer_alias_id: Optional[int] = None
    part_name: str = Field(min_length=1, max_length=200)
    ordered_qty: int = Field(gt=0)
    planned_ship_date: date
    remark: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class ShippingLineCreate(ShippingLineBase):
    pass


class ShippingLineResponse(ShippingLineBase):
    id: int
    order_id: int
    customer_part_no_snapshot: str
    part_name_snapshot: str
    status: str
    cancelled_qty: int
    shipped_qty: int = 0
    remaining_qty: int = 0
    inventory_stock_qty: Optional[int] = None
    inventory_reserved_qty: int = 0
    inventory_available_qty: Optional[int] = None
    inventory_location: Optional[str] = None
    label_confirmed: bool = False
    cancellation_consents: list["CancellationConsentResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ShippingOrderCreate(BaseModel):
    order_type: str = Field(default="formal", pattern="^(formal|sample)$")
    customer_id: Optional[int] = None
    temporary_customer_name: Optional[str] = Field(default=None, max_length=200)
    po_no: Optional[str] = Field(default=None, max_length=100)
    lines: list[ShippingLineCreate] = Field(default_factory=list)


class ShippingOrderUpdate(ShippingOrderCreate):
    pass


class SubmitRequest(BaseModel):
    confirm_duplicate_po: bool = False
    confirm_unregistered_customer_parts: bool = False


class LabelConfirmRequest(BaseModel):
    remark: Optional[str] = None


class CancelRequest(BaseModel):
    cancel_qty: int = Field(gt=0)
    reason: str = Field(min_length=1)


class CancellationConsentRequest(BaseModel):
    consent: bool = True


class CancellationConsentResponse(BaseModel):
    id: int
    order_line_id: int
    cancel_qty: int
    reason: str
    status: str
    business_confirmed_by: Optional[int] = None
    label_confirmed_by: Optional[int] = None
    business_confirmed_at: Optional[datetime] = None
    label_confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LogisticsInput(BaseModel):
    carrier_name: Optional[str] = Field(default=None, max_length=100)
    tracking_no: Optional[str] = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def has_transport_reference(self):
        if not self.carrier_name and not self.tracking_no:
            raise ValueError("物流公司或物流号至少填写一项")
        return self


class ShipmentLineInput(BaseModel):
    order_line_id: int
    qty: int = Field(gt=0)


class ShipmentConfirmRequest(BaseModel):
    lines: list[ShipmentLineInput] = Field(min_length=1)
    logistics: list[LogisticsInput] = Field(min_length=1)
    remark: Optional[str] = None
    production_batch_no: Optional[str] = None
    confirm_unregistered_customer_parts: bool = False


class LogisticsUpdateRequest(BaseModel):
    logistics: list[LogisticsInput] = Field(min_length=1)


class LogisticsResponse(BaseModel):
    id: int
    shipment_id: int
    carrier_name: Optional[str]
    tracking_no: Optional[str]
    created_at: datetime
    created_by: int
    model_config = ConfigDict(from_attributes=True)


class ShipmentLineResponse(BaseModel):
    id: int
    order_line_id: int
    qty: int
    model_config = ConfigDict(from_attributes=True)


class ShipmentResponse(BaseModel):
    id: int
    shipment_no: str
    order_id: int
    confirmed_by: int
    confirmed_at: datetime
    production_batch_no: Optional[str]
    remark: Optional[str]
    lines: list[ShipmentLineResponse] = []
    logistics: list[LogisticsResponse] = []
    model_config = ConfigDict(from_attributes=True)


class LabelConfirmationResponse(BaseModel):
    id: int
    order_line_id: int
    confirmed_by: int
    confirmed_at: datetime
    remark: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class OperationHistoryResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int]
    user_id: Optional[int]
    created_at: datetime
    changes_summary: Optional[str]
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)


class ShippingOrderResponse(BaseModel):
    id: int
    order_no: str
    order_type: str
    customer_id: Optional[int]
    temporary_customer_name: Optional[str]
    po_no: Optional[str]
    status: str
    created_by: int
    created_at: datetime
    last_modified_at: datetime
    submitted_at: Optional[datetime]
    completed_at: Optional[datetime]
    lines: list[ShippingLineResponse] = []
    shipments: list[ShipmentResponse] = []
    warnings: list[dict] = []
    operation_history: list[OperationHistoryResponse] = []
    model_config = ConfigDict(from_attributes=True)


class CustomerPartSearchResponse(BaseModel):
    customer_part_no: str
    part_id: int
    part_customer_alias_id: int
    part_name: Optional[str]
    customer_part_name: Optional[str]
    same_physical_part_hint: Optional[str] = None
    inventory_stock_qty: int = 0
    inventory_reserved_qty: int = 0
    inventory_available_qty: int = 0
    inventory_location: Optional[str] = None


class ShippingOrderListResponse(BaseModel):
    items: list[ShippingOrderResponse]
    total: int
