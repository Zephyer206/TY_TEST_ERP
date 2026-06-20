"""Business logic for production planning."""

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.machine import Machine, MachineState
from app.models.part import Part
from app.models.production import (
    MachineAssignment,
    PlanMachineAssignment,
    ProductionPlan,
    ProductionSession,
    PlanState,
    SessionState,
)
from app.models.tooling import Tooling
from app.models.user import User
from app.schemas.production import MachineAssignmentCreate, ProductionPlanCreate, ProductionPlanUpdate


def generate_plan_no(db: AsyncSession) -> str:
    """Generate a unique production plan number."""
    now = datetime.utcnow()
    return f"PP-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


async def create_plan(
    db: AsyncSession,
    data: ProductionPlanCreate,
    creator: User,
) -> ProductionPlan:
    """Create a new production plan."""
    # Validate part exists
    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise ValueError("Part not found")

    plan_no = generate_plan_no(db)

    plan = ProductionPlan(
        plan_no=plan_no,
        part_id=data.part_id,
        total_qty=data.total_qty,
        due_date=data.due_date,
        priority=data.priority,
        notes=data.notes,
        state=PlanState.PLANNED,
        created_by=creator.id if hasattr(creator, 'id') else None,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan_by_id(
    db: AsyncSession,
    plan_id: int,
) -> Optional[ProductionPlan]:
    """Get production plan by ID."""
    result = await db.execute(
        select(ProductionPlan)
        .options(selectinload(ProductionPlan.part))
        .where(ProductionPlan.id == plan_id, ProductionPlan.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_plans(
    db: AsyncSession,
    state: Optional[PlanState] = None,
    part_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[ProductionPlan]:
    """Get production plans with optional filters."""
    query = (
        select(ProductionPlan)
        .options(selectinload(ProductionPlan.part))
        .where(ProductionPlan.is_deleted == False)
    )

    if state:
        query = query.where(ProductionPlan.state == state)
    if part_id:
        query = query.where(ProductionPlan.part_id == part_id)

    query = query.order_by(
        ProductionPlan.priority.desc(),
        ProductionPlan.due_date.asc(),
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_plan(
    db: AsyncSession,
    plan: ProductionPlan,
    data: ProductionPlanUpdate,
) -> ProductionPlan:
    """Update production plan fields."""
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None and hasattr(plan, field):
            setattr(plan, field, value)

    await db.commit()
    await db.refresh(plan)
    return plan


async def assign_machine(
    db: AsyncSession,
    plan_id: int,
    data: MachineAssignmentCreate,
    assigner: User,
) -> PlanMachineAssignment:
    """Assign a machine to a production plan."""
    # Validate plan exists
    plan = await get_plan_by_id(db, plan_id)
    if not plan:
        raise ValueError("Production plan not found")

    # Validate machine exists and is available
    result = await db.execute(
        select(Machine).where(Machine.id == data.machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise ValueError("Machine not found")

    # Check if already assigned
    existing = await db.execute(
        select(PlanMachineAssignment)
        .where(
            PlanMachineAssignment.plan_id == plan_id,
            PlanMachineAssignment.machine_id == data.machine_id,
            PlanMachineAssignment.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Machine already assigned to this plan")

    # Create assignment
    assignment = PlanMachineAssignment(
        plan_id=plan_id,
        machine_id=data.machine_id,
        assigned_qty=data.assigned_qty,
        is_primary=data.is_primary,
        assigned_by=assigner.id if hasattr(assigner, 'id') else None,
    )
    db.add(assignment)

    # Update machine state
    machine.state = MachineState.RUNNING

    # If this is the first assignment, start the plan
    if plan.state == PlanState.PLANNED:
        plan.state = PlanState.IN_PROGRESS
        plan.start_date = datetime.utcnow()

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def get_plan_assignments(
    db: AsyncSession,
    plan_id: int,
) -> Sequence[PlanMachineAssignment]:
    """Get all machine assignments for a plan."""
    result = await db.execute(
        select(PlanMachineAssignment)
        .options(selectinload(PlanMachineAssignment.machine))
        .where(
            PlanMachineAssignment.plan_id == plan_id,
            PlanMachineAssignment.is_deleted == False,
        )
    )
    return result.scalars().all()


async def cancel_plan(
    db: AsyncSession,
    plan: ProductionPlan,
    reason: str,
) -> ProductionPlan:
    """Cancel a production plan."""
    if plan.state == PlanState.COMPLETED:
        raise ValueError("Cannot cancel a completed plan")

    # Release assigned machines
    assignments = await get_plan_assignments(db, plan.id)
    for assignment in assignments:
        result = await db.execute(
            select(Machine).where(Machine.id == assignment.machine_id)
        )
        machine = result.scalar_one_or_none()
        if machine:
            machine.state = MachineState.IDLE
        assignment.is_deleted = True

    plan.state = PlanState.CANCELLED
    plan.notes = f"{plan.notes or ''}\nCancelled: {reason}".strip()

    await db.commit()
    await db.refresh(plan)
    return plan


async def update_plan_progress(
    db: AsyncSession,
    plan_id: int,
    additional_qty: int,
) -> ProductionPlan:
    """Update production plan completed quantity."""
    plan = await get_plan_by_id(db, plan_id)
    if not plan:
        raise ValueError("Production plan not found")

    plan.completed_qty += additional_qty

    # Check if plan is completed
    if plan.completed_qty >= plan.total_qty:
        plan.state = PlanState.COMPLETED
        plan.completed_date = datetime.utcnow()

        # Release assigned machines
        assignments = await get_plan_assignments(db, plan.id)
        for assignment in assignments:
            result = await db.execute(
                select(Machine).where(Machine.id == assignment.machine_id)
            )
            machine = result.scalar_one_or_none()
            if machine:
                machine.state = MachineState.IDLE

    await db.commit()
    await db.refresh(plan)
    return plan
