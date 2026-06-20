"""QR Code API endpoints for code generation and lookup."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.schemas.qr import (
    MachineQRInfo,
    MaterialQRInfo,
    ProcessFlowQRInfo,
    QRCodeLookupResponse,
    QRCodeResponse,
)
from app.services import qr_service

router = APIRouter(prefix="/qr", tags=["QR Code"])


@router.get("/lookup", response_model=QRCodeLookupResponse)
async def lookup_qr_code(
    db: DbSession,
    current_user: CurrentUser,
    code: str = Query(..., description="QR code string (e.g., MAT-12345, MCN-001)"),
) -> QRCodeLookupResponse:
    """
    Look up entity by QR code.

    Supports prefixes:
    - MAT-: Material batch
    - MCN-: Machine
    - PFC-: Process flow card
    - PRT-: Part
    - PKG-: Packaging record
    - COA-: Coating record
    """
    parsed = qr_service.parse_qr_code(code)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid QR code format")

    qr_type = parsed["type"]
    entity_id = parsed["id"]

    # Query based on type
    details = None
    entity_name = None
    entity_type = None

    if qr_type == qr_service.QRType.MATERIAL:
        # Query material batch
        result = await db.execute(
            select().where()  # Simplified - would query material batch table
        )
        entity_type = "material_batch"
        details = {"message": "Material batch lookup"}

    elif qr_type == qr_service.QRType.MACHINE:
        # Query machine
        result = await db.execute(
            select().where()  # Simplified - would query machines table
        )
        entity_type = "machine"
        details = {"message": "Machine lookup"}

    elif qr_type == qr_service.QRType.PROCESS_FLOW:
        # Query process flow card
        result = await db.execute(
            select().where()  # Simplified - would query process flow table
        )
        entity_type = "process_flow"
        details = {"message": "Process flow lookup"}

    elif qr_type == qr_service.QRType.PART:
        entity_type = "part"
        details = {"message": "Part lookup"}

    elif qr_type == qr_service.QRType.PACKAGING:
        entity_type = "packaging_record"
        details = {"message": "Packaging record lookup"}

    elif qr_type == qr_service.QRType.COATING:
        entity_type = "coating_record"
        details = {"message": "Coating record lookup"}

    return QRCodeLookupResponse(
        qr_code=code,
        qr_type=qr_type,
        entity_id=entity_id,
        entity_name=entity_name,
        entity_type=entity_type,
        details=details,
        timestamp=datetime.utcnow(),
    )


@router.get("/material/{batch_id}", response_model=QRCodeResponse)
async def get_material_qr(
    batch_id: str,
    current_user: CurrentUser,
) -> QRCodeResponse:
    """Generate QR code for material batch."""
    try:
        qr_bytes, qr_code = qr_service.generate_material_qr(batch_id)
        content = qr_service.generate_qr_content(qr_service.QRType.MATERIAL, batch_id)
        import base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(qr_bytes).decode()}"

        return QRCodeResponse(
            qr_code=qr_code,
            content=content,
            image_base64=image_base64,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machine/{machine_id}", response_model=QRCodeResponse)
async def get_machine_qr(
    machine_id: int,
    current_user: CurrentUser,
) -> QRCodeResponse:
    """Generate QR code for machine."""
    try:
        qr_bytes, qr_code = qr_service.generate_machine_qr(machine_id)
        content = qr_service.generate_qr_content(qr_service.QRType.MACHINE, machine_id)
        import base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(qr_bytes).decode()}"

        return QRCodeResponse(
            qr_code=qr_code,
            content=content,
            image_base64=image_base64,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machine/{machine_id}/image")
async def get_machine_qr_image(
    machine_id: int,
    current_user: CurrentUser,
) -> Response:
    """Get machine QR code as PNG image."""
    try:
        qr_bytes, _ = qr_service.generate_machine_qr(machine_id)
        return Response(content=qr_bytes, media_type="image/png")
    except ImportError:
        raise HTTPException(status_code=500, detail="QR library not installed")


@router.get("/process-flow/{card_id}", response_model=QRCodeResponse)
async def get_process_flow_qr(
    card_id: int,
    current_user: CurrentUser,
) -> QRCodeResponse:
    """Generate QR code for process flow card."""
    try:
        qr_bytes, qr_code = qr_service.generate_process_flow_qr(card_id)
        content = qr_service.generate_qr_content(qr_service.QRType.PROCESS_FLOW, card_id)
        import base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(qr_bytes).decode()}"

        return QRCodeResponse(
            qr_code=qr_code,
            content=content,
            image_base64=image_base64,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/process-flow/{card_id}/image")
async def get_process_flow_qr_image(
    card_id: int,
    current_user: CurrentUser,
) -> Response:
    """Get process flow QR code as PNG image."""
    try:
        qr_bytes, _ = qr_service.generate_process_flow_qr(card_id)
        return Response(content=qr_bytes, media_type="image/png")
    except ImportError:
        raise HTTPException(status_code=500, detail="QR library not installed")


@router.get("/material/{batch_id}/image")
async def get_material_qr_image(
    batch_id: str,
    current_user: CurrentUser,
) -> Response:
    """Get material batch QR code as PNG image."""
    try:
        qr_bytes, _ = qr_service.generate_material_qr(batch_id)
        return Response(content=qr_bytes, media_type="image/png")
    except ImportError:
        raise HTTPException(status_code=500, detail="QR library not installed")


@router.get("/part/{part_id}", response_model=QRCodeResponse)
async def get_part_qr(
    part_id: int,
    current_user: CurrentUser,
) -> QRCodeResponse:
    """Generate QR code for part."""
    try:
        qr_bytes, qr_code = qr_service.generate_part_qr(part_id)
        content = qr_service.generate_qr_content(qr_service.QRType.PART, part_id)
        import base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(qr_bytes).decode()}"

        return QRCodeResponse(
            qr_code=qr_code,
            content=content,
            image_base64=image_base64,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/part/{part_id}/image")
async def get_part_qr_image(
    part_id: int,
    current_user: CurrentUser,
) -> Response:
    """Get part QR code as PNG image."""
    try:
        qr_bytes, _ = qr_service.generate_part_qr(part_id)
        return Response(content=qr_bytes, media_type="image/png")
    except ImportError:
        raise HTTPException(status_code=500, detail="QR library not installed")


@router.get("/packaging/{record_id}", response_model=QRCodeResponse)
async def get_packaging_qr(
    record_id: int,
    current_user: CurrentUser,
) -> QRCodeResponse:
    """Generate QR code for packaging record."""
    try:
        qr_bytes, qr_code = qr_service.generate_packaging_qr(record_id)
        content = qr_service.generate_qr_content(qr_service.QRType.PACKAGING, record_id)
        import base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(qr_bytes).decode()}"

        return QRCodeResponse(
            qr_code=qr_code,
            content=content,
            image_base64=image_base64,
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packaging/{record_id}/image")
async def get_packaging_qr_image(
    record_id: int,
    current_user: CurrentUser,
) -> Response:
    """Get packaging record QR code as PNG image."""
    try:
        qr_bytes, _ = qr_service.generate_packaging_qr(record_id)
        return Response(content=qr_bytes, media_type="image/png")
    except ImportError:
        raise HTTPException(status_code=500, detail="QR library not installed")
