"""Business logic for production planning and reporting."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.machine import Machine, MachineState
from app.models.part import Part
from app.models.production import (
    PlanMachineAssignment,
    PlanStatus,
    ProductionPlan,
)
from app.models.user import User


def generate_plan_no() -> str:
    """Generate a unique production plan number."""
    now = datetime.utcnow()
    prefix = now.strftime("%Y%m%d")
    return f"PP-{prefix}-{now.strftime('%H%M%S')}"


async def create_plan(
    db: AsyncSession,
    part_id: int,
    total_qty: int,
    planned_start_date: Optional[datetime] = None,
    planned_end_date: Optional[datetime] = None,
    priority: int = 0,
    notes: Optional[str] = None,
    created_by: Optional[int] = None,
) -> ProductionPlan:
    """Create a new production plan."""
    plan = ProductionPlan(
        part_id=part_id,
        total_qty=total_qty,
        due_date=planned_end_date or planned_start_date,
        plan_order=priority,
        remark=notes,
        created_by=created_by,
        status=PlanStatus.PLANNED.value,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def create_material_ready_plan(
    db: AsyncSession,
    *,
    part_id: int,
    paired_part_id: Optional[int] = None,
    is_left_right_pair: bool = False,
    paired_customer_part_no_snapshot: Optional[str] = None,
    paired_part_name_snapshot: Optional[str] = None,
    total_qty: int,
    twp_source_spec_id: int,
    twp_value: str,
    twp_thickness: float,
    twp_width: float,
    twp_pitch: float,
    twp_cavity_count: int,
    twp_manual_override: bool,
    material_name_snapshot: Optional[str],
    material_density_snapshot: Optional[float],
    is_urgent: bool,
    notes: Optional[str],
    created_by: Optional[int],
) -> ProductionPlan:
    """Create a plan waiting for material readiness confirmation.

    The source values are snapshotted so later part/TWP edits cannot silently
    alter a submitted purchasing requirement.
    """
    plan = ProductionPlan(
        part_id=part_id,
        paired_part_id=paired_part_id,
        is_left_right_pair=is_left_right_pair,
        paired_customer_part_no_snapshot=paired_customer_part_no_snapshot,
        paired_part_name_snapshot=paired_part_name_snapshot,
        total_qty=total_qty,
        progress_qty=0,
        status=PlanStatus.PLANNED.value,
        is_urgent=is_urgent,
        material_status="pending",
        material_calculation_mode="manual",
        twp_source_spec_id=twp_source_spec_id,
        twp_value=twp_value,
        twp_thickness=twp_thickness,
        twp_width=twp_width,
        twp_pitch=twp_pitch,
        twp_cavity_count=twp_cavity_count,
        twp_manual_override=twp_manual_override,
        material_name_snapshot=material_name_snapshot,
        material_density_snapshot=material_density_snapshot,
        remark=notes,
        created_by=created_by,
    )
    db.add(plan)
    await db.flush()
    return plan


async def update_material_ready_plan(
    db: AsyncSession,
    plan: ProductionPlan,
    *,
    total_qty: Optional[int] = None,
    is_urgent: Optional[bool] = None,
    notes: Optional[str] = None,
    material_calculation_mode: Optional[str] = None,
) -> ProductionPlan:
    """Update a plan without incorrectly reopening it for a quantity decrease."""
    if total_qty is not None:
        previous_qty = plan.total_qty or 0
        plan.total_qty = total_qty
        confirmed_qty = plan.material_confirmed_qty or 0
        if total_qty > previous_qty and confirmed_qty < total_qty:
            plan.material_status = "pending"
        elif total_qty <= previous_qty and plan.material_status == "ready":
            # A lower target is already covered by the last material readiness check.
            plan.material_status = "ready"
    if is_urgent is not None:
        plan.is_urgent = is_urgent
    if notes is not None:
        plan.remark = notes
    if material_calculation_mode is not None:
        plan.material_calculation_mode = material_calculation_mode

    await db.flush()
    return plan


async def confirm_material_ready(
    db: AsyncSession,
    plans: Sequence[ProductionPlan],
    *,
    confirmed_by: int,
    note: Optional[str],
) -> list[ProductionPlan]:
    """Mark the selected plans as material-ready in one transaction."""
    confirmed_at = datetime.utcnow()
    for plan in plans:
        plan.material_status = "ready"
        plan.material_confirmed_qty = plan.total_qty
        plan.material_confirmed_by = confirmed_by
        plan.material_confirmed_at = confirmed_at
        plan.material_confirmation_note = note
    await db.flush()
    return list(plans)


async def get_plan_by_id(
    db: AsyncSession,
    plan_id: int,
) -> Optional[ProductionPlan]:
    """Get a production plan by ID."""
    result = await db.execute(
        select(ProductionPlan)
        .options(
            selectinload(ProductionPlan.assignments).joinedload(PlanMachineAssignment.machine),
        )
        .where(ProductionPlan.id == plan_id)
    )
    return result.scalar_one_or_none()


async def get_plans(
    db: AsyncSession,
    status: Optional[PlanStatus] = None,
    part_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[ProductionPlan]:
    """Get production plans with optional filters."""
    query = (
        select(ProductionPlan)
        .options(
            selectinload(ProductionPlan.assignments),
        )
        .where(True)
    )

    if status:
        query = query.where(ProductionPlan.status == status)
    if part_id:
        query = query.where(ProductionPlan.part_id == part_id)

    query = query.order_by(
        ProductionPlan.plan_order.asc().nullslast(),
        ProductionPlan.due_date.asc().nullslast(),
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_plan(
    db: AsyncSession,
    plan: ProductionPlan,
    total_qty: Optional[int] = None,
    planned_start_date: Optional[datetime] = None,
    planned_end_date: Optional[datetime] = None,
    priority: Optional[int] = None,
    notes: Optional[str] = None,
    status: Optional[PlanStatus] = None,
) -> ProductionPlan:
    """Update a production plan."""
    if total_qty is not None:
        plan.total_qty = total_qty
    if planned_end_date is not None:
        plan.due_date = planned_end_date
    elif planned_start_date is not None:
        plan.due_date = planned_start_date
    if priority is not None:
        plan.plan_order = priority
    if notes is not None:
        plan.remark = notes
    if status is not None:
        plan.status = status.value

    await db.commit()
    await db.refresh(plan)
    return plan


async def assign_machine(
    db: AsyncSession,
    plan: ProductionPlan,
    machine_id: int,
    assigned_qty: int,
    assigned_by: Optional[User] = None,
) -> PlanMachineAssignment:
    """Assign a machine to a production plan."""
    assignment = PlanMachineAssignment(
        plan_id=plan.id,
        machine_id=machine_id,
        assigned_qty=assigned_qty,
        assigned_by=assigned_by.id if assigned_by else None,
    )
    db.add(assignment)

    # Update machine state to running if not already
    machine_result = await db.execute(
        select(Machine).where(Machine.id == machine_id)
    )
    machine = machine_result.scalar_one_or_none()
    if machine and machine.state == MachineState.IDLE:
        machine.state = MachineState.RUNNING

    # Update plan status if first assignment
    if len(plan.assignments) == 0:
        plan.status = PlanStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def unassign_machine(
    db: AsyncSession,
    assignment: PlanMachineAssignment,
) -> PlanMachineAssignment:
    """Unassign a machine from a production plan."""
    assignment.is_active = False

    # Update machine state back to idle
    machine_result = await db.execute(
        select(Machine).where(Machine.id == assignment.machine_id)
    )
    machine = machine_result.scalar_one_or_none()
    if machine and machine.state == MachineState.RUNNING:
        machine.state = MachineState.IDLE

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def update_plan_completed_qty(
    db: AsyncSession,
    plan: ProductionPlan,
    added_qty: int,
) -> ProductionPlan:
    """Update the completed quantity of a plan."""
    plan.progress_qty = (plan.progress_qty or 0) + added_qty

    if plan.progress_qty >= (plan.total_qty or 0):
        plan.status = PlanStatus.COMPLETED.value

    await db.commit()
    await db.refresh(plan)
    return plan


async def cancel_plan(
    db: AsyncSession,
    plan: ProductionPlan,
) -> ProductionPlan:
    """Cancel a production plan."""
    plan.status = PlanStatus.CANCELLED.value

    # Reset machine states
    for assignment in plan.assignments:
        if assignment.is_active:
            machine_result = await db.execute(
                select(Machine).where(Machine.id == assignment.machine_id)
            )
            machine = machine_result.scalar_one_or_none()
            if machine and machine.state == MachineState.RUNNING:
                machine.state = MachineState.IDLE
            assignment.is_active = False

    await db.commit()
    await db.refresh(plan)
    return plan
