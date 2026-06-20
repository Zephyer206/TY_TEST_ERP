"""Pydantic schemas for QR code operations."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class QRLookupResponse(BaseModel):
    """Schema for QR lookup response."""

    found: bool
    prefix: Optional[str] = None
    entity_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QRGenerateRequest(BaseModel):
    """Schema for QR generation request."""

    prefix: str  # MAT, MCN, PFC, PRT, TLG, PKG, COT
    entity_id: int
    extra_data: Optional[dict[str, str]] = None


class QRGenerateResponse(BaseModel):
    """Schema for QR generation response."""

    content: str  # Raw QR content
    image_base64: str  # Base64 encoded image
    url: Optional[str] = None  # Cloud URL if uploaded


class QRMaterialResponse(BaseModel):
    """Schema for material batch QR response."""

    batch_id: int
    batch_no: str
    qr_content: str
    image_base64: str


class QRMachineResponse(BaseModel):
    """Schema for machine QR response."""

    machine_id: int
    machine_no: str
    qr_content: str
    image_base64: str


class QRProcessFlowResponse(BaseModel):
    """Schema for process flow QR response."""

    card_id: int
    card_no: str
    qr_content: str
    image_base64: str
