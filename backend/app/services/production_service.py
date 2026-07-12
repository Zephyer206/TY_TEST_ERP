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
    plan_no = generate_plan_no()

    plan = ProductionPlan(
        plan_no=plan_no,
        part_id=part_id,
        total_qty=total_qty,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        priority=priority,
        notes=notes,
        created_by=created_by,
        status=PlanStatus.PLANNED,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


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
        .where(ProductionPlan.id == plan_id, ProductionPlan.is_deleted == False)
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
        .where(ProductionPlan.is_deleted == False)
    )

    if status:
        query = query.where(ProductionPlan.status == status)
    if part_id:
        query = query.where(ProductionPlan.part_id == part_id)

    query = query.order_by(
        ProductionPlan.priority.desc(),
        ProductionPlan.planned_end_date.asc().nullslast(),
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
    if planned_start_date is not None:
        plan.planned_start_date = planned_start_date
    if planned_end_date is not None:
        plan.planned_end_date = planned_end_date
    if priority is not None:
        plan.priority = priority
    if notes is not None:
        plan.notes = notes
    if status is not None:
        plan.status = status

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
    plan.completed_qty += added_qty

    if plan.completed_qty >= plan.total_qty:
        plan.status = PlanStatus.COMPLETED

    await db.commit()
    await db.refresh(plan)
    return plan


async def cancel_plan(
    db: AsyncSession,
    plan: ProductionPlan,
) -> ProductionPlan:
    """Cancel a production plan."""
    plan.status = PlanStatus.CANCELLED

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
