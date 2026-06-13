"""QR code API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.machine import Machine
from app.models.part import Part
from app.models.production import ProcessFlowCard
from app.models.tooling import Tooling
from app.schemas.qr import (
    QRGenerateRequest,
    QRGenerateResponse,
    QRLookupResponse,
    QRMaterialResponse,
    QRMachineResponse,
    QRProcessFlowResponse,
)
from app.services import qr_service

router = APIRouter(prefix="/qr", tags=["QR Code"])


async def lookup_entity(db: AsyncSession, prefix: str, entity_id: int) -> dict:
    """Look up entity by prefix and ID."""
    if prefix == "MAT":
        # Material batch lookup (handled by warehouse service)
        from app.services.warehouse_service import get_batch_by_id

        batch = await get_batch_by_id(db, entity_id)
        if batch:
            return {
                "entity_type": "material_batch",
                "entity_data": {
                    "batch_id": batch.id,
                    "batch_no": batch.batch_no,
                    "material_id": batch.material_id,
                    "quantity": batch.quantity,
                    "status": batch.status.value if hasattr(batch, "status") else None,
                },
            }

    elif prefix == "MCN":
        result = await db.execute(
            select(Machine).where(Machine.id == entity_id)
        )
        machine = result.scalar_one_or_none()
        if machine:
            return {
                "entity_type": "machine",
                "entity_data": {
                    "machine_id": machine.id,
                    "machine_no": machine.machine_no,
                    "machine_name": machine.machine_name,
                    "status": machine.status.value if hasattr(machine, "status") else None,
                },
            }

    elif prefix == "PFC":
        result = await db.execute(
            select(ProcessFlowCard).where(ProcessFlowCard.id == entity_id)
        )
        card = result.scalar_one_or_none()
        if card:
            return {
                "entity_type": "process_flow_card",
                "entity_data": {
                    "card_id": card.id,
                    "card_no": card.card_no,
                    "part_id": card.part_id,
                    "plan_id": card.plan_id,
                    "status": card.status.value if hasattr(card, "status") else None,
                },
            }

    elif prefix == "PRT":
        result = await db.execute(select(Part).where(Part.id == entity_id))
        part = result.scalar_one_or_none()
        if part:
            return {
                "entity_type": "part",
                "entity_data": {
                    "part_id": part.id,
                    "part_number": part.part_number,
                    "internal_name": part.internal_name,
                    "status": part.status.value if hasattr(part, "status") else None,
                },
            }

    elif prefix == "TLG":
        result = await db.execute(
            select(Tooling).where(Tooling.id == entity_id)
        )
        tooling = result.scalar_one_or_none()
        if tooling:
            return {
                "entity_type": "tooling",
                "entity_data": {
                    "tooling_id": tooling.id,
                    "tooling_no": tooling.tooling_no,
                    "tooling_name": tooling.tooling_name,
                    "status": tooling.status.value if hasattr(tooling, "status") else None,
                },
            }

    return {"entity_type": None, "entity_data": None}


@router.get("/lookup", response_model=QRLookupResponse)
async def lookup_qr_code(
    code: str = Query(..., description="QR code content to look up"),
    db: DbSession,
    current_user: CurrentUser,
) -> QRLookupResponse:
    """Look up QR code and return entity information.

    Supports MAT-, MCN-, PFC- prefixes for different entity types.
    """
    # Parse QR content
    parsed = qr_service.parse_qr_content(code)

    if not parsed:
        return QRLookupResponse(
            found=False,
            error="Invalid QR code format",
        )

    prefix = parsed.get("prefix", "").upper()
    entity_id = parsed.get("entity_id")

    if not entity_id:
        return QRLookupResponse(
            found=False,
            error="Invalid entity ID in QR code",
        )

    # Validate prefix
    prefix_type = qr_service.get_prefix_type(prefix)
    if not prefix_type:
        return QRLookupResponse(
            found=False,
            prefix=prefix,
            error=f"Unknown QR prefix: {prefix}",
        )

    # Look up entity
    result = await lookup_entity(db, prefix, entity_id)

    if result["entity_type"]:
        return QRLookupResponse(
            found=True,
            prefix=prefix,
            entity_id=entity_id,
            entity_type=result["entity_type"],
            entity_data=result["entity_data"],
        )

    return QRLookupResponse(
        found=False,
        prefix=prefix,
        entity_id=entity_id,
        error=f"Entity not found: {prefix}:{entity_id}",
    )


@router.post("/generate", response_model=QRGenerateResponse)
async def generate_qr_code(
    data: QRGenerateRequest,
    current_user: CurrentUser,
) -> QRGenerateResponse:
    """Generate QR code for an entity.

    Creates a QR code image and optionally uploads to cloud storage.
    """
    prefix_type = qr_service.get_prefix_type(data.prefix)
    if not prefix_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid prefix: {data.prefix}",
        )

    # Generate content
    extra = data.extra_data or {}
    content = qr_service.generate_qr_content(prefix_type, data.entity_id, **extra)

    # Generate image
    image_base64 = qr_service.generate_qr_base64(content)

    # Try to upload to cloud
    filename = f"{data.prefix}_{data.entity_id}"
    url = await qr_service.upload_qr_to_cos(content, filename)

    return QRGenerateResponse(
        content=content,
        image_base64=image_base64,
        url=url,
    )


@router.get("/material/{batch_id}", response_model=QRMaterialResponse)
async def get_material_qr(
    batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QRMaterialResponse:
    """Generate QR code for material batch."""
    from app.services.warehouse_service import get_batch_by_id

    batch = await get_batch_by_id(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Material batch not found")

    content = qr_service.generate_material_qr(batch.id, batch.batch_no)
    image_base64 = qr_service.generate_qr_base64(content)

    return QRMaterialResponse(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        qr_content=content,
        image_base64=image_base64,
    )


@router.get("/machine/{machine_id}", response_model=QRMachineResponse)
async def get_machine_qr(
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QRMachineResponse:
    """Generate QR code for machine."""
    result = await db.execute(
        select(Machine).where(Machine.id == machine_id)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    content = qr_service.generate_machine_qr(machine.id, machine.machine_no)
    image_base64 = qr_service.generate_qr_base64(content)

    return QRMachineResponse(
        machine_id=machine.id,
        machine_no=machine.machine_no,
        qr_content=content,
        image_base64=image_base64,
    )


@router.get("/process-flow/{card_id}", response_model=QRProcessFlowResponse)
async def get_process_flow_qr(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> QRProcessFlowResponse:
    """Generate QR code for process flow card."""
    result = await db.execute(
        select(ProcessFlowCard).where(ProcessFlowCard.id == card_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Process flow card not found")

    content = qr_service.generate_process_flow_qr(card.id, card.card_no)
    image_base64 = qr_service.generate_qr_base64(content)

    return QRProcessFlowResponse(
        card_id=card.id,
        card_no=card.card_no,
        qr_content=content,
        image_base64=image_base64,
    )


@router.get("/part/{part_id}")
async def get_part_qr(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Generate QR code for part."""
    result = await db.execute(select(Part).where(Part.id == part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    content = qr_service.generate_part_qr(part.id, part.part_number)
    image_base64 = qr_service.generate_qr_base64(content)

    return {
        "part_id": part.id,
        "part_number": part.part_number,
        "qr_content": content,
        "image_base64": image_base64,
    }
