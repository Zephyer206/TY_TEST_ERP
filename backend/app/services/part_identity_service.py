"""Canonical customer-part identity helpers.

Customer part numbers are scoped by customer and live exclusively in
``part_customer_aliases``.  This module keeps lookup and upsert behavior in one
place while the old denormalized part columns are retired.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.part_customer_alias import PartCustomerAlias


async def get_part_aliases(
    db: AsyncSession,
    part_id: int,
    customer_id: Optional[int] = None,
    *,
    include_pending: bool = False,
) -> list[PartCustomerAlias]:
    query = select(PartCustomerAlias).where(
        PartCustomerAlias.part_id == part_id,
        PartCustomerAlias.is_active == True,
    )
    if customer_id is not None:
        query = query.where(PartCustomerAlias.customer_id == customer_id)
    if not include_pending:
        query = query.where(PartCustomerAlias.data_quality_status == "approved")
    query = query.order_by(
        PartCustomerAlias.customer_id,
        PartCustomerAlias.revision,
        PartCustomerAlias.id,
    )
    return list((await db.execute(query)).scalars().all())


async def get_primary_part_alias(
    db: AsyncSession,
    part_id: int,
    customer_id: Optional[int] = None,
) -> Optional[PartCustomerAlias]:
    aliases = await get_part_aliases(db, part_id, customer_id)
    return aliases[0] if aliases else None


async def resolve_part_id_by_customer_part_no(
    db: AsyncSession,
    customer_part_no: str,
    customer_id: Optional[int] = None,
) -> Optional[int]:
    value = customer_part_no.strip()
    if not value:
        return None
    query = select(PartCustomerAlias.part_id).where(
        PartCustomerAlias.customer_part_no == value,
        PartCustomerAlias.is_active == True,
        PartCustomerAlias.data_quality_status == "approved",
    )
    if customer_id is not None:
        query = query.where(PartCustomerAlias.customer_id == customer_id)
    row = (await db.execute(query.order_by(PartCustomerAlias.id))).first()
    return row[0] if row else None


async def upsert_part_alias(
    db: AsyncSession,
    *,
    part_id: int,
    customer_id: int,
    customer_part_no: str,
    customer_part_name: Optional[str] = None,
    vehicle_model: Optional[str] = None,
    revision: str = "",
) -> PartCustomerAlias:
    customer_part_no = customer_part_no.strip()
    if not customer_part_no:
        raise ValueError("customer_part_no is required")
    query = select(PartCustomerAlias).where(
        PartCustomerAlias.customer_id == customer_id,
        PartCustomerAlias.customer_part_no == customer_part_no,
        PartCustomerAlias.revision == revision,
    )
    alias = (await db.execute(query)).scalar_one_or_none()
    if alias is None:
        alias = PartCustomerAlias(
            part_id=part_id,
            customer_id=customer_id,
            customer_part_no=customer_part_no,
            customer_part_name=customer_part_name,
            vehicle_model=vehicle_model,
            revision=revision,
            is_active=True,
            data_quality_status="approved",
        )
        db.add(alias)
    else:
        alias.part_id = part_id
        alias.customer_part_name = customer_part_name
        alias.vehicle_model = vehicle_model
        alias.is_active = True
        alias.data_quality_status = "approved"
        alias.data_quality_reason = None
    await db.flush()
    return alias
