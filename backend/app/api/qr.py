"""QR code API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.machine import Machine
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
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


# ── Manual Lookup (T028) ─────────────────────────────────────────────────────

async def _manual_lookup(
    db: AsyncSession,
    entity_type: str,
    code: str,
) -> dict:
    """Manual lookup by entity type and any identifier code.

    T028: Enables manual entry when QR code is damaged.
    Tries multiple lookup strategies per entity type.
    """
    if entity_type == "MAT":
        # Try: batch_no, then batch_id, then qr_code
        from app.services import material_batch_service
        batch = await material_batch_service.get_batch_by_no(db, code)
        if batch:
            return _build_material_batch_data(batch)
        try:
            batch_id = int(code)
            batch = await material_batch_service.get_batch_by_id(db, batch_id)
            if batch:
                return _build_material_batch_data(batch)
        except ValueError:
            pass
        # Try by qr_code
        from app.models.warehouse import MaterialBatch
        result = await db.execute(
            select(MaterialBatch).where(MaterialBatch.qr_code == code)
        )
        batch = result.scalar_one_or_none()
        if batch:
            return _build_material_batch_data(batch)

    elif entity_type == "MCN":
        result = await db.execute(
            select(Machine).where(Machine.machine_no == code)
        )
        machine = result.scalar_one_or_none()
        if not machine:
            try:
                mid = int(code)
                result = await db.execute(
                    select(Machine).where(Machine.id == mid)
                )
                machine = result.scalar_one_or_none()
            except ValueError:
                pass
        if machine:
            return {
                "found": True,
                "entity_type": "machine",
                "entity_data": {
                    "machine_id": machine.id,
                    "machine_no": machine.machine_no,
                    "machine_name": machine.name,
                    "state": machine.state.value if machine.state else None,
                    "tonnage": machine.tonnage,
                    "location": machine.location,
                },
            }

    elif entity_type == "PFC":
        result = await db.execute(
            select(ProcessFlowCard).where(ProcessFlowCard.card_no == code)
        )
        card = result.scalar_one_or_none()
        if not card:
            try:
                cid = int(code)
                result = await db.execute(
                    select(ProcessFlowCard).where(ProcessFlowCard.id == cid)
                )
                card = result.scalar_one_or_none()
            except ValueError:
                pass
        if card:
            return {
                "found": True,
                "entity_type": "process_flow_card",
                "entity_data": {
                    "card_id": card.id,
                    "card_no": card.card_no,
                    "part_id": card.part_id,
                    "session_id": card.session_id,
                    "status": card.status.value if card.status else None,
                    "good_qty": card.good_qty,
                },
            }

    elif entity_type == "PRT":
        result = await db.execute(select(PartCustomerAlias).where(
            PartCustomerAlias.customer_part_no == code,
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.data_quality_status == "approved",
        ))
        alias = result.scalars().first()
        part = await db.get(Part, alias.part_id) if alias else None
        if not part:
            try:
                pid = int(code)
                result = await db.execute(select(Part).where(Part.id == pid))
                part = result.scalar_one_or_none()
            except ValueError:
                pass
        if part:
            return {
                "found": True,
                "entity_type": "part",
                "entity_data": {
                    "part_id": part.id,
                    "customer_part_no": alias.customer_part_no if alias else None,
                    "part_name": part.internal_name,
                },
            }

    elif entity_type == "TLG":
        result = await db.execute(
            select(Tooling).where(Tooling.tooling_number == code)
        )
        tooling = result.scalar_one_or_none()
        if not tooling:
            try:
                tid = int(code)
                result = await db.execute(
                    select(Tooling).where(Tooling.id == tid)
                )
                tooling = result.scalar_one_or_none()
            except ValueError:
                pass
        if tooling:
            return {
                "found": True,
                "entity_type": "tooling",
                "entity_data": {
                    "tooling_id": tooling.id,
                    "tooling_number": tooling.tooling_number,
                    "tooling_name": tooling.tooling_name,
                },
            }

    return {"found": False, "error": f"Not found: {entity_type}:{code}"}


def _build_material_batch_data(batch) -> dict:
    """Build material batch lookup data."""
    return {
        "found": True,
        "entity_type": "material_batch",
        "entity_data": {
            "batch_id": batch.id,
            "batch_no": batch.batch_no,
            "qr_code": batch.qr_code,
            "material_name": batch.material.name if batch.material else None,
            "supplier_name": (
                batch.supplier.name if batch.supplier else batch.supplier_name
            ),
            "current_weight": (
                float(batch.current_weight) if batch.current_weight else None
            ),
            "status": batch.status.value if batch.status else None,
        },
    }


# ── Auto Lookup ──────────────────────────────────────────────────────────────

async def lookup_entity(db: AsyncSession, prefix: str, entity_id: int) -> dict:
    """Look up entity by prefix and ID."""
    if prefix == "MAT":
        from app.services import material_batch_service

        batch = await material_batch_service.get_batch_by_id(db, entity_id)
        if batch:
            return _build_material_batch_data(batch)

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
                    "machine_name": machine.name,
                    "state": machine.state.value if machine.state else None,
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
                    "session_id": card.session_id,
                    "status": card.status.value if card.status else None,
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
                    "part_name": part.internal_name,
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
                    "tooling_number": tooling.tooling_number,
                    "tooling_name": tooling.tooling_name,
                    "status": tooling.status,
                },
            }

    return {"entity_type": None, "entity_data": None}


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/lookup", response_model=QRLookupResponse)
async def lookup_qr_code(
    db: DbSession,
    current_user: CurrentUser,
    code: str = Query(..., description="QR code content or entity identifier to look up"),
    manual: bool = Query(default=False, description="Enable manual lookup mode (type+code)"),
    type: Optional[str] = Query(default=None, description="Entity type for manual lookup: MAT, MCN, PFC, PRT, TLG"),
) -> QRLookupResponse:
    """Look up QR code and return entity information.

    Supports two modes:
    - Auto mode (default): parse QR code string to extract prefix + entity ID
    - Manual mode (?manual=true): look up by type + code (code can be any identifier)

    T028: Enables manual entry when QR code is damaged.
    """
    if manual:
        if not type:
            return QRLookupResponse(
                found=False,
                error="type parameter required when manual=true",
            )
        result = await _manual_lookup(db, type.upper(), code)
        return QRLookupResponse(
            found=result.get("found", False),
            entity_type=result.get("entity_type"),
            entity_data=result.get("entity_data"),
            error=result.get("error"),
        )

    # Auto mode: parse QR content
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

    prefix_type = qr_service.get_prefix_type(prefix)
    if not prefix_type:
        return QRLookupResponse(
            found=False,
            prefix=prefix,
            error=f"Unknown QR prefix: {prefix}",
        )

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

    extra = data.extra_data or {}
    content = qr_service.generate_qr_content(prefix_type, data.entity_id, **extra)
    image_base64 = qr_service.generate_qr_base64(content)
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
    from app.services import material_batch_service

    batch = await material_batch_service.get_batch_by_id(db, batch_id)
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

    alias = (await db.execute(select(PartCustomerAlias).where(
        PartCustomerAlias.part_id == part.id,
        PartCustomerAlias.is_active == True,
        PartCustomerAlias.data_quality_status == "approved",
    ).order_by(PartCustomerAlias.id))).scalars().first()
    if not alias:
        raise HTTPException(status_code=409, detail="Part has no approved customer part number")
    content = qr_service.generate_part_qr(part.id, alias.customer_part_no)
    image_base64 = qr_service.generate_qr_base64(content)

    return {
        "part_id": part.id,
        "customer_part_no": alias.customer_part_no,
        "qr_content": content,
        "image_base64": image_base64,
    }
