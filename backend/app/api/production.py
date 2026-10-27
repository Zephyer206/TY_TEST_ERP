"""Production planning and reporting API endpoints."""

from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.machine import Machine, MachineState
from app.models.material_dict import MaterialDict
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.part_display_group import PartDisplayGroupDef, PartDisplayGroupMember
from app.models.part_tooling_spec import PartToolingSpec
from app.models.production import ProductionPlan, PlanMachineAssignment, PlanStatus, ProcessFlowStatus
from app.models.tooling import Tooling, ToolingPart
from app.schemas.production import (
    MachineAssignmentResponse,
    MaterialMatchResult,
    PlanStatus,
    ProcessFlowCardResponse,
    ProductionPlanCreate,
    ProductionPlanBatchCreate,
    ProductionPlanBatchLine,
    ProductionPlanCancelRequest,
    ProductionPlanDetailResponse,
    ProductionPlanPartOption,
    ProductionPlanPairedPartOption,
    ProductionPlanResponse,
    ProductionPlanTWPOption,
    ProductionPlanUpdate,
    ProductionPlanWorkbenchItem,
    ProductionPlanWorkbenchPage,
    ProductionSchedulingMachine,
    ProductionSchedulingPlan,
    ProductionSchedulingWorkbench,
    ProductionScheduleAssignment,
    ProductionScheduleReorder,
    ProductionReportCreate,
    ProductionReportResponse,
    ProductionSessionDetailResponse,
    ProductionSessionResponse,
    SessionStartWithMaterialRequest,
    SessionStatus,
    MaterialConfirmationBatch,
)
from app.services import production_service, process_flow_service, session_service
from app.services.press_type_service import classify_press, group_press_types

router = APIRouter(prefix="/production", tags=["Production"])


def _format_twp(thickness: Optional[float], width: Optional[float], pitch: Optional[float]) -> Optional[str]:
    if thickness is None or width is None or pitch is None:
        return None
    return f"{float(thickness):g} × {float(width):g} × {float(pitch):g}"


def _estimated_material_weight(plan: ProductionPlan) -> Optional[float]:
    """Return the theoretical strip requirement in kg when source data is complete."""
    values = (
        plan.twp_thickness,
        plan.twp_width,
        plan.twp_pitch,
        plan.material_density_snapshot,
    )
    if any(value is None for value in values):
        return None
    cavity_count = plan.twp_cavity_count or 0
    if cavity_count <= 0 or not plan.total_qty:
        return None
    # One left/right pair yields one left and one right per stroke. The target
    # quantity is per side, so the shared strip requirement is not halved.
    total_qty = plan.total_qty or 0
    strokes = total_qty if plan.is_left_right_pair else ceil(total_qty / cavity_count)
    return round(
        float(plan.twp_thickness)
        * float(plan.twp_width)
        * float(plan.twp_pitch)
        * float(plan.material_density_snapshot)
        * strokes
        / 1_000_000,
        3,
    )


async def _load_plan_display_context(db: DbSession, plans: list[ProductionPlan]) -> dict[int, dict[str, Optional[str]]]:
    part_ids = {plan.part_id for plan in plans if plan.part_id is not None}
    if not part_ids:
        return {}

    parts = (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars().all()
    result = {
        part.id: {"part_name": part.internal_name, "customer_part_no": None}
        for part in parts
    }
    aliases = (await db.execute(
        select(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no)
        .where(
            PartCustomerAlias.part_id.in_(part_ids),
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.customer_part_no.is_not(None),
            PartCustomerAlias.customer_part_no != "",
        )
        .order_by(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no)
    )).all()
    alias_map: dict[int, list[str]] = {}
    for part_id, customer_part_no in aliases:
        alias_map.setdefault(part_id, []).append(customer_part_no)
    for part_id, values in alias_map.items():
        if part_id in result:
            result[part_id]["customer_part_no"] = " / ".join(dict.fromkeys(values))
    return result


def _to_workbench_item(plan: ProductionPlan, context: dict[str, Optional[str]]) -> ProductionPlanWorkbenchItem:
    completed_qty = plan.progress_qty or 0
    confirmed_qty = plan.material_confirmed_qty or 0
    total_qty = plan.total_qty or 0
    return ProductionPlanWorkbenchItem(
        id=plan.id,
        part_id=plan.part_id,
        customer_part_no=context.get("customer_part_no"),
        part_name=context.get("part_name"),
        paired_part_id=plan.paired_part_id,
        paired_customer_part_no=plan.paired_customer_part_no_snapshot,
        paired_part_name=plan.paired_part_name_snapshot,
        is_left_right_pair=bool(plan.is_left_right_pair),
        material_name=plan.material_name_snapshot,
        total_qty=total_qty,
        completed_qty=completed_qty,
        remaining_qty=max(total_qty - completed_qty, 0),
        is_urgent=bool(plan.is_urgent),
        status=plan.status or PlanStatus.PLANNED.value,
        material_status="ready" if plan.material_status == "ready" else "pending",
        material_confirmed_qty=plan.material_confirmed_qty,
        material_confirmed_by=plan.material_confirmed_by,
        material_confirmed_at=plan.material_confirmed_at,
        material_confirmation_note=plan.material_confirmation_note,
        material_calculation_mode="auto" if plan.material_calculation_mode == "auto" else "manual",
        twp_value=plan.twp_value,
        twp_manual_override=bool(plan.twp_manual_override),
        material_density=float(plan.material_density_snapshot) if plan.material_density_snapshot is not None else None,
        estimated_material_weight_kg=_estimated_material_weight(plan),
        confirmation_increment=max(total_qty - confirmed_qty, 0) if plan.material_status != "ready" else 0,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


async def _material_density_by_name(db: DbSession, material_names: set[str]) -> dict[str, float]:
    normalized_names = {value.strip().lower() for value in material_names if value and value.strip()}
    if not normalized_names:
        return {}
    materials = (await db.execute(select(MaterialDict).where(MaterialDict.is_active == True))).scalars().all()
    density_by_name: dict[str, float] = {}
    for material in materials:
        if material.density is None:
            continue
        for candidate in (material.code, material.name, material.name_cn):
            if candidate and candidate.strip().lower() in normalized_names:
                density_by_name[candidate.strip().lower()] = float(material.density)
    return density_by_name


async def _load_left_right_partner_ids(db: DbSession, part_ids: set[int]) -> dict[int, int]:
    """Return counterparts from explicit groups or verified one-output-pair tooling."""
    if not part_ids:
        return {}
    rows = (await db.execute(
        select(PartDisplayGroupMember.group_id, PartDisplayGroupMember.part_id)
        .join(PartDisplayGroupDef, PartDisplayGroupDef.id == PartDisplayGroupMember.group_id)
        .where(
            PartDisplayGroupDef.group_type == "left_right",
            PartDisplayGroupDef.is_active == True,
        )
    )).all()
    members_by_group: dict[int, list[int]] = {}
    for group_id, part_id in rows:
        members_by_group.setdefault(group_id, []).append(part_id)
    partner_by_part: dict[int, int] = {}
    for members in members_by_group.values():
        unique_members = list(dict.fromkeys(members))
        if len(unique_members) != 2:
            continue
        first, second = unique_members
        if first in part_ids:
            partner_by_part[first] = second
        if second in part_ids:
            partner_by_part[second] = first

    unresolved_ids = part_ids - set(partner_by_part)
    if not unresolved_ids:
        return partner_by_part
    rows = (await db.execute(
        select(
            ToolingPart.part_id,
            Part.part_position,
            Tooling.tooling_number,
            Tooling.cavity_count,
        )
        .join(Tooling, Tooling.id == ToolingPart.tooling_id)
        .join(Part, Part.id == ToolingPart.part_id)
        .where(
            Part.part_position.in_(["left", "right"]),
            Tooling.is_deleted == False,
            Tooling.cavity_count > 1,
        )
    )).all()
    candidates: dict[str, dict[str, set[int]]] = {}
    for part_id, position, tooling_number, cavity_count in rows:
        if not tooling_number or not tooling_number.endswith(("-1", "-2")) or cavity_count < 2:
            continue
        candidates.setdefault(tooling_number[:-2], {}).setdefault(position, set()).add(part_id)
    for positions in candidates.values():
        left_ids = positions.get("left", set())
        right_ids = positions.get("right", set())
        if len(left_ids) != 1 or len(right_ids) != 1:
            continue
        left_id, right_id = next(iter(left_ids)), next(iter(right_ids))
        if left_id in unresolved_ids:
            partner_by_part[left_id] = right_id
        if right_id in unresolved_ids:
            partner_by_part[right_id] = left_id
    return partner_by_part


async def _load_primary_tooling_numbers(db: DbSession, part_ids: set[int]) -> dict[int, str]:
    if not part_ids:
        return {}
    rows = (await db.execute(
        select(ToolingPart.part_id, Tooling.tooling_number)
        .join(Tooling, Tooling.id == ToolingPart.tooling_id)
        .where(ToolingPart.part_id.in_(part_ids), Tooling.is_deleted == False)
        .order_by(ToolingPart.part_id, ToolingPart.is_primary.desc(), ToolingPart.sequence, Tooling.id)
    )).all()
    result: dict[int, str] = {}
    for part_id, tooling_number in rows:
        if tooling_number and part_id not in result:
            result[part_id] = tooling_number
    return result


def _plan_to_response(plan: ProductionPlan) -> ProductionPlanResponse:
    """Convert ProductionPlan to response."""
    return ProductionPlanResponse(
        id=plan.id,
        plan_no=f"PP-{plan.id:06d}",
        part_id=plan.part_id,
        total_qty=plan.total_qty or 0,
        planned_start_date=None,
        planned_end_date=plan.due_date,
        priority=0,
        notes=plan.remark,
        completed_qty=plan.progress_qty or 0,
        status=plan.status or PlanStatus.PLANNED.value,
        created_by=plan.created_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _assignment_to_response(assignment: PlanMachineAssignment) -> MachineAssignmentResponse:
    """Convert PlanMachineAssignment to response."""
    return MachineAssignmentResponse(
        id=assignment.id,
        plan_id=assignment.plan_id,
        machine_id=assignment.machine_id,
        machine_no=assignment.machine.machine_no if assignment.machine else None,
        machine_name=assignment.machine.name if assignment.machine else None,
        assigned_qty=assignment.assigned_qty,
        completed_qty=assignment.completed_qty,
        is_active=assignment.is_active,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
    )


async def _load_scheduling_context(db: DbSession, plans: list[ProductionPlan]) -> dict[int, dict[str, Optional[str]]]:
    """Load only operator-facing identifiers for scheduling cards."""
    part_ids = {part_id for plan in plans for part_id in (plan.part_id, plan.paired_part_id) if part_id is not None}
    if not part_ids:
        return {}
    context: dict[int, dict[str, Optional[str]]] = {
        part_id: {"customer_part_no": None, "tooling_number": None, "minimum_tonnage": None}
        for part_id in part_ids
    }
    aliases = (await db.execute(
        select(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no)
        .where(
            PartCustomerAlias.part_id.in_(part_ids),
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.customer_part_no.is_not(None),
            PartCustomerAlias.customer_part_no != "",
        )
        .order_by(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no)
    )).all()
    aliases_by_part: dict[int, list[str]] = {}
    for part_id, value in aliases:
        aliases_by_part.setdefault(part_id, []).append(value)
    part_rows = (await db.execute(select(Part.id, Part.press_tonnage).where(Part.id.in_(part_ids)))).all()
    for part_id, press_tonnage in part_rows:
        context[part_id]["customer_part_no"] = " / ".join(dict.fromkeys(aliases_by_part.get(part_id, []))) or None
        context[part_id]["minimum_tonnage"] = press_tonnage
    tooling_rows = (await db.execute(
        select(ToolingPart.part_id, Tooling.tooling_number, Tooling.press_tonnage)
        .join(Tooling, Tooling.id == ToolingPart.tooling_id)
        .where(ToolingPart.part_id.in_(part_ids), Tooling.is_deleted == False)
        .order_by(ToolingPart.part_id, ToolingPart.is_primary.desc(), ToolingPart.sequence, Tooling.id)
    )).all()
    for part_id, tooling_number, tooling_tonnage in tooling_rows:
        if context[part_id]["tooling_number"] is None:
            context[part_id]["tooling_number"] = tooling_number
        if context[part_id]["minimum_tonnage"] is None and tooling_tonnage:
            context[part_id]["minimum_tonnage"] = tooling_tonnage
    return context


def _tonnage_value(value: Optional[object]) -> Optional[float]:
    if value is None:
        return None
    try:
        text = str(value).upper().replace("吨", "").replace("T", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return None


def _scheduling_plan(plan: ProductionPlan, context: dict[int, dict[str, Optional[str]]]) -> ProductionSchedulingPlan:
    primary = context.get(plan.part_id or -1, {})
    paired = context.get(plan.paired_part_id or -1, {})
    return ProductionSchedulingPlan(
        id=plan.id,
        customer_part_no=primary.get("customer_part_no"),
        paired_customer_part_no=paired.get("customer_part_no") or plan.paired_customer_part_no_snapshot,
        tooling_number=primary.get("tooling_number"),
        minimum_tonnage=_tonnage_value(primary.get("minimum_tonnage")),
        total_qty=plan.total_qty or 0,
        is_urgent=bool(plan.is_urgent),
        material_status="ready" if plan.material_status == "ready" else "pending",
        status=plan.status or PlanStatus.PLANNED.value,
        machine_id=plan.machine_id,
        plan_order=plan.plan_order,
    )


@router.get("/planning-part-options", response_model=list[ProductionPlanPartOption])
async def list_planning_part_options(
    db: DbSession,
    current_user: CurrentUser,
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
) -> list[ProductionPlanPartOption]:
    """Search production-plan parts by customer part number or part name."""
    search_term = query.strip()
    base_query = select(Part.id).where(Part.is_deleted == False)
    if search_term:
        pattern = f"%{search_term}%"
        base_query = (
            base_query.outerjoin(PartCustomerAlias, PartCustomerAlias.part_id == Part.id)
            .where(
                or_(
                    Part.internal_name.ilike(pattern),
                    PartCustomerAlias.customer_part_no.ilike(pattern),
                )
            )
        )
    part_ids = list((await db.execute(
        base_query.distinct().order_by(Part.id.desc()).limit(limit)
    )).scalars().all())
    if not part_ids:
        return []

    # The search result must carry its counterpart even when that part does not
    # independently match the entered customer number or name.
    searched_part_ids = list(part_ids)
    partner_by_part = await _load_left_right_partner_ids(db, set(part_ids))
    part_ids = list(dict.fromkeys([*part_ids, *partner_by_part.values()]))

    parts = (await db.execute(select(Part).where(Part.id.in_(part_ids)))).scalars().all()
    part_by_id = {part.id: part for part in parts}
    aliases = (await db.execute(
        select(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no)
        .where(
            PartCustomerAlias.part_id.in_(part_ids),
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.customer_part_no.is_not(None),
            PartCustomerAlias.customer_part_no != "",
        )
        .order_by(PartCustomerAlias.customer_part_no)
    )).all()
    aliases_by_part: dict[int, list[str]] = {}
    for part_id, customer_part_no in aliases:
        aliases_by_part.setdefault(part_id, []).append(customer_part_no)

    spec_rows = (await db.execute(
        select(PartToolingSpec, Tooling.tooling_number, Tooling.cavity_count)
        .join(Tooling, Tooling.id == PartToolingSpec.tooling_id)
        .where(PartToolingSpec.part_id.in_(part_ids), Tooling.is_deleted == False)
        .order_by(PartToolingSpec.is_primary.desc(), Tooling.tooling_number, PartToolingSpec.id)
    )).all()
    specs_by_part: dict[int, list[ProductionPlanTWPOption]] = {}
    for spec, tooling_number, cavity_count in spec_rows:
        specs_by_part.setdefault(spec.part_id, []).append(ProductionPlanTWPOption(
            id=spec.id,
            tooling_number=tooling_number,
            value=_format_twp(spec.thickness, spec.width, spec.pitch) or spec.spec_twph,
            thickness=float(spec.thickness) if spec.thickness is not None else None,
            width=float(spec.width) if spec.width is not None else None,
            pitch=float(spec.pitch) if spec.pitch is not None else None,
            cavity_count=cavity_count,
            is_primary=spec.is_primary,
        ))

    density_by_name = await _material_density_by_name(
        db, {part.material_name for part in parts if part.material_name}
    )
    tooling_numbers = await _load_primary_tooling_numbers(db, set(part_ids))

    def to_part_option(part_id: int, *, partner: Optional[ProductionPlanPairedPartOption] = None) -> ProductionPlanPartOption:
        part = part_by_id[part_id]
        return ProductionPlanPartOption(
            id=part_id,
            customer_part_no=" / ".join(dict.fromkeys(aliases_by_part.get(part_id, []))) or None,
            part_name=part.internal_name,
            material_name=part.material_name,
            material_density=density_by_name.get((part.material_name or "").strip().lower()),
            twp_options=specs_by_part.get(part_id, []),
            left_right_partner=partner,
            left_right_tooling_number=tooling_numbers.get(part_id),
        )

    return [
        to_part_option(
            part_id,
            partner=(
                ProductionPlanPairedPartOption(
                    id=partner_id,
                    customer_part_no=" / ".join(dict.fromkeys(aliases_by_part.get(partner_id, []))) or None,
                    part_name=part_by_id[partner_id].internal_name,
                    material_name=part_by_id[partner_id].material_name,
                    material_density=density_by_name.get((part_by_id[partner_id].material_name or "").strip().lower()),
                    twp_options=specs_by_part.get(partner_id, []),
                    tooling_number=tooling_numbers.get(partner_id),
                )
                if (partner_id := partner_by_part.get(part_id)) in part_by_id
                else None
            ),
        )
        for part_id in searched_part_ids
        if part_id in part_by_id
    ]


@router.get("/plans/workbench", response_model=ProductionPlanWorkbenchPage)
async def list_plan_workbench(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    material_status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=120),
    plan_id: Optional[int] = Query(default=None, ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ProductionPlanWorkbenchPage:
    """List plans that still require material handling before scheduling.

    Scheduled plans belong to the scheduling workbench. They remain in
    ``active_items`` only so a later order can still warn the business user
    that the same part already has unfinished demand.
    """
    query = select(ProductionPlan).where(ProductionPlan.machine_id.is_(None)).order_by(
        ProductionPlan.is_urgent.desc(),
        ProductionPlan.created_at.desc().nulls_last(),
        ProductionPlan.id.desc(),
    )
    if status_filter:
        query = query.where(ProductionPlan.status == status_filter)
    if plan_id is not None:
        query = query.where(ProductionPlan.id == plan_id)
    if material_status in {"pending", "ready"}:
        query = query.where(ProductionPlan.material_status == material_status)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        matching_part_ids = select(PartCustomerAlias.part_id).where(
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.customer_part_no.ilike(pattern),
        )
        query = query.where(or_(
            ProductionPlan.part_id.in_(matching_part_ids),
            ProductionPlan.part_id.in_(select(Part.id).where(Part.internal_name.ilike(pattern))),
        ))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    plans = list((await db.execute(query.offset(skip).limit(limit))).scalars().all())
    active_plans = list((await db.execute(
        select(ProductionPlan)
        .where(or_(
            ProductionPlan.status.is_(None),
            ProductionPlan.status.notin_([
                PlanStatus.CANCELLED.value,
                PlanStatus.COMPLETED.value,
                PlanStatus.CLOSED.value,
            ]),
        ))
        .order_by(ProductionPlan.created_at.desc().nulls_last(), ProductionPlan.id.desc())
    )).scalars().all())
    context_by_part = await _load_plan_display_context(db, list({plan.id: plan for plan in [*plans, *active_plans]}.values()))
    return ProductionPlanWorkbenchPage(
        total=int(total or 0),
        items=[_to_workbench_item(plan, context_by_part.get(plan.part_id, {})) for plan in plans],
        active_items=[_to_workbench_item(plan, context_by_part.get(plan.part_id, {})) for plan in active_plans],
    )


@router.post("/plans/batch", response_model=list[ProductionPlanWorkbenchItem], status_code=status.HTTP_201_CREATED)
async def create_production_plan_batch(
    data: ProductionPlanBatchCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProductionPlanWorkbenchItem]:
    """Submit one or more business plans to the material-readiness queue."""
    require_role(current_user, min_level=2)
    from app.services.production_service import create_material_ready_plan

    # A left/right pair is one manufacturing demand: one plan, one shared TWP,
    # and one strip requirement for each matching left/right output quantity.
    requested_lines = list(data.lines)
    requested_part_ids = {line.part_id for line in requested_lines}
    partner_by_part = await _load_left_right_partner_ids(db, requested_part_ids)
    part_ids = set(requested_part_ids) | set(partner_by_part.values())
    parts = (await db.execute(
        select(Part).where(Part.id.in_(part_ids), Part.is_deleted == False)
    )).scalars().all()
    parts_by_id = {part.id: part for part in parts}
    missing_part_ids = sorted(part_ids - set(parts_by_id))
    if missing_part_ids:
        raise HTTPException(status_code=404, detail={"message": "零件不存在或已删除", "part_ids": missing_part_ids})

    spec_ids = {line.twp_source_spec_id for line in requested_lines}
    specs = (await db.execute(
        select(PartToolingSpec, Tooling.cavity_count)
        .join(Tooling, Tooling.id == PartToolingSpec.tooling_id)
        .where(PartToolingSpec.id.in_(spec_ids), Tooling.is_deleted == False)
    )).all()
    specs_by_id = {spec.id: (spec, cavity_count) for spec, cavity_count in specs}
    if spec_ids - set(specs_by_id):
        raise HTTPException(status_code=400, detail="所选 TWP 来源已失效，请重新选择零件")

    density_by_name = await _material_density_by_name(
        db, {part.material_name for part in parts if part.material_name}
    )
    aliases = (await db.execute(
        select(PartCustomerAlias.part_id, PartCustomerAlias.customer_part_no)
        .where(
            PartCustomerAlias.part_id.in_(part_ids),
            PartCustomerAlias.is_active == True,
            PartCustomerAlias.customer_part_no.is_not(None),
            PartCustomerAlias.customer_part_no != "",
        )
        .order_by(PartCustomerAlias.customer_part_no)
    )).all()
    aliases_by_part: dict[int, list[str]] = {}
    for part_id, customer_part_no in aliases:
        aliases_by_part.setdefault(part_id, []).append(customer_part_no)
    prepared_lines = []
    change_warnings = []
    for line in requested_lines:
        spec, cavity_count = specs_by_id[line.twp_source_spec_id]
        if spec.part_id != line.part_id:
            raise HTTPException(status_code=400, detail="TWP 来源不属于所选零件")
        if line.manual_twp:
            thickness = line.manual_twp.thickness
            width = line.manual_twp.width
            pitch = line.manual_twp.pitch
            manual_override = True
        else:
            thickness = float(spec.thickness) if spec.thickness is not None else None
            width = float(spec.width) if spec.width is not None else None
            pitch = float(spec.pitch) if spec.pitch is not None else None
            manual_override = False
        twp_value = _format_twp(thickness, width, pitch)
        if twp_value is None:
            raise HTTPException(status_code=400, detail="TWP 不完整，不能提交给资材确认")

        previous = (await db.execute(
            select(ProductionPlan)
            .where(
                ProductionPlan.part_id == line.part_id,
                ProductionPlan.twp_source_spec_id == spec.id,
                ProductionPlan.twp_manual_override == False,
            )
            .order_by(ProductionPlan.created_at.desc().nulls_last(), ProductionPlan.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        if previous and previous.twp_value and previous.twp_value != twp_value and not line.acknowledge_twp_change:
            change_warnings.append({
                "part_id": line.part_id,
                "previous_twp": previous.twp_value,
                "current_twp": twp_value,
            })
        partner_id = partner_by_part.get(line.part_id)
        partner = parts_by_id.get(partner_id) if partner_id else None
        if partner and partner.material_name and partner.material_name != parts_by_id[line.part_id].material_name:
            raise HTTPException(status_code=400, detail="左右件材料不一致，需先在零件档案核实后再提交")
        if partner:
            partner_spec = (await db.execute(
                select(PartToolingSpec)
                .join(Tooling, Tooling.id == PartToolingSpec.tooling_id)
                .where(
                    PartToolingSpec.part_id == partner.id,
                    Tooling.is_deleted == False,
                    PartToolingSpec.thickness.is_not(None),
                    PartToolingSpec.width.is_not(None),
                    PartToolingSpec.pitch.is_not(None),
                )
                .order_by(PartToolingSpec.is_primary.desc(), PartToolingSpec.id)
                .limit(1)
            )).scalar_one_or_none()
            partner_twp_value = _format_twp(
                float(partner_spec.thickness) if partner_spec and partner_spec.thickness is not None else None,
                float(partner_spec.width) if partner_spec and partner_spec.width is not None else None,
                float(partner_spec.pitch) if partner_spec and partner_spec.pitch is not None else None,
            )
            if partner_twp_value is None or partner_twp_value != twp_value:
                raise HTTPException(status_code=400, detail="Left/right pair TWP does not match; verify the tooling association before submitting.")
        prepared_lines.append((
            line, parts_by_id[line.part_id], spec, cavity_count, thickness, width, pitch, twp_value, manual_override,
            partner,
            " / ".join(dict.fromkeys(aliases_by_part.get(partner.id, []))) or None if partner else None,
        ))

    if change_warnings:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "零件 TWP 已变化，请确认后再提交", "twp_changes": change_warnings},
        )

    created_plans = []
    for line, part, spec, cavity_count, thickness, width, pitch, twp_value, manual_override, partner, partner_customer_part_no in prepared_lines:
        density = density_by_name.get((part.material_name or "").strip().lower())
        created_plans.append(await create_material_ready_plan(
            db,
            part_id=part.id,
            paired_part_id=partner.id if partner else None,
            is_left_right_pair=partner is not None,
            paired_customer_part_no_snapshot=partner_customer_part_no,
            paired_part_name_snapshot=partner.internal_name if partner else None,
            total_qty=line.total_qty,
            twp_source_spec_id=spec.id,
            twp_value=twp_value,
            twp_thickness=thickness,
            twp_width=width,
            twp_pitch=pitch,
            twp_cavity_count=cavity_count,
            twp_manual_override=manual_override,
            material_name_snapshot=part.material_name,
            material_density_snapshot=density,
            is_urgent=line.is_urgent,
            notes=line.notes,
            created_by=current_user.id,
        ))
    await db.commit()
    for plan in created_plans:
        await db.refresh(plan)
    context_by_part = await _load_plan_display_context(db, created_plans)
    return [_to_workbench_item(plan, context_by_part.get(plan.part_id, {})) for plan in created_plans]


@router.post("/plans/material-confirmations", response_model=list[ProductionPlanWorkbenchItem])
async def confirm_plan_materials(
    data: MaterialConfirmationBatch,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProductionPlanWorkbenchItem]:
    """Confirm that material has been prepared for selected plans."""
    require_role(current_user, min_level=2)
    from app.services.production_service import confirm_material_ready

    plan_ids = set(data.plan_ids)
    plans = list((await db.execute(
        select(ProductionPlan).where(ProductionPlan.id.in_(plan_ids))
    )).scalars().all())
    if len(plans) != len(plan_ids):
        raise HTTPException(status_code=404, detail="存在未找到的生产计划")
    if any(plan.status in {PlanStatus.CANCELLED.value, PlanStatus.COMPLETED.value, PlanStatus.CLOSED.value} for plan in plans):
        raise HTTPException(status_code=400, detail="已取消或已完成的计划不能确认备料")
    await confirm_material_ready(db, plans, confirmed_by=current_user.id, note=data.note)
    await db.commit()
    for plan in plans:
        await db.refresh(plan)
    context_by_part = await _load_plan_display_context(db, plans)
    return [_to_workbench_item(plan, context_by_part.get(plan.part_id, {})) for plan in plans]


@router.post("/plans", response_model=ProductionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_production_plan(
    data: ProductionPlanCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Create a new production plan. Requires LV2 (manager/supervisor)."""
    require_role(current_user, min_level=2)

    # Verify part exists
    from app.models.part import Part

    result = await db.execute(select(Part).where(Part.id == data.part_id))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    plan = await production_service.create_plan(
        db,
        part_id=data.part_id,
        total_qty=data.total_qty,
        planned_start_date=data.planned_start_date,
        planned_end_date=data.planned_end_date,
        priority=data.priority,
        notes=data.notes,
        created_by=current_user.id,
    )
    return _plan_to_response(plan)


@router.get("/plans", response_model=list[ProductionPlanResponse])
async def list_production_plans(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[PlanStatus] = Query(default=None, alias="status"),
    part_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProductionPlanResponse]:
    """List production plans with optional filters."""
    plans = await production_service.get_plans(
        db,
        status=status_filter,
        part_id=part_id,
        skip=skip,
        limit=limit,
    )
    return [_plan_to_response(p) for p in plans]


@router.get("/plans-count")
async def count_production_plans(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(default=None, alias="status"),
) -> dict[str, int]:
    """Return a lightweight plan count using the canonical production schema."""
    query = select(func.count()).select_from(ProductionPlan)
    if status_filter:
        query = query.where(ProductionPlan.status == status_filter)
    total = await db.scalar(query)
    return {"total": int(total or 0)}


@router.get("/plans/{plan_id}", response_model=ProductionPlanDetailResponse)
async def get_production_plan(
    plan_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanDetailResponse:
    """Get production plan details with assignments."""
    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    response = _plan_to_response(plan)
    assignments = [_assignment_to_response(a) for a in plan.assignments]

    return ProductionPlanDetailResponse(
        id=response.id,
        plan_no=response.plan_no,
        part_id=response.part_id,
        total_qty=response.total_qty,
        planned_start_date=response.planned_start_date,
        planned_end_date=response.planned_end_date,
        priority=response.priority,
        notes=response.notes,
        completed_qty=response.completed_qty,
        status=response.status,
        created_by=response.created_by,
        created_at=response.created_at,
        updated_at=response.updated_at,
        assignments=assignments,
    )


@router.patch("/plans/{plan_id}", response_model=ProductionPlanResponse)
async def update_production_plan(
    plan_id: int,
    data: ProductionPlanUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanResponse:
    """Update a production plan. Requires LV2 (manager/supervisor)."""
    require_role(current_user, min_level=2)

    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    if data.material_calculation_mode == "auto" and _estimated_material_weight(plan) is None:
        raise HTTPException(status_code=400, detail="TWP、材料密度或穴数不完整，只能由资材手动确认")
    plan = await production_service.update_material_ready_plan(
        db,
        plan,
        total_qty=data.total_qty,
        is_urgent=data.is_urgent,
        notes=data.notes,
        material_calculation_mode=data.material_calculation_mode,
    )
    # Legacy execution fields are still accepted for the separate shop-floor API.
    if data.planned_start_date is not None or data.planned_end_date is not None or data.priority is not None or data.status is not None:
        plan = await production_service.update_plan(
            db,
            plan,
            planned_start_date=data.planned_start_date,
            planned_end_date=data.planned_end_date,
            priority=data.priority,
            status=data.status,
        )
    else:
        await db.commit()
        await db.refresh(plan)
    return _plan_to_response(plan)


@router.post("/plans/{plan_id}/cancel", response_model=ProductionPlanWorkbenchItem)
async def cancel_production_plan(
    plan_id: int,
    data: ProductionPlanCancelRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionPlanWorkbenchItem:
    """Cancel a plan with an auditable reason before it enters scheduling."""
    require_role(current_user, min_level=2)
    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")
    if plan.status in {PlanStatus.IN_PROGRESS.value, PlanStatus.COMPLETED.value, PlanStatus.CLOSED.value}:
        raise HTTPException(status_code=400, detail="生产已开始或已完成的计划不能在此取消")
    plan.status = PlanStatus.CANCELLED.value
    plan.cancellation_reason = data.reason
    await db.commit()
    await db.refresh(plan)
    context_by_part = await _load_plan_display_context(db, [plan])
    return _to_workbench_item(plan, context_by_part.get(plan.part_id, {}))


@router.post("/plans/{plan_id}/assign-machine", response_model=MachineAssignmentResponse)
async def assign_machine_to_plan(
    plan_id: int,
    machine_id: int,
    db: DbSession,
    current_user: CurrentUser,
    assigned_qty: int = Query(..., ge=1),
) -> MachineAssignmentResponse:
    """Assign a machine to a production plan. Requires LV2 (manager/supervisor)."""
    require_role(current_user, min_level=2)

    plan = await production_service.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")

    # Verify machine exists
    result = await db.execute(
        select(Machine).where(Machine.id == machine_id, Machine.is_deleted == False)
    )
    machine = result.scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    assignment = await production_service.assign_machine(
        db, plan, machine_id, assigned_qty, current_user
    )
    return _assignment_to_response(assignment)


@router.get("/scheduling-workbench", response_model=ProductionSchedulingWorkbench)
async def get_scheduling_workbench(
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSchedulingWorkbench:
    """Return material-ready plans and the fixed machine queue board."""
    require_role(current_user, min_level=2)
    plans = list((await db.execute(
        select(ProductionPlan)
        .where(
            ProductionPlan.material_status == "ready",
            ProductionPlan.status.in_([
                PlanStatus.PLANNED.value,
                PlanStatus.QUEUED.value,
                PlanStatus.IN_PROGRESS.value,
            ]),
        )
        .order_by(
            ProductionPlan.is_urgent.desc(),
            ProductionPlan.plan_order.asc().nullslast(),
            ProductionPlan.created_at.asc().nullslast(),
            ProductionPlan.id.asc(),
        )
    )).scalars().all())
    machines = list((await db.execute(
        select(Machine)
        .where(Machine.is_deleted == False)
        .order_by(Machine.tonnage.asc().nullslast(), Machine.machine_no.asc())
    )).scalars().all())
    context = await _load_scheduling_context(db, plans)
    cards = {plan.id: _scheduling_plan(plan, context) for plan in plans}
    machine_payload: list[ProductionSchedulingMachine] = []
    assigned_ids: set[int] = set()
    press_types = {option.key: option for option in group_press_types(machines)}
    for machine in machines:
        press_type = classify_press(machine)
        press_type = press_types.get(press_type.key, press_type)
        queue = [
            cards[plan.id]
            for plan in plans
            if plan.machine_id == machine.id and plan.id in cards
        ]
        queue.sort(key=lambda item: (item.plan_order is None, item.plan_order or 0, item.id))
        assigned_ids.update(item.id for item in queue)
        machine_payload.append(ProductionSchedulingMachine(
            id=machine.id,
            machine_no=machine.machine_no,
            name=machine.name,
            machine_type=machine.machine_type,
            tonnage=machine.tonnage,
            press_type_key=press_type.key,
            press_type_label=press_type.label,
            is_dual_axis=press_type.is_dual_axis,
            max_stroke=machine.max_stroke,
            bed_size=machine.bed_size,
            state=machine.state.value if hasattr(machine.state, "value") else str(machine.state),
            location=machine.location,
            queue=queue,
        ))
    return ProductionSchedulingWorkbench(
        pending=[card for plan_id, card in cards.items() if plan_id not in assigned_ids],
        machines=machine_payload,
    )


@router.post("/plans/{plan_id}/schedule", response_model=ProductionSchedulingPlan)
async def schedule_production_plan(
    plan_id: int,
    data: ProductionScheduleAssignment,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSchedulingPlan:
    """Put one material-ready plan into one fixed machine queue."""
    require_role(current_user, min_level=2)
    plan = (await db.execute(select(ProductionPlan).where(ProductionPlan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")
    if plan.material_status != "ready":
        raise HTTPException(status_code=400, detail="只有资材确认后的计划才能排产")
    if plan.status in {PlanStatus.COMPLETED.value, PlanStatus.CANCELLED.value, PlanStatus.CLOSED.value}:
        raise HTTPException(status_code=400, detail="已完成或已取消的计划不能排产")
    machine = (await db.execute(
        select(Machine).where(Machine.id == data.machine_id, Machine.is_deleted == False)
    )).scalar_one_or_none()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    context = await _load_scheduling_context(db, [plan])
    card = _scheduling_plan(plan, context)
    unavailable_states = {
        MachineState.FAULT.value,
        MachineState.PENDING_CHECK.value,
        MachineState.REPAIRING.value,
        MachineState.OFFLINE.value,
    }
    machine_state = machine.state.value if hasattr(machine.state, "value") else str(machine.state)
    if machine_state in unavailable_states:
        raise HTTPException(status_code=400, detail="故障、维修或离线机台不能排产")
    if card.minimum_tonnage is not None and (machine.tonnage is None or machine.tonnage < card.minimum_tonnage):
        raise HTTPException(status_code=400, detail="机台吨位低于零件最低吨位，不能排入")
    if card.minimum_tonnage is None and not data.confirm_missing_tonnage:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="零件未维护最低吨位，请特别确认后排入",
        )

    next_order = await db.scalar(
        select(func.max(ProductionPlan.plan_order)).where(
            ProductionPlan.machine_id == machine.id,
            ProductionPlan.status.in_([PlanStatus.QUEUED.value, PlanStatus.IN_PROGRESS.value]),
        )
    )
    if plan.machine_id != machine.id:
        plan.plan_order = int(next_order or 0) + 1
    plan.machine_id = machine.id
    plan.assigned_by = current_user.id
    plan.assigned_at = datetime.utcnow()
    if plan.status == PlanStatus.PLANNED.value:
        plan.status = PlanStatus.QUEUED.value

    active_assignments = list((await db.execute(
        select(PlanMachineAssignment).where(
            PlanMachineAssignment.plan_id == plan.id,
            PlanMachineAssignment.is_active == True,
        )
    )).scalars().all())
    for assignment in active_assignments:
        if assignment.machine_id != machine.id:
            assignment.is_active = False
    current_assignment = next((item for item in active_assignments if item.machine_id == machine.id), None)
    if current_assignment is None:
        db.add(PlanMachineAssignment(
            plan_id=plan.id,
            machine_id=machine.id,
            assigned_qty=plan.total_qty or 0,
            assigned_by=current_user.id,
        ))
    else:
        current_assignment.assigned_qty = plan.total_qty or 0
        current_assignment.assigned_by = current_user.id
    await db.commit()
    await db.refresh(plan)
    context = await _load_scheduling_context(db, [plan])
    return _scheduling_plan(plan, context)


@router.post("/plans/{plan_id}/unschedule", response_model=ProductionSchedulingPlan)
async def unschedule_production_plan(
    plan_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSchedulingPlan:
    """Remove a queued plan from its machine without deleting the plan."""
    require_role(current_user, min_level=2)
    plan = (await db.execute(select(ProductionPlan).where(ProductionPlan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found")
    if plan.status == PlanStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=400, detail="生产中的计划不能移出队列")
    plan.machine_id = None
    plan.plan_order = None
    if plan.status == PlanStatus.QUEUED.value:
        plan.status = PlanStatus.PLANNED.value
    assignments = (await db.execute(
        select(PlanMachineAssignment).where(
            PlanMachineAssignment.plan_id == plan.id,
            PlanMachineAssignment.is_active == True,
        )
    )).scalars().all()
    for assignment in assignments:
        assignment.is_active = False
    await db.commit()
    await db.refresh(plan)
    context = await _load_scheduling_context(db, [plan])
    return _scheduling_plan(plan, context)


@router.post("/scheduling/reorder", response_model=ProductionSchedulingWorkbench)
async def reorder_scheduling_queue(
    data: ProductionScheduleReorder,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSchedulingWorkbench:
    """Persist the visible waiting order for one fixed machine."""
    require_role(current_user, min_level=2)
    plans = list((await db.execute(
        select(ProductionPlan).where(
            ProductionPlan.id.in_(data.plan_ids),
            ProductionPlan.machine_id == data.machine_id,
            ProductionPlan.status == PlanStatus.QUEUED.value,
        )
    )).scalars().all())
    found = {plan.id for plan in plans}
    if found != set(data.plan_ids):
        raise HTTPException(status_code=400, detail="排序项必须是该机台队列中的待生产计划")
    for order, plan_id in enumerate(data.plan_ids, start=1):
        next(plan for plan in plans if plan.id == plan_id).plan_order = order
    await db.commit()
    # Reuse the single workbench builder so the UI immediately receives a fresh board.
    return await get_scheduling_workbench(db, current_user)


@router.post("/sessions/verify-material", response_model=MaterialMatchResult)
async def verify_material_match(
    machine_id: int,
    part_id: int,
    material_batch_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> MaterialMatchResult:
    """Verify if material matches the tooling on the machine for the part."""
    result = await session_service.verify_material_tooling_match(
        db, machine_id, part_id, material_batch_id
    )
    return MaterialMatchResult(**result)


@router.post("/sessions/start", response_model=ProductionSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_production_session(
    data: SessionStartWithMaterialRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSessionResponse:
    """Start a new production session with material verification."""
    require_role(current_user, min_level=1)

    try:
        session = await session_service.start_session(
            db,
            machine_id=data.machine_id,
            part_id=data.part_id,
            material_batch_id=data.material_batch_id,
            plan_id=data.plan_id,
            operator_id=current_user.id,
            force_start=data.force_start,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionSessionResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        part_id=session.part_id,
        material_batch_id=session.material_batch_id,
        status=session.status,
        started_at=session.started_at,
        closed_at=session.closed_at,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        process_flow_id=session.process_flow_id,
        operator_id=session.operator_id,
        created_at=session.created_at,
    )


@router.get("/sessions/active", response_model=list[ProductionSessionResponse])
async def list_active_sessions(
    db: DbSession,
    current_user: CurrentUser,
    machine_id: Optional[int] = Query(default=None),
    part_id: Optional[int] = Query(default=None),
) -> list[ProductionSessionResponse]:
    """List active production sessions."""
    sessions = await session_service.get_active_sessions(
        db, machine_id=machine_id, part_id=part_id
    )

    return [
        ProductionSessionResponse(
            id=s.id,
            session_no=s.session_no,
            plan_id=s.plan_id,
            machine_id=s.machine_id,
            tooling_id=s.tooling_id,
            part_id=s.part_id,
            material_batch_id=s.material_batch_id,
            status=s.status,
            started_at=s.started_at,
            closed_at=s.closed_at,
            total_strokes=s.total_strokes,
            total_output=s.total_output,
            good_qty=s.good_qty,
            reject_qty=s.reject_qty,
            process_flow_id=s.process_flow_id,
            operator_id=s.operator_id,
            created_at=s.created_at,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ProductionSessionDetailResponse)
async def get_session(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSessionDetailResponse:
    """Get production session details with reports."""
    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    reports = [
        ProductionReportResponse(
            id=r.id,
            session_id=r.session_id,
            strokes=r.strokes,
            cavity_count=r.cavity_count,
            output=r.output,
            good_qty=r.good_qty,
            reject_qty=r.reject_qty,
            material_used=r.material_used,
            report_time=r.report_time,
            operator_id=r.operator_id,
            notes=r.notes,
            created_at=r.created_at,
        )
        for r in session.reports
    ]

    return ProductionSessionDetailResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        part_id=session.part_id,
        material_batch_id=session.material_batch_id,
        status=session.status,
        started_at=session.started_at,
        closed_at=session.closed_at,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        process_flow_id=session.process_flow_id,
        operator_id=session.operator_id,
        created_at=session.created_at,
        reports=reports,
    )


@router.post("/reports", response_model=ProductionReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_production_report(
    session_id: int,
    data: ProductionReportCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionReportResponse:
    """Submit a production report within a session."""
    require_role(current_user, min_level=1)

    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        report = await session_service.submit_report(
            db,
            session,
            strokes=data.strokes,
            cavity_count=data.cavity_count,
            good_qty=data.good_qty,
            reject_qty=data.reject_qty,
            material_used=data.material_used,
            notes=data.notes,
            operator_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionReportResponse(
        id=report.id,
        session_id=report.session_id,
        strokes=report.strokes,
        cavity_count=report.cavity_count,
        output=report.output,
        good_qty=report.good_qty,
        reject_qty=report.reject_qty,
        material_used=report.material_used,
        report_time=report.report_time,
        operator_id=report.operator_id,
        notes=report.notes,
        created_at=report.created_at,
    )


@router.post("/sessions/{session_id}/close", response_model=ProductionSessionResponse)
async def close_session(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ProductionSessionResponse:
    """Close a production session and generate process flow card."""
    require_role(current_user, min_level=1)

    session = await session_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        session = await session_service.close_session(db, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductionSessionResponse(
        id=session.id,
        session_no=session.session_no,
        plan_id=session.plan_id,
        machine_id=session.machine_id,
        tooling_id=session.tooling_id,
        part_id=session.part_id,
        material_batch_id=session.material_batch_id,
        status=session.status,
        started_at=session.started_at,
        closed_at=session.closed_at,
        total_strokes=session.total_strokes,
        total_output=session.total_output,
        good_qty=session.good_qty,
        reject_qty=session.reject_qty,
        process_flow_id=session.process_flow_id,
        operator_id=session.operator_id,
        created_at=session.created_at,
    )


@router.get("/process-flow-cards", response_model=list[ProcessFlowCardResponse])
async def list_process_flow_cards(
    db: DbSession,
    current_user: CurrentUser,
    part_id: Optional[int] = Query(default=None),
    machine_id: Optional[int] = Query(default=None),
    status_filter: Optional[ProcessFlowStatus] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProcessFlowCardResponse]:
    """List process flow cards."""
    from app.models.production import ProcessFlowStatus

    cards = await process_flow_service.get_process_flow_cards(
        db,
        part_id=part_id,
        machine_id=machine_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )

    return [
        ProcessFlowCardResponse(
            id=c.id,
            card_no=c.card_no,
            session_id=c.session_id,
            part_id=c.part_id,
            machine_id=c.machine_id,
            tooling_id=c.tooling_id,
            material_batch_no=c.material_batch_no,
            planned_qty=c.planned_qty,
            actual_output=c.actual_output,
            good_qty=c.good_qty,
            reject_qty=c.reject_qty,
            status=c.status,
            start_time=c.start_time,
            end_time=c.end_time,
            operator_id=c.operator_id,
            qr_code=c.qr_code,
            qr_image_base64=None,
            created_at=c.created_at,
        )
        for c in cards
    ]


# ── US4: Process Flow Card QR ────────────────────────────────────────────────

class PFCScanResponse(BaseModel):
    """Schema for process flow card scan response."""

    card_id: int
    card_no: str
    part_id: int
    part_name: Optional[str] = None
    machine_id: int
    machine_no: Optional[str] = None
    tooling_id: Optional[int] = None
    tooling_number: Optional[str] = None
    material_batch_no: Optional[str] = None
    planned_qty: int
    actual_output: int
    good_qty: int
    reject_qty: int
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    operator_id: Optional[int] = None
    qr_content: str
    qr_image_base64: str
    scan_history: list

    class Config:
        from_attributes = True


class PFCReverseTraceResponse(BaseModel):
    """Schema for reverse trace response."""

    card_id: int
    card_no: str
    status: str
    good_qty: int
    operator_id: Optional[int] = None
    material_batch_no: Optional[str] = None
    material_name: Optional[str] = None
    supplier_name: Optional[str] = None
    session_id: Optional[int] = None
    scan_history: list

    class Config:
        from_attributes = True


@router.get("/process-flow-cards/scan/{card_id}", response_model=PFCScanResponse)
async def scan_process_flow_card(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCScanResponse:
    """Scan process flow card: get full info, QR image, and scan history.

    Records the scan event in qr_scan_logs.
    """
    try:
        result = await process_flow_service.scan_process_flow_card(
            db, card_id, operator_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    card = result["card"]

    scan_history = []
    for log in result["scan_history"]:
        scan_history.append({
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        })

    return PFCScanResponse(
        card_id=card.id,
        card_no=card.card_no,
        part_id=card.part_id,
        part_name=card.part.internal_name if card.part else None,
        machine_id=card.machine_id,
        machine_no=card.machine.machine_no if card.machine else None,
        tooling_id=card.tooling_id,
        tooling_number=card.tooling.tooling_number if card.tooling else None,
        material_batch_no=card.material_batch_no,
        planned_qty=card.planned_qty,
        actual_output=card.actual_output,
        good_qty=card.good_qty,
        reject_qty=card.reject_qty,
        status=card.status.value if card.status else None,
        start_time=card.start_time.isoformat() if card.start_time else None,
        end_time=card.end_time.isoformat() if card.end_time else None,
        operator_id=card.operator_id,
        qr_content=result["qr_content"],
        qr_image_base64=result["qr_image_base64"],
        scan_history=scan_history,
    )


@router.get("/process-flow-cards/{card_id}/reverse-trace", response_model=PFCReverseTraceResponse)
async def reverse_trace_card(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCReverseTraceResponse:
    """Reverse trace: from card -> session -> material batch -> supplier.

    Returns the full provenance chain of a process flow card.
    """
    try:
        result = await process_flow_service.reverse_trace_card(db, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    card = result["card"]
    material_batch = result.get("material_batch")

    scan_history = []
    for log in result["scan_history"]:
        scan_history.append({
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        })

    return PFCReverseTraceResponse(
        card_id=card.id,
        card_no=card.card_no,
        status=card.status.value if card.status else None,
        good_qty=card.good_qty,
        operator_id=card.operator_id,
        material_batch_no=card.material_batch_no,
        material_name=material_batch.material_name if material_batch else None,
        supplier_name=material_batch.supplier_name if material_batch else None,
        session_id=card.session_id,
        scan_history=scan_history,
    )


class PFCInboundRequest(BaseModel):
    """Schema for process flow card inbound confirmation."""

    notes: Optional[str] = None


@router.put("/process-flow-cards/{card_id}/inbound", response_model=PFCReverseTraceResponse)
async def confirm_pfc_inbound(
    card_id: int,
    data: PFCInboundRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCReverseTraceResponse:
    """Confirm OQC passed and mark process flow card as inbound.

    Records the inbound operation in qr_scan_logs with operation='inbound'.
    """
    try:
        card = await process_flow_service.confirm_inbound(
            db, card_id,
            operator_id=current_user.id,
            notes=data.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get updated scan history
    from app.models.warehouse import QRScanLog
    history_result = await db.execute(
        select(QRScanLog)
        .where(QRScanLog.scan_type == "PFC", QRScanLog.entity_id == card.id)
        .order_by(QRScanLog.scanned_at.desc())
        .limit(20)
    )
    scan_history_obj = history_result.scalars().all()
    scan_history = [
        {
            "id": log.id,
            "operation": log.operation,
            "operator_id": log.operator_id,
            "notes": log.notes,
            "scanned_at": log.scanned_at.isoformat() if log.scanned_at else None,
        }
        for log in scan_history_obj
    ]

    return PFCReverseTraceResponse(
        card_id=card.id,
        card_no=card.card_no,
        status=card.status.value if card.status else None,
        good_qty=card.good_qty,
        operator_id=card.operator_id,
        material_batch_no=card.material_batch_no,
        material_name=None,
        supplier_name=None,
        session_id=card.session_id,
        scan_history=scan_history,
    )


# ── T027: PFC Reprint QR ───────────────────────────────────────────────────

class PFCReprintResponse(BaseModel):
    """Schema for process flow card reprint response."""

    card_id: int
    card_no: str
    qr_content: str
    qr_image_base64: str

    class Config:
        from_attributes = True


@router.post("/process-flow-cards/{card_id}/reprint-qr", response_model=PFCReprintResponse)
async def reprint_pfc_qr(
    card_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PFCReprintResponse:
    """Reprint QR code for a process flow card.

    Returns the card info with qr_content and qr_image_base64.
    Records the reprint operation in qr_scan_logs.
    """
    try:
        card = await process_flow_service.get_process_flow_card(db, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not card:
        raise HTTPException(status_code=404, detail="Process flow card not found")

    if not card.qr_code:
        raise HTTPException(status_code=400, detail="Card has no QR code")

    from app.services.qr_service import generate_process_flow_qr, generate_qr_base64
    qr_content = generate_process_flow_qr(card.id, card.card_no)
    qr_image_base64 = generate_qr_base64(qr_content)

    # Record reprint scan log
    from app.models.warehouse import QRScanLog
    log = QRScanLog(
        scan_type="PFC",
        entity_id=card.id,
        entity_no=card.card_no,
        operator_id=current_user.id,
        operation="reprint",
        notes="PFC QR code reprint",
    )
    db.add(log)
    await db.commit()

    return PFCReprintResponse(
        card_id=card.id,
        card_no=card.card_no,
        qr_content=qr_content,
        qr_image_base64=qr_image_base64,
    )
