"""Business logic for machine management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.machine import Machine, MachineState


async def get_machine_by_id(
    db: AsyncSession,
    machine_id: int,
) -> Machine | None:
    """Get machine by ID with current tooling info."""
    result = await db.execute(
        select(Machine)
        .options(joinedload(Machine.current_tooling))
        .where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_machine_by_qr(
    db: AsyncSession,
    qr_content: str,
) -> Machine | None:
    """Resolve machine from QR content string.

    QR format: MCN:{machine_id}:{timestamp}:{machine_no}
    """
    from src.services.qr_service import parse_qr_content, QRCodePrefix

    parsed = parse_qr_content(qr_content)
    if not parsed or parsed.get("prefix") != QRCodePrefix.MACHINE.value:
        return None

    machine_id = parsed.get("id")
    if not machine_id:
        return None

    return await get_machine_by_id(db, machine_id)


async def generate_machine_qr(
    db: AsyncSession,
    machine_id: int,
) -> dict:
    """Generate QR content and image for a machine.

    Returns dict with machine info, qr_content, and qr_image_base64.
    """
    from src.services.qr_service import generate_machine_qr as gen_qr_content
    from src.services.qr_service import generate_qr_base64

    machine = await get_machine_by_id(db, machine_id)
    if not machine:
        raise ValueError(f"Machine not found: {machine_id}")

    qr_content = gen_qr_content(machine.id, machine.machine_no)
    qr_image_base64 = generate_qr_base64(qr_content)

    return {
        "machine_id": machine.id,
        "machine_no": machine.machine_no,
        "name": machine.name,
        "machine_type": machine.machine_type,
        "tonnage": machine.tonnage,
        "location": machine.location,
        "state": machine.state.value if machine.state else None,
        "qr_content": qr_content,
        "qr_image_base64": qr_image_base64,
    }


async def get_machine_scan_result(
    db: AsyncSession,
    machine_id: int,
    operator_id: int | None = None,
) -> dict:
    """Return machine scan result (full status + recent scan history).

    Also records the scan event in qr_scan_logs.
    """
    from src.services.qr_service import generate_machine_qr
    from src.services.qr_service import generate_qr_base64

    machine = await get_machine_by_id(db, machine_id)
    if not machine:
        raise ValueError(f"Machine not found: {machine_id}")

    qr_content = generate_machine_qr(machine.id, machine.machine_no)
    qr_image_base64 = generate_qr_base64(qr_content)

    # Record scan log
    await _record_scan_log(
        db,
        entity_id=machine.id,
        entity_no=machine.machine_no,
        operation="query",
        operator_id=operator_id,
        notes=f"Scan machine QR: {machine.machine_no}",
    )
    await db.commit()

    # Get recent scan history
    scan_history = await _get_scan_history(db, "MCN", machine.id, limit=10)

    return {
        "machine": machine,
        "qr_content": qr_content,
        "qr_image_base64": qr_image_base64,
        "scan_history": scan_history,
    }


async def _record_scan_log(
    db: AsyncSession,
    entity_id: int,
    entity_no: str,
    operation: str,
    operator_id: int | None = None,
    notes: str | None = None,
):
    """Record a QR scan event."""
    from src.models.warehouse import QRScanLog

    log = QRScanLog(
        scan_type="MCN",
        entity_id=entity_id,
        entity_no=entity_no,
        operator_id=operator_id,
        operation=operation,
        notes=notes,
    )
    db.add(log)


async def _get_scan_history(
    db: AsyncSession,
    scan_type: str,
    entity_id: int,
    limit: int = 10,
):
    """Get recent scan history for an entity."""
    from src.models.warehouse import QRScanLog

    result = await db.execute(
        select(QRScanLog)
        .where(QRScanLog.scan_type == scan_type, QRScanLog.entity_id == entity_id)
        .order_by(QRScanLog.scanned_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
