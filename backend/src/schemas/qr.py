"""Pydantic schemas for QR code operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.services.qr_service import QRType


class QRCodeResponse(BaseModel):
    """Schema for QR code generation response."""

    qr_code: str  # e.g., "MAT-12345"
    content: str  # Full URL encoded in QR
    image_base64: str  # Data URI

    model_config = ConfigDict(from_attributes=True)


class QRCodeLookupResponse(BaseModel):
    """Schema for QR code lookup response."""

    qr_code: str
    qr_type: QRType
    entity_id: str
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    details: Optional[dict] = None
    timestamp: datetime


class MaterialQRInfo(BaseModel):
    """Schema for material batch QR info."""

    batch_id: str
    material_name: str
    supplier_name: Optional[str] = None
    quantity: float
    unit: str
    received_at: Optional[datetime] = None
    status: str


class MachineQRInfo(BaseModel):
    """Schema for machine QR info."""

    machine_id: int
    machine_number: str
    press_tonnage: float
    location: Optional[str] = None
    status: str


class ProcessFlowQRInfo(BaseModel):
    """Schema for process flow card QR info."""

    card_id: int
    card_no: str
    part_name: str
    process_step: str
    status: str
