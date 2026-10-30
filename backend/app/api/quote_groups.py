"""Persistent project quotation group API."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_role
from app.models.customer import Customer
from app.models.customer_inquiry import CustomerInquiry
from app.models.quote_group import QuoteGroup, QuoteGroupItem
from app.models.price import TreatmentDict
from app.services.costing_service import encode
from app.schemas.costing import MaterialCalculation
from app.services.costing_calculator import quotation_material
from app.schemas.quote_group import QuoteGroupCreate, QuoteGroupItemResponse, QuoteGroupResponse, QuoteGroupUpdate
from app.services.quote_press_service import LOCKED_QUOTE_GROUP_STATUSES, press_metadata, sync_quote_presses

router = APIRouter(prefix="/quote-groups", tags=["Quote Groups"])


def assert_quote_group_editable(group: QuoteGroup) -> None:
    if group.status in LOCKED_QUOTE_GROUP_STATUSES:
        raise HTTPException(status_code=409, detail="Quote group is locked")


def development_tooling_cost(group: QuoteGroup) -> Decimal | None:
    """Total the engineering snapshots, counting shared left/right tooling once."""
    if not group.items:
        return None
    total = Decimal("0")
    seen_pairs: set[str] = set()
    for item in group.items:
        if item.pair_key and item.pair_key in seen_pairs:
            continue
        if item.pair_key:
            seen_pairs.add(item.pair_key)
        snapshot = item.technical_snapshot or {}
        # Zero is a valid estimate only when engineering explicitly supplied it.
        if snapshot.get("toolingCost") in (None, "") and not item.tooling_cost:
            return None
        total += item.tooling_cost or Decimal("0")
    return total


async def _response(db: DbSession, group: QuoteGroup) -> QuoteGroupResponse:
    customer = await db.get(Customer, group.customer_id)
    return QuoteGroupResponse(
        id=group.id, group_no=group.group_no, inquiry_id=group.inquiry_id,
        customer_id=group.customer_id, customer=customer.name if customer else "",
        project_name=group.project_name, status=group.status, quote_path=group.quote_path,
        tooling_type=group.tooling_type, tooling_cost=group.tooling_cost,
        development_tooling_cost=development_tooling_cost(group),
        tooling_lead_time=group.tooling_lead_time, tooling_life=group.tooling_life,
        material_name=group.material_name, material_density=group.material_density,
        material_unit_price=group.material_unit_price, material_scrap_price=group.material_scrap_price,
        surface_treatment_fee=group.surface_treatment_fee, inspection_fee=group.inspection_fee,
        surface_rule_snapshot=group.surface_rule_snapshot,
        packaging_fee=group.packaging_fee, freight_fee=group.freight_fee,
        management_fee=group.management_fee, profit_margin=group.profit_margin,
        material_adjustment=group.material_adjustment, quote_note=group.quote_note,
        updated_at=group.updated_at, items=[_item_response(item) for item in group.items],
    )


def _item_response(item: QuoteGroupItem) -> QuoteGroupItemResponse:
    result = QuoteGroupItemResponse.model_validate(item)
    return result.model_copy(update=press_metadata(item.technical_snapshot, item.press_tonnage))


def _group_query():
    return select(QuoteGroup).options(selectinload(QuoteGroup.items)).order_by(QuoteGroup.updated_at.desc())


async def ensure_quote_group(db: DbSession, inquiry: CustomerInquiry, user_id: int) -> QuoteGroup:
    existing = (await db.execute(select(QuoteGroup).options(selectinload(QuoteGroup.items)).where(QuoteGroup.inquiry_id == inquiry.id))).scalar_one_or_none()
    if existing is not None:
        if existing.status not in LOCKED_QUOTE_GROUP_STATUSES:
            sync_quote_presses(existing, inquiry)
        return existing
    group = QuoteGroup(
        group_no=f"QG-{inquiry.id:06d}", inquiry_id=inquiry.id, customer_id=inquiry.customer_id,
        project_name=inquiry.project_name, status="待报价", created_by=user_id,
    )
    for index, data_item in enumerate(inquiry.technical_data or [], 1):
        part_numbers = [data_item.get("customerPartNo", "")]
        if data_item.get("isLeftRightPair") and data_item.get("customerPartNo2"):
            part_numbers.append(data_item["customerPartNo2"])
        for offset, part_no in enumerate(part_numbers):
            group.items.append(QuoteGroupItem(
                sequence=index + offset, customer_part_no=part_no.strip() or None,
                part_name=str(data_item.get("partName", "")).strip() or None,
                pair_key=data_item.get("key") if len(part_numbers) > 1 else None,
                material_name=str(data_item.get("material", "")).strip() or None,
                thickness=Decimal(str(data_item["thickness"])) if data_item.get("thickness") else None,
                width=Decimal(str(data_item["width"])) if data_item.get("width") else None,
                pitch=Decimal(str(data_item["pitch"])) if data_item.get("pitch") else None,
                utilization=Decimal(str(data_item["utilization"])) if data_item.get("utilization") else None,
                press_tonnage=int(data_item["pressTonnage"]) if data_item.get("pressTonnage") else None,
                cavity_count=int(data_item.get("cavityCount") or 1),
                tooling_cost=Decimal(str(data_item.get("toolingCost") or 0)),
                tooling_lead_time=int(data_item.get("toolingLeadTime") or 0),
                technical_snapshot=data_item,
            ))
    if group.items:
        group.material_name = group.items[0].material_name
        group.tooling_cost = development_tooling_cost(group) or Decimal("0")
        group.tooling_lead_time = group.items[0].tooling_lead_time
    db.add(group)
    await db.flush()
    return group


@router.get("", response_model=list[QuoteGroupResponse])
async def list_quote_groups(
    db: DbSession, current_user: CurrentUser,
    inquiry_id: int | None = Query(default=None), search: str | None = Query(default=None, max_length=100),
) -> list[QuoteGroupResponse]:
    query = _group_query()
    if inquiry_id is not None:
        query = query.where(QuoteGroup.inquiry_id == inquiry_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Customer, Customer.id == QuoteGroup.customer_id).where(
            QuoteGroup.group_no.ilike(term) | QuoteGroup.project_name.ilike(term) | Customer.name.ilike(term)
        )
    groups = (await db.execute(query)).scalars().unique().all()
    return [await _response(db, group) for group in groups]


@router.get("/{group_id}", response_model=QuoteGroupResponse)
async def get_quote_group(group_id: int, db: DbSession, current_user: CurrentUser) -> QuoteGroupResponse:
    group = (await db.execute(_group_query().where(QuoteGroup.id == group_id))).scalars().unique().first()
    if group is None:
        raise HTTPException(status_code=404, detail="Quote group not found")
    return await _response(db, group)


@router.post("", response_model=QuoteGroupResponse)
async def create_quote_group(data: QuoteGroupCreate, db: DbSession, current_user: CurrentUser) -> QuoteGroupResponse:
    require_role(current_user, min_level=2)
    inquiry = await db.get(CustomerInquiry, data.inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Customer inquiry not found")
    group = await ensure_quote_group(db, inquiry, current_user.id)
    await db.commit()
    group = (await db.execute(_group_query().where(QuoteGroup.id == group.id))).scalars().unique().first()
    return await _response(db, group)


@router.post("/{group_id}/sync-press", response_model=QuoteGroupResponse)
async def sync_quote_group_press(group_id: int, db: DbSession, current_user: CurrentUser) -> QuoteGroupResponse:
    """Refresh only press engineering fields from the approved inquiry; preserve prices."""
    require_role(current_user, min_level=2)
    group = (await db.execute(_group_query().where(QuoteGroup.id == group_id))).scalars().unique().first()
    if group is None:
        raise HTTPException(404, detail="Quote group not found")
    inquiry = await db.get(CustomerInquiry, group.inquiry_id)
    if inquiry is None:
        raise HTTPException(404, detail="Customer inquiry not found")
    sync_quote_presses(group, inquiry)
    await db.commit()
    return await _response(db, group)


@router.patch("/{group_id}", response_model=QuoteGroupResponse)
async def update_quote_group(group_id: int, data: QuoteGroupUpdate, db: DbSession, current_user: CurrentUser) -> QuoteGroupResponse:
    require_role(current_user, min_level=2)
    group = (await db.execute(_group_query().where(QuoteGroup.id == group_id))).scalars().unique().first()
    if group is None:
        raise HTTPException(status_code=404, detail="Quote group not found")
    assert_quote_group_editable(group)
    values = data.model_dump(exclude_unset=True)
    item_values = values.pop("items", None)
    refresh_rule = values.pop('refresh_surface_rule',False)
    if 'surface_rule_id' in values:
        rule_id = values.pop('surface_rule_id')
        if rule_id is None:
            group.surface_rule_snapshot = None
        elif refresh_rule or not group.surface_rule_snapshot or group.surface_rule_snapshot.get('id') != rule_id:
            rule = await db.get(TreatmentDict, rule_id)
            if not rule or not rule.is_active or (rule.calc_mode,rule.unit) not in {('manual','元/件'),('net_weight','元/kg')}:
                raise HTTPException(422,'请选择有效的按件或净重收费规则')
            group.surface_rule_snapshot = encode(dict(id=rule.id,name=rule.name,rate=rule.default_rate,
                method='net_kg' if rule.calc_mode=='net_weight' else 'piece',unit=rule.unit,updated_at=rule.updated_at))
    for field, value in values.items():
        setattr(group, field, value)
    if item_values is not None:
        if len(item_values) != len(group.items):
            raise HTTPException(status_code=400, detail="Quote item count does not match")
        for item, item_data in zip(group.items, item_values):
            for field, value in item_data.items():
                setattr(item, field, value)
    # Preserve the legacy per-piece fee field for older consumers while keeping
    # the selected rule/rate snapshot authoritative for each quote line.
    if group.surface_rule_snapshot:
        snapshot=group.surface_rule_snapshot
        if snapshot['method']=='piece':
            group.surface_treatment_fee=Decimal(snapshot['rate'])
        else:
            amounts=[]
            for item in group.items:
                estimate=quotation_material(MaterialCalculation(thickness=item.thickness,width=item.width,pitch=item.pitch,
                    density=group.material_density,utilization_pct=item.utilization))
                if estimate['net_weight_g'] is None:
                    raise HTTPException(422,'按净重收费需要每个报价零件的规格、密度和材料利用率')
                amounts.append(Decimal(estimate['net_weight_g'])/Decimal(1000)*Decimal(snapshot['rate']))
            if not amounts:
                raise HTTPException(422,'按净重收费需要至少一个报价零件')
            group.surface_treatment_fee=amounts[0]
    group.status = "已报价"
    await db.commit()
    group = (await db.execute(_group_query().where(QuoteGroup.id == group.id))).scalars().unique().first()
    return await _response(db, group)
