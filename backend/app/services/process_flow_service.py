"""Business logic for process flow card generation."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.machine import Machine
from app.models.part import Part
from app.models.production import (
    ProcessFlowCard,
    ProcessFlowStatus,
    ProductionSession,
)
from app.models.tooling import Tooling


def generate_card_no() -> str:
    """Generate a unique process flow card number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"PFC-{prefix}-{now.strftime('%H%M%S')}"


async def generate_process_flow_card(
    db: AsyncSession,
    session: ProductionSession,
) -> ProcessFlowCard:
    """Generate a process flow card from a closed production session."""
    # Get related entities
    machine_result = await db.execute(
        select(Machine).where(Machine.id == session.machine_id)
    )
    machine = machine_result.scalar_one_or_none()

    part_result = await db.execute(
        select(Part).where(Part.id == session.part_id)
    )
    part = part_result.scalar_one_or_none()

    tooling = None
    if session.tooling_id:
        tooling_result = await db.execute(
            select(Tooling).where(Tooling.id == session.tooling_id)
        )
        tooling = tooling_result.scalar_one_or_none()

    # Get material batch number if available
    material_batch_no = None
    if session.material_batch_id:
        from app.models.warehouse import MaterialBatch

        batch_result = await db.execute(
            select(MaterialBatch).where(MaterialBatch.id == session.material_batch_id)
        )
        batch = batch_result.scalar_one_or_none()
        if batch:
            material_batch_no = batch.batch_no

    card_no = generate_card_no()

    card = ProcessFlowCard(
        card_no=card_no,
        session_id=session.id,
        part_id=session.part_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        material_batch_no=material_batch_no,
        planned_qty=session.total_output,
        actual_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        status=ProcessFlowStatus.COMPLETED,
        start_time=session.started_at,
        end_time=session.closed_at,
        operator_id=session.operator_id,
    )
    db.add(card)
    await db.flush()

    # Generate QR code for the card
    from app.services.qr_service import generate_process_flow_qr
    card.qr_code = generate_process_flow_qr(card.id, card.card_no)

    await db.commit()
    await db.refresh(card)
    return card


async def get_process_flow_card(
    db: AsyncSession,
    card_id: int,
) -> Optional[ProcessFlowCard]:
    """Get a process flow card by ID."""
    result = await db.execute(
        select(ProcessFlowCard)
        .where(ProcessFlowCard.id == card_id)
    )
    return result.scalar_one_or_none()


async def get_process_flow_cards(
    db: AsyncSession,
    part_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    status: Optional[ProcessFlowStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[ProcessFlowCard]:
    """Get process flow cards with optional filters."""
    query = select(ProcessFlowCard).where(ProcessFlowCard.id > 0)

    if part_id:
        query = query.where(ProcessFlowCard.part_id == part_id)
    if machine_id:
        query = query.where(ProcessFlowCard.machine_id == machine_id)
    if status:
        query = query.where(ProcessFlowCard.status == status)

    query = query.order_by(ProcessFlowCard.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_card_status(
    db: AsyncSession,
    card: ProcessFlowCard,
    status: ProcessFlowStatus,
) -> ProcessFlowCard:
    """Update process flow card status."""
    card.status = status
    if status == ProcessFlowStatus.IN_PROGRESS and not card.start_time:
        card.start_time = datetime.utcnow()
    elif status == ProcessFlowStatus.COMPLETED and not card.end_time:
        card.end_time = datetime.utcnow()

    await db.commit()
    await db.refresh(card)
    return card


async def scan_process_flow_card(
    db: AsyncSession,
    card_id: int,
    operator_id: int | None = None,
) -> dict:
    """Scan a process flow card: get full info + QR image + scan history."""
    from app.services.qr_service import generate_process_flow_qr, generate_qr_base64

    card = await get_process_flow_card(db, card_id)
    if not card:
        raise ValueError(f"Process flow card not found: {card_id}")

    qr_content = generate_process_flow_qr(card.id, card.card_no)
    qr_image_base64 = generate_qr_base64(qr_content)

    # Record scan log
    from app.models.warehouse import QRScanLog
    log = QRScanLog(
        scan_type="PFC",
        entity_id=card.id,
        entity_no=card.card_no,
        operator_id=operator_id,
        operation="query",
        notes=f"Scan PFC: {card.card_no}",
    )
    db.add(log)
    await db.commit()

    # Get scan history
    history_result = await db.execute(
        select(QRScanLog)
        .where(QRScanLog.scan_type == "PFC", QRScanLog.entity_id == card.id)
        .order_by(QRScanLog.scanned_at.desc())
        .limit(20)
    )
    scan_history = history_result.scalars().all()

    return {
        "card": card,
        "qr_content": qr_content,
        "qr_image_base64": qr_image_base64,
        "scan_history": scan_history,
    }


async def reverse_trace_card(
    db: AsyncSession,
    card_id: int,
) -> dict:
    """Reverse trace: from card to session -> machine -> material batch -> supplier."""
    from app.models.warehouse import MaterialBatch, QRScanLog
    from app.services.session_service import get_session_by_id

    card = await get_process_flow_card(db, card_id)
    if not card:
        raise ValueError(f"Process flow card not found: {card_id}")

    # Get production session
    session = await get_session_by_id(db, card.session_id)

    # Get material batch info if available
    material_batch = None
    if card.material_batch_no:
        batch_result = await db.execute(
            select(MaterialBatch)
            .where(MaterialBatch.batch_no == card.material_batch_no)
        )
        material_batch = batch_result.scalar_one_or_none()

    # Get scan history
    history_result = await db.execute(
        select(QRScanLog)
        .where(QRScanLog.scan_type == "PFC", QRScanLog.entity_id == card.id)
        .order_by(QRScanLog.scanned_at.desc())
        .limit(20)
    )
    scan_history = history_result.scalars().all()

    return {
        "card": card,
        "session": session,
        "material_batch": material_batch,
        "scan_history": scan_history,
    }


async def confirm_inbound(
    db: AsyncSession,
    card_id: int,
    operator_id: int,
    notes: str | None = None,
) -> ProcessFlowCard:
    """Confirm inbound (OQC passed) for a process flow card.

    Records the scan event and updates the card with inbound metadata.
    """
    from app.models.warehouse import QRScanLog

    card = await get_process_flow_card(db, card_id)
    if not card:
        raise ValueError(f"Process flow card not found: {card_id}")

    if card.status not in (ProcessFlowStatus.COMPLETED, ProcessFlowStatus.IN_PROGRESS):
        raise ValueError(f"Card not eligible for inbound: {card.status.value}")

    card.inbound_time = datetime.utcnow()
    card.inbound_operator_id = operator_id
    card.inbound_notes = notes

    # Record scan log
    log = QRScanLog(
        scan_type="PFC",
        entity_id=card.id,
        entity_no=card.card_no,
        operator_id=operator_id,
        operation="inbound",
        notes=notes or "OQC passed, inbound confirmed",
    )
    db.add(log)
    await db.commit()
    await db.refresh(card)
    return card
