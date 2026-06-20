"""Business logic for production sessions and reporting."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.machine import Machine, MachineState
from app.models.part import Part
from app.models.production import (
    ProductionReport,
    ProductionSession,
    SessionStatus,
)
from app.models.tooling import Tooling


def generate_session_no() -> str:
    """Generate a unique production session number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"PS-{prefix}-{now.strftime('%H%M%S')}"


async def verify_material_tooling_match(
    db: AsyncSession,
    machine_id: int,
    part_id: int,
    material_batch_id: Optional[int] = None,
) -> dict:
    """Verify material matches tooling on machine for the part.

    严格校验四字段：material_type + thickness + width + cavity_count（澄清 2026-06-20 #3）
    Returns dict with is_match, message, mismatches list.
    """
    from app.models.warehouse import MaterialBatch

    result: dict = {"is_match": True, "message": "OK", "tooling_id": None, "mismatches": []}

    machine_result = await db.execute(select(Machine).where(Machine.id == machine_id))
    machine = machine_result.scalar_one_or_none()
    if not machine:
        return {**result, "is_match": False, "message": "机台不存在"}
    if not machine.current_tooling_id:
        return {**result, "is_match": False, "message": "机台未上模"}

    tooling_result = await db.execute(select(Tooling).where(Tooling.id == machine.current_tooling_id))
    tooling = tooling_result.scalar_one_or_none()
    if not tooling:
        return {**result, "is_match": False, "message": "模具不存在"}
    result["tooling_id"] = tooling.id

    if not material_batch_id:
        return result

    part_result = await db.execute(select(Part).where(Part.id == part_id))
    part = part_result.scalar_one_or_none()

    batch_result = await db.execute(select(MaterialBatch).where(MaterialBatch.id == material_batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        return {**result, "is_match": False, "message": "原料批次不存在"}

    mismatches = []
    if part:
        # 材质
        if part.material and batch.material_name and part.material != batch.material_name:
            mismatches.append(f"材质不符：期望 {part.material}，实际 {batch.material_name}")
        # 厚度
        if part.thickness and batch.thickness and abs(part.thickness - batch.thickness) > 0.01:
            mismatches.append(f"厚度不符：期望 {part.thickness}mm，实际 {batch.thickness}mm")
        # 宽度
        if part.width and batch.width and abs(part.width - batch.width) > 0.5:
            mismatches.append(f"宽度不符：期望 {part.width}mm，实际 {batch.width}mm")
        # 穴数
        if part.cavity_count and tooling.cavity_count and part.cavity_count != tooling.cavity_count:
            mismatches.append(f"穴数不符：期望 {part.cavity_count}，模具 {tooling.cavity_count}")

    if mismatches:
        result["is_match"] = False
        result["message"] = "；".join(mismatches)
        result["mismatches"] = mismatches

    return result


async def start_session(
    db: AsyncSession,
    machine_id: int,
    part_id: int,
    material_batch_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    force_start: bool = False,
) -> ProductionSession:
    """Start a new production session.

    Args:
        force_start: If True, skip material matching verification
    """
    from app.models.production import PlanMachineAssignment, ProductionPlan
    from app.models.warehouse import MaterialBatch

    # Verify machine
    machine_result = await db.execute(
        select(Machine).where(Machine.id == machine_id)
    )
    machine = machine_result.scalar_one_or_none()
    if not machine:
        raise ValueError("Machine not found")

    # Verify part
    part_result = await db.execute(
        select(Part).where(Part.id == part_id)
    )
    part = part_result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    # Get tooling from machine
    tooling_id = machine.current_tooling_id

    # Verify material matching if not forced
    if material_batch_id and not force_start:
        match_result = await verify_material_tooling_match(
            db, machine_id, part_id, material_batch_id
        )
        if not match_result["is_match"]:
            raise ValueError(f"Material mismatch: {match_result['message']}")

    session_no = generate_session_no()

    session = ProductionSession(
        session_no=session_no,
        plan_id=plan_id,
        machine_id=machine_id,
        tooling_id=tooling_id,
        part_id=part_id,
        material_batch_id=material_batch_id,
        status=SessionStatus.ACTIVE,
        started_at=datetime.utcnow(),
        operator_id=operator_id,
    )
    db.add(session)

    # Update machine state
    if machine.state == MachineState.IDLE:
        machine.state = MachineState.RUNNING

    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_id(
    db: AsyncSession,
    session_id: int,
) -> Optional[ProductionSession]:
    """Get a production session by ID."""
    result = await db.execute(
        select(ProductionSession)
        .options(
            joinedload(ProductionSession.machine),
            joinedload(ProductionSession.tooling),
            joinedload(ProductionSession.part),
            selectinload(ProductionSession.reports),
        )
        .where(ProductionSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def get_active_sessions(
    db: AsyncSession,
    machine_id: Optional[int] = None,
    part_id: Optional[int] = None,
) -> Sequence[ProductionSession]:
    """Get active production sessions."""
    query = (
        select(ProductionSession)
        .options(
            joinedload(ProductionSession.machine),
            joinedload(ProductionSession.tooling),
            joinedload(ProductionSession.part),
        )
        .where(ProductionSession.status == SessionStatus.ACTIVE)
    )

    if machine_id:
        query = query.where(ProductionSession.machine_id == machine_id)
    if part_id:
        query = query.where(ProductionSession.part_id == part_id)

    result = await db.execute(query)
    return result.scalars().all()


async def submit_report(
    db: AsyncSession,
    session: ProductionSession,
    strokes: int,
    cavity_count: int,
    good_qty: int,
    reject_qty: int,
    material_used: Optional[float] = None,
    notes: Optional[str] = None,
    operator_id: Optional[int] = None,
) -> ProductionReport:
    """Submit a production report within a session.

    Output = strokes × cavity_count
    行锁防止并发丢失（澄清 2026-06-20 #22）
    """
    # Lock the session row for the duration of this transaction
    locked = await db.execute(
        select(ProductionSession)
        .where(ProductionSession.id == session.id)
        .with_for_update()
    )
    session = locked.scalar_one()

    if session.status != SessionStatus.ACTIVE:
        raise ValueError(f"Session not active: {session.status.value}")

    output = strokes * cavity_count

    report = ProductionReport(
        session_id=session.id,
        strokes=strokes,
        cavity_count=cavity_count,
        output=output,
        good_qty=good_qty,
        reject_qty=reject_qty,
        material_used=material_used,
        notes=notes,
        operator_id=operator_id,
    )
    db.add(report)

    # Update session totals
    session.total_strokes += strokes
    session.total_output += output
    session.good_qty += good_qty
    session.reject_qty += reject_qty

    await db.commit()
    await db.refresh(report)
    return report


async def close_session(
    db: AsyncSession,
    session: ProductionSession,
) -> ProductionSession:
    """Close a production session and optionally generate process flow card."""
    if session.status != SessionStatus.ACTIVE:
        raise ValueError(f"Session not active: {session.status.value}")

    session.status = SessionStatus.CLOSED
    session.closed_at = datetime.utcnow()
    session.work_hours = (session.closed_at - session.started_at).total_seconds() / 3600

    # Generate process flow card
    from app.services.process_flow_service import generate_process_flow_card

    flow_card = await generate_process_flow_card(db, session)
    session.process_flow_id = flow_card.id

    # Update plan completed quantity
    if session.plan_id:
        from app.services.production_service import update_plan_completed_qty, get_plan_by_id

        plan = await get_plan_by_id(db, session.plan_id)
        if plan:
            await update_plan_completed_qty(db, plan, session.good_qty)

    # Update machine state if no more active sessions
    active_sessions = await get_active_sessions(db, machine_id=session.machine_id)
    if not active_sessions:
        machine_result = await db.execute(
            select(Machine).where(Machine.id == session.machine_id)
        )
        machine = machine_result.scalar_one_or_none()
        if machine and machine.state == MachineState.RUNNING:
            machine.state = MachineState.IDLE

    await db.commit()
    await db.refresh(session)
    return session


async def cancel_session(
    db: AsyncSession,
    session: ProductionSession,
) -> ProductionSession:
    """Cancel a production session."""
    if session.status == SessionStatus.CLOSED:
        raise ValueError("Cannot cancel a closed session")

    session.status = SessionStatus.CANCELLED
    session.closed_at = datetime.utcnow()

    # Update machine state if no more active sessions
    active_sessions = await get_active_sessions(db, machine_id=session.machine_id)
    if not active_sessions:
        machine_result = await db.execute(
            select(Machine).where(Machine.id == session.machine_id)
        )
        machine = machine_result.scalar_one_or_none()
        if machine and machine.state == MachineState.RUNNING:
            machine.state = MachineState.IDLE

    await db.commit()
    await db.refresh(session)
    return session
