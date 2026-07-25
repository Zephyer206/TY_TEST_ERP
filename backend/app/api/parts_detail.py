"""Parts detail API with proper relationship queries."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import distinct, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.tooling import Tooling, ToolingPart
from app.models.tooling_shared_relation import ToolingSharedRelation
from app.models.tooling_customer_link import ToolingCustomerLink
from app.models.tooling_step import ToolingStep
from app.schemas.part_detail import (
    PartCustomerAliasInfo,
    PartDetailResponse,
    PartToolingInfo,
    SharedToolingRelationInfo,
    ToolingStepInfo,
)

router = APIRouter(prefix="/parts", tags=["Parts Detail"])


def _select_primary_tooling(tooling_data):
    """Prefer a continuous mold as the primary tooling in part details."""
    if not tooling_data:
        return None

    continuous_data = [
        record for record in tooling_data
        if record[1].is_continuous
    ]
    preferred_data = continuous_data or tooling_data
    return sorted(
        preferred_data,
        key=lambda record: (
            not record[0].is_primary,
            str(record[1].tooling_number or record[1].tooling_no or ""),
            record[1].id,
        ),
    )[0]


@router.get("/{part_id}/detail", response_model=PartDetailResponse)
async def get_part_detail(
    part_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> PartDetailResponse:
    """获取零件详情，包含所有关联关系。"""
    # Get part
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="零件不存在")

    # Get all customer aliases via part_customer_aliases
    aliases_query = (
        select(PartCustomerAlias, Customer)
        .join(Customer, PartCustomerAlias.customer_id == Customer.id)
        .where(PartCustomerAlias.part_id == part_id)
        .order_by(PartCustomerAlias.is_active.desc(), Customer.name)
    )
    aliases_result = await db.execute(aliases_query)
    aliases_data = aliases_result.all()

    # A customer part number can have separate internal rows for different
    # mold types.  Detail must keep those tooling records together while
    # retaining the underlying part rows unchanged.
    identity_conditions = [
        (
            PartCustomerAlias.customer_id == alias.customer_id,
            PartCustomerAlias.customer_part_no == alias.customer_part_no,
        )
        for alias, _customer in aliases_data
        if alias.is_active and alias.customer_part_no and alias.customer_part_no.strip()
    ]
    related_part_ids = {part_id}
    if identity_conditions:
        related_result = await db.execute(
            select(distinct(PartCustomerAlias.part_id)).where(
                PartCustomerAlias.is_active == True,
                or_(*(
                    (condition[0] & condition[1])
                    for condition in identity_conditions
                )),
            )
        )
        related_part_ids.update(related_result.scalars().all())

    customer_aliases = [
        PartCustomerAliasInfo(
            customer_id=alias.customer_id,
            customer_name=customer.name,
            customer_code=customer.customer_code,
            customer_part_no=alias.customer_part_no,
            customer_part_name=alias.customer_part_name,
            vehicle_model=alias.vehicle_model,
            revision=alias.revision,
            is_active=alias.is_active,
        )
        for alias, customer in aliases_data
    ]

    # Get all tooling via tooling_parts
    tooling_query = (
        select(ToolingPart, Tooling)
        .join(Tooling, ToolingPart.tooling_id == Tooling.id)
        .where(ToolingPart.part_id.in_(related_part_ids))
        .order_by(ToolingPart.is_primary.desc(), Tooling.tooling_number)
    )
    tooling_result = await db.execute(tooling_query)
    tooling_data = tooling_result.all()
    primary_tooling = _select_primary_tooling(tooling_data)
    primary_tooling_part_id = primary_tooling[0].id if primary_tooling else None

    tooling_data = sorted(
        tooling_data,
        key=lambda record: (
            record[0].id != primary_tooling_part_id,
            not record[1].is_continuous,
            str(record[1].tooling_number or record[1].tooling_no or ""),
            record[1].id,
        ),
    )

    tooling_list = []
    for tp, tooling in tooling_data:
        # Get steps for non-continuous molds
        steps = []
        if not tooling.is_continuous:
            steps_query = (
                select(ToolingStep)
                .where(ToolingStep.tooling_id == tooling.id)
                .order_by(ToolingStep.sequence, ToolingStep.step_no)
            )
            steps_result = await db.execute(steps_query)
            steps_data = steps_result.scalars().all()
            steps = [
                ToolingStepInfo(
                    step_no=s.step_no,
                    step_code=s.step_code,
                    step_name=s.step_name,
                    operation_type=s.operation_type,
                    sequence=s.sequence,
                )
                for s in steps_data
            ]

        # Get tooling customers via tooling_customer_links
        tooling_customers_query = (
            select(ToolingCustomerLink, Customer)
            .join(Customer, ToolingCustomerLink.customer_id == Customer.id)
            .where(ToolingCustomerLink.tooling_id == tooling.id)
            .order_by(ToolingCustomerLink.is_owner.desc(), Customer.name)
        )
        tooling_customers_result = await db.execute(tooling_customers_query)
        tooling_customers_data = tooling_customers_result.all()

        tooling_customer_names = [
            f"{customer.name}({customer.customer_code or '无代号'})"
            for link, customer in tooling_customers_data
        ]

        tooling_list.append(
            PartToolingInfo(
                tooling_id=tooling.id,
                tooling_number=tooling.tooling_number or tooling.tooling_no,
                tooling_name=tooling.tooling_name or tooling.name,
                mold_type=tooling.mold_type,
                is_continuous=tooling.is_continuous,
                cavity_count=tooling.cavity_count,
                process_step_count=tooling.process_step_count if not tooling.is_continuous else None,
                status=tooling.status,
                position=tp.position,
                is_primary=tp.id == primary_tooling_part_id,
                steps=steps if steps else None,
                tooling_customers=tooling_customer_names if tooling_customer_names else None,
            )
        )

    # Shared-mold links are separate from tooling/part ownership. Include any
    # source-backed relation touching a tooling record shown for this part.
    shared_relations: list[SharedToolingRelationInfo] = []
    tooling_ids = {tooling.id for _tp, tooling in tooling_data}
    if tooling_ids:
        relation_result = await db.execute(
            select(ToolingSharedRelation)
            .where(
                or_(
                    ToolingSharedRelation.tooling_id.in_(tooling_ids),
                    ToolingSharedRelation.related_tooling_id.in_(tooling_ids),
                )
            )
            .order_by(ToolingSharedRelation.id)
        )
        relation_rows = relation_result.scalars().all()
        other_ids = {
            relation.related_tooling_id
            if relation.tooling_id in tooling_ids
            else relation.tooling_id
            for relation in relation_rows
        }
        other_result = await db.execute(select(Tooling).where(Tooling.id.in_(other_ids))) if other_ids else None
        number_by_id = {
            tooling.id: tooling.tooling_number or tooling.tooling_no
            for tooling in (other_result.scalars().all() if other_result else [])
        }
        number_by_id.update({tooling.id: tooling.tooling_number or tooling.tooling_no for _tp, tooling in tooling_data})
        shared_relations = [
            SharedToolingRelationInfo(
                relation_id=relation.id,
                tooling_id=relation.tooling_id,
                tooling_number=number_by_id.get(relation.tooling_id),
                related_tooling_id=relation.related_tooling_id,
                related_tooling_number=number_by_id.get(relation.related_tooling_id),
                relation_scope=relation.relation_scope,
                source_sheet=relation.source_sheet,
                source_row=relation.source_row,
                source_note=relation.source_note,
                confidence=relation.confidence,
            )
            for relation in relation_rows
        ]

    return PartDetailResponse(
        id=part.id,
        internal_name=part.internal_name,
        internal_part_no=part.internal_part_no,
        drawing_url=part.drawing_url,
        material_name=part.material_name,
        thickness=float(part.thickness) if part.thickness else None,
        width=float(part.width) if part.width else None,
        pitch=float(part.pitch) if part.pitch else None,
        gross_weight=float(part.gross_weight) if part.gross_weight else None,
        net_weight=float(part.net_weight) if part.net_weight else None,
        part_position=part.part_position,
        part_status=part.part_status,
        customer_aliases=customer_aliases if customer_aliases else [],
        tooling=tooling_list if tooling_list else [],
        shared_tooling_relations=shared_relations,
    )
