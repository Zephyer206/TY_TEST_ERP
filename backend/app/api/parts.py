"""Parts API endpoints - 匹配实际数据库字段."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, or_, distinct
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.customer import Customer
from app.models.part import Part
from app.models.tooling import Tooling, ToolingPart
from app.models.part_customer_alias import PartCustomerAlias
from app.models.material_dict import MaterialDict
from app.schemas.part import (
    PartCreate,
    PartDisplayGroup,
    PartDisplayPage,
    PartResponse,
    PartUpdate,
)

router = APIRouter(prefix="/parts", tags=["Parts"])


def _apply_part_filters(q, search, customer_id, part_status, material):
    """Apply the shared parts-list filters to a SELECT statement."""
    if search:
        customer_alias_subq = select(PartCustomerAlias.part_id).where(
            PartCustomerAlias.customer_part_no.ilike(f"%{search}%")
        )
        tooling_subq = select(ToolingPart.part_id).join(
            Tooling, ToolingPart.tooling_id == Tooling.id
        ).where(
            or_(
                Tooling.tooling_number.ilike(f"%{search}%"),
                Tooling.tooling_no.ilike(f"%{search}%")
            )
        )
        q = q.where(or_(
            Part.internal_name.ilike(f"%{search}%"),
            Part.part_number.ilike(f"%{search}%"),
            Part.id.in_(customer_alias_subq),
            Part.id.in_(tooling_subq),
        ))

    if customer_id:
        customer_part_subq = select(PartCustomerAlias.part_id).where(
            PartCustomerAlias.customer_id == customer_id
        )
        q = q.where(Part.id.in_(customer_part_subq))

    if part_status:
        q = q.where(Part.part_status == part_status)
    if material:
        q = q.where(Part.material_name.ilike(f"%{material}%"))

    return q


async def _to_resp(db, p: Part) -> PartResponse:
    customer = await db.get(Customer, p.customer_id) if p.customer_id else None
    return PartResponse(
        id=p.id,
        part_number=p.part_number,
        internal_name=p.internal_name,
        customer_id=p.customer_id,
        customer_name=customer.name if customer else None,
        customer_product_no=p.customer_product_no,
        vehicle_model=p.vehicle_model,
        material_name=p.material_name,
        part_status=p.part_status,
        stock_pcs=p.stock_pcs,
        mold_number=p.mold_number,
        mold_type=p.mold_type,
        press_tonnage=p.press_tonnage,
        ppap_no=p.ppap_no,
        thickness=float(p.thickness) if p.thickness else None,
        width=float(p.width) if p.width else None,
        pitch=float(p.pitch) if p.pitch else None,
        spec_twph=p.spec_twph,
        part_position=p.part_position,
        remark=p.remark,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _build_part_responses(db, parts: list[Part]) -> list[PartResponse]:
    """Build list-page responses with relation-based customer/tooling summaries."""
    if not parts:
        return []

    part_ids = [p.id for p in parts]

    customer_aliases = {}
    aliases_result = await db.execute(
        select(PartCustomerAlias).where(PartCustomerAlias.part_id.in_(part_ids))
    )
    for alias in aliases_result.scalars():
        customer_aliases.setdefault(alias.part_id, []).append(alias)

    cust_ids = list({
        alias.customer_id
        for aliases in customer_aliases.values()
        for alias in aliases
    })
    customers = {}
    if cust_ids:
        customers = {c.id: c for c in (await db.execute(
            select(Customer).where(Customer.id.in_(cust_ids))
        )).scalars()}

    tooling_parts_map = {}
    tp_result = await db.execute(
        select(ToolingPart).where(ToolingPart.part_id.in_(part_ids))
    )
    for tp in tp_result.scalars():
        tooling_parts_map.setdefault(tp.part_id, []).append(tp)

    tooling_ids = list({
        tp.tooling_id
        for tps in tooling_parts_map.values()
        for tp in tps
    })
    toolings = {}
    if tooling_ids:
        toolings = {t.id: t for t in (await db.execute(
            select(Tooling).where(Tooling.id.in_(tooling_ids))
        )).scalars()}

    material_ids = list({p.material_id for p in parts if p.material_id})
    materials = {}
    if material_ids:
        materials = {m.id: m for m in (await db.execute(
            select(MaterialDict).where(MaterialDict.id.in_(material_ids))
        )).scalars()}

    results = []
    for p in parts:
        aliases = customer_aliases.get(p.id, [])
        customer_summary = None
        if aliases:
            names = sorted({
                customers[a.customer_id].name
                for a in aliases
                if a.customer_id in customers
            })
            customer_summary = ", ".join(names[:3])
            if len(names) > 3:
                customer_summary += f" (+{len(names) - 3})"

        tps = tooling_parts_map.get(p.id, [])
        mold_summary = None
        if tps:
            mold_numbers = sorted({
                toolings[tp.tooling_id].tooling_number
                or toolings[tp.tooling_id].tooling_no
                for tp in tps
                if tp.tooling_id in toolings
                and (toolings[tp.tooling_id].tooling_number or toolings[tp.tooling_id].tooling_no)
            })
            mold_summary = ", ".join(mold_numbers[:3])
            if len(mold_numbers) > 3:
                mold_summary += f" (+{len(mold_numbers) - 3})"

        results.append(PartResponse(
            id=p.id,
            part_number=p.part_number,
            internal_name=p.internal_name,
            customer_id=None,
            customer_name=customer_summary,
            customer_product_no=None,
            customer_product_name=p.customer_product_name,
            vehicle_model=p.vehicle_model,
            material_name=p.material_name,
            material_name_full=materials[p.material_id].name if p.material_id in materials else None,
            part_status=p.part_status,
            stock_pcs=p.stock_pcs,
            mold_number=mold_summary,
            mold_type=p.mold_type,
            press_tonnage=p.press_tonnage,
            ppap_no=p.ppap_no,
            spec_twph=p.spec_twph,
            thickness=p.thickness,
            width=p.width,
            pitch=p.pitch,
            height=p.height,
            gross_weight=p.gross_weight,
            net_weight=p.net_weight,
            part_position=p.part_position,
            cavity_count=None,
            remark=p.remark,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))

    return results


async def _load_left_right_pair_lookup(db):
    """Return part_id -> (base tooling number, ordered member ids)."""
    rows = (await db.execute(
        select(ToolingPart.part_id, Tooling.tooling_number, Part.part_position)
        .join(Tooling, ToolingPart.tooling_id == Tooling.id)
        .join(Part, Part.id == ToolingPart.part_id)
        .where(Part.part_position.in_(["left", "right"]))
    )).all()

    candidates = {}
    for part_id, tooling_number, position in rows:
        if not tooling_number or not tooling_number.endswith(("-1", "-2")):
            continue
        base_number = tooling_number[:-2]
        candidates.setdefault(base_number, {}).setdefault(position, set()).add(part_id)

    lookup = {}
    for base_number, positions in candidates.items():
        left_ids = positions.get("left", set())
        right_ids = positions.get("right", set())
        if len(left_ids) != 1 or len(right_ids) != 1:
            continue
        left_id = next(iter(left_ids))
        right_id = next(iter(right_ids))
        if left_id == right_id:
            continue
        member_ids = [left_id, right_id]
        lookup[left_id] = (base_number, member_ids)
        lookup[right_id] = (base_number, member_ids)

    return lookup


@router.get("/count")
async def count_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
) -> dict[str, int]:
    """Count parts with the same filters as list_parts - returns total distinct parts."""
    q = _apply_part_filters(
        select(Part.id), search, customer_id, part_status, material
    )

    # Count distinct parts
    result = await db.execute(select(distinct(Part.id)).select_from(Part).where(Part.id.in_(q)))
    total = len(result.all())

    return {"total": total}


@router.get("", response_model=list[PartResponse])
async def list_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PartResponse]:
    q = _apply_part_filters(
        select(Part), search, customer_id, part_status, material
    )

    # Stable ordering: created_at DESC, then id DESC for deterministic pagination
    q = q.order_by(Part.created_at.desc().nulls_last(), Part.id.desc()).offset(skip).limit(limit)
    parts = (await db.execute(q)).scalars().all()
    return await _build_part_responses(db, parts)


@router.get("/grouped", response_model=PartDisplayPage)
async def list_grouped_parts(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    part_status: Optional[str] = Query(default=None),
    material: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PartDisplayPage:
    """List parts as display groups, merging valid left/right pairs into one row.

    Pairing is intentionally strict: both parts must have explicit left/right
    positions and tooling numbers with the same base plus ``-1``/``-2`` suffixes.
    Filtering matches either member and returns the complete pair.
    """
    id_query = _apply_part_filters(
        select(Part.id), search, customer_id, part_status, material
    ).order_by(Part.created_at.desc().nulls_last(), Part.id.desc())
    filtered_ids = list((await db.execute(id_query)).scalars().all())

    pair_lookup = await _load_left_right_pair_lookup(db)
    descriptors = []
    seen_pairs = set()

    for part_id in filtered_ids:
        pair_info = pair_lookup.get(part_id)
        if pair_info:
            base_number, member_ids = pair_info
            if base_number in seen_pairs:
                continue
            seen_pairs.add(base_number)
            descriptors.append((f"pair:{base_number}", True, member_ids))
        else:
            descriptors.append((f"part:{part_id}", False, [part_id]))

    total = len(descriptors)
    page_descriptors = descriptors[skip:skip + limit]
    selected_ids = list({
        part_id
        for _, _, member_ids in page_descriptors
        for part_id in member_ids
    })

    if not selected_ids:
        return PartDisplayPage(total=total, items=[])

    selected_parts = (await db.execute(
        select(Part).where(Part.id.in_(selected_ids))
    )).scalars().all()
    selected_parts.sort(
        key=lambda p: (
            0 if p.part_position == "left" else 1 if p.part_position == "right" else 2,
            p.id,
        )
    )
    responses = await _build_part_responses(db, selected_parts)
    response_by_id = {response.id: response for response in responses}

    items = []
    for key, is_pair, member_ids in page_descriptors:
        members = [response_by_id[part_id] for part_id in member_ids if part_id in response_by_id]
        if not members:
            continue
        items.append(PartDisplayGroup(
            key=key,
            is_left_right_pair=is_pair and len(members) == 2,
            members=members,
        ))

    return PartDisplayPage(total=total, items=items)


@router.post("", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
async def create_part(data: PartCreate, db: DbSession, current_user: CurrentUser) -> PartResponse:
    require_role(current_user, min_level=4)
    existing = (await db.execute(select(Part).where(Part.part_number == data.part_number))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="零件编号已存在")
    part = Part(
        part_number=data.part_number,
        internal_name=data.internal_name,
        customer_id=data.customer_id,
        customer_product_no=data.customer_product_no,
        vehicle_model=data.vehicle_model,
        material_name=data.material_name,
        remark=data.remark,
        part_status="DRAFT",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return await _to_resp(db, part)


@router.get("/{part_id}", response_model=PartResponse)
async def get_part(part_id: int, db: DbSession, current_user: CurrentUser) -> PartResponse:
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return await _to_resp(db, part)


@router.patch("/{part_id}", response_model=PartResponse)
async def update_part(part_id: int, data: PartUpdate, db: DbSession, current_user: CurrentUser) -> PartResponse:
    require_role(current_user, min_level=4)
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    part.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(part)
    return await _to_resp(db, part)


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part(part_id: int, db: DbSession, current_user: CurrentUser) -> None:
    require_role(current_user, min_level=4)
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    # 软删除：改状态
    part.part_status = "OBSOLETE"
    part.updated_at = datetime.utcnow()
    await db.commit()
