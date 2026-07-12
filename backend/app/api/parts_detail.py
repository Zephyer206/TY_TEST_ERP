"""Parts detail API with proper relationship queries."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models.customer import Customer
from app.models.part import Part
from app.models.part_customer_alias import PartCustomerAlias
from app.models.tooling import Tooling, ToolingPart
from app.models.tooling_customer_link import ToolingCustomerLink
from app.models.tooling_step import ToolingStep
from app.schemas.part_detail import PartDetailResponse, PartCustomerAliasInfo, PartToolingInfo, ToolingStepInfo

router = APIRouter(prefix="/parts", tags=["Parts Detail"])


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
        .where(ToolingPart.part_id == part_id)
        .order_by(ToolingPart.is_primary.desc(), Tooling.tooling_number)
    )
    tooling_result = await db.execute(tooling_query)
    tooling_data = tooling_result.all()

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
                is_primary=tp.is_primary,
                steps=steps if steps else None,
                tooling_customers=tooling_customer_names if tooling_customer_names else None,
            )
        )

    return PartDetailResponse(
        id=part.id,
        internal_name=part.internal_name,
        internal_part_no=part.internal_part_no,
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
    )
