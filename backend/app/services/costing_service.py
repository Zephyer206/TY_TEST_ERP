"""Resolve explicit part/tooling/spec identity and source-backed calculation inputs."""
from decimal import Decimal
import hashlib
import json
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from app.models.part import Part
from app.models.customer import Customer
from app.models.part_customer_alias import PartCustomerAlias
from app.models.part_tooling_spec import PartToolingSpec
from app.models.tooling import Tooling, ToolingPart
from app.models.material_dict import MaterialDict
from app.models.price import TreatmentDict
from app.models.quote_group import QuoteGroup, QuoteGroupItem
from app.api.part_treatments import treatment_of
from app.services.costing_calculator import calculate_simple


def encode(value):
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def digest(value):
    return hashlib.sha256(json.dumps(encode(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def eligibility(tooling):
    kind = (tooling.mold_type or '').strip()
    continuous = kind in {'连续模', 'continuous'}
    engineering = kind in {'工程模', 'engineering'}
    if not (continuous or engineering):
        return 'excluded', '仅连续模或工程模量产方案参与核算'
    if continuous != bool(tooling.is_continuous):
        return 'needs_review', '模具类型与连续模标识不一致，请先核对主档'
    return 'eligible', ''


async def resolve_identity(db, alias_id, part_id, tooling_id, spec_id, customer_id=None):
    alias = await db.get(PartCustomerAlias, alias_id)
    part = await db.get(Part, part_id)
    tooling = await db.get(Tooling, tooling_id)
    if not alias or not part or not tooling or part.is_deleted or tooling.is_deleted:
        raise HTTPException(404, '零件或模具不存在')
    if alias.part_id != part.id or not alias.is_active or alias.data_quality_status != 'approved' or (customer_id and alias.customer_id != customer_id):
        raise HTTPException(422, '客户、件号和零件归属不一致或别名待复核')
    link = (await db.execute(select(ToolingPart.id).where(ToolingPart.part_id == part.id, ToolingPart.tooling_id == tooling.id))).first()
    if not link:
        raise HTTPException(422, '该模具不属于所选零件')
    state, reason = eligibility(tooling)
    if state != 'eligible':
        raise HTTPException(422, reason)
    spec = await db.get(PartToolingSpec, spec_id) if spec_id else None
    if spec_id and (not spec or spec.part_id != part.id or spec.tooling_id != tooling.id):
        raise HTTPException(422, '规格不属于本次零件及模具')
    customer = await db.get(Customer, alias.customer_id)
    return part, alias, tooling, spec, customer


async def context_for(db, identity):
    part, alias, tooling, spec, customer = identity
    quote_rows = (await db.execute(select(QuoteGroupItem, QuoteGroup)
        .join(QuoteGroup, QuoteGroupItem.quote_group_id == QuoteGroup.id)
        .where(QuoteGroup.customer_id == alias.customer_id,
               QuoteGroupItem.customer_part_no == alias.customer_part_no)
        .order_by(QuoteGroup.updated_at.desc(), QuoteGroupItem.id))).all()
    return encode(dict(part_id=part.id, alias_id=alias.id, customer_id=alias.customer_id,
        customer=customer.name, part_name=part.internal_name, customer_part_no=alias.customer_part_no,
        material_name=part.material_name, material_id=part.material_id, drawing_url=part.drawing_url,
        tooling_id=tooling.id, tooling_number=tooling.tooling_number, mold_type=tooling.mold_type,
        spec_id=spec.id if spec else None, spec_twph=spec.spec_twph if spec else part.spec_twph,
        thickness=spec.thickness if spec else part.thickness, width=spec.width if spec else part.width,
        pitch=spec.pitch if spec else part.pitch, gross_weight_g=part.gross_weight,
        net_weight_g=part.net_weight, cavity_count=tooling.cavity_count,
        part_updated_at=part.updated_at, tooling_updated_at=tooling.updated_at,
        spec_updated_at=spec.updated_at if spec else None,
        surface_treatment=treatment_of(part),
        quotes=[dict(item_id=i.id, quote_no=g.group_no, utilization_pct=i.utilization,
            thickness=i.thickness, width=i.width, pitch=i.pitch, density=g.material_density,
            material_price=g.material_unit_price, scrap_price=g.material_scrap_price,
            surface_fee=g.surface_treatment_fee, updated_at=g.updated_at) for i,g in quote_rows]))


async def resolve_calculation(db, identity, request, source_reference=None):
    part, alias, tooling, spec, customer = identity
    context = await context_for(db, identity)
    context['import_source'] = source_reference
    calculation = request.calculation.model_copy(deep=True)
    material = calculation.material
    sources = dict(price_source=request.price_source, note=request.source_note)
    if request.price_source == 'catalog':
        record = await db.get(MaterialDict, request.material_id) if request.material_id else None
        if not record or not record.is_active:
            raise HTTPException(422, '请选择有效的共用材料价格资料')
        material.material_price = record.default_price
        material.scrap_price = record.scrap_price
        material.density = record.density
        sources['material'] = encode(dict(id=record.id, name=record.name, updated_at=record.updated_at,
            price=record.default_price, scrap=record.scrap_price, density=record.density))
    elif request.price_source == 'quote':
        item = await db.get(QuoteGroupItem, request.quote_item_id) if request.quote_item_id else None
        group = await db.get(QuoteGroup, item.quote_group_id) if item else None
        if not group or group.customer_id != alias.customer_id or item.customer_part_no != alias.customer_part_no:
            raise HTTPException(422, '报价与客户件号不匹配')
        material.material_price = group.material_unit_price
        material.scrap_price = group.material_scrap_price
        material.density = group.material_density
        material.utilization_pct = item.utilization
        if all(v is not None for v in [item.thickness, item.width, item.pitch, group.material_density]):
            material.quoted_gross_weight_g = item.thickness * item.width * item.pitch * group.material_density / Decimal(1000) / material.pieces_per_blank
        sources['quote'] = encode(dict(item_id=item.id, group_id=group.id, quote_no=group.group_no,
            updated_at=group.updated_at, material_price=group.material_unit_price,
            scrap_price=group.material_scrap_price, density=group.material_density,
            utilization=item.utilization, thickness=item.thickness, width=item.width, pitch=item.pitch))
    elif not request.source_note.strip():
        raise HTTPException(422, '补充材料价格请填写依据')
    # The selected spec always supplies dimensions. Recorded measured net weight takes precedence.
    for field in ['thickness', 'width', 'pitch']:
        value = getattr(spec, field) if spec else getattr(part, field)
        setattr(material, field, value)
    if part.net_weight is not None:
        material.net_weight_g = part.net_weight
    if ((material.gross_weight_g is not None and material.gross_weight_g != part.gross_weight) or (part.net_weight is None and material.net_weight_g is not None)
            or (request.price_source != 'quote' and material.net_weight_g is None)) and not request.source_note.strip():
        raise HTTPException(422, '补充重量或报价利用率资料请填写依据')
    requirements = treatment_of(part)
    calculation.treatment_status = requirements['status']
    required = {entry['item_key']: entry for entry in requirements['items']}
    submitted = [entry.item_key for entry in calculation.treatments]
    if len(submitted) != len(set(submitted)) or any(key not in required for key in submitted):
        raise HTTPException(422, '处理费用必须关联该零件的处理项，且不得重复')
    if requirements['status'] == 'required' and set(submitted) != set(required):
        # Return partial results as incomplete, never silently drop a required treatment.
        from app.schemas.costing import TreatmentCharge
        for key in set(required) - set(submitted):
            calculation.treatments.append(TreatmentCharge(item_key=key, name=required[key]['name']))
    rule_sources = []
    for charge in calculation.treatments:
        charge.name = required[charge.item_key]['name']
        if charge.rule_id:
            rule = await db.get(TreatmentDict, charge.rule_id)
            if not rule or not rule.is_active:
                raise HTTPException(422, '表面收费规则不存在或已停用')
            supported = {('manual', '元/件'): 'piece', ('net_weight', '元/kg'): 'net_kg'}
            method = supported.get((rule.calc_mode, rule.unit))
            if method is None:
                raise HTTPException(422, '该收费规则单位尚不支持，请使用有依据的补充收费')
            charge.method, charge.rate = method, rule.default_rate
            charge.source = f'共用收费规则：{rule.name}'
            rule_sources.append(encode(dict(id=rule.id, name=rule.name, updated_at=rule.updated_at,
                rate=rule.default_rate, method=rule.calc_mode, unit=rule.unit)))
    sources['treatment_rules'] = rule_sources
    context['sources'] = sources
    token = digest(context)
    if request.expected_source_token and token != request.expected_source_token:
        raise HTTPException(409, '零件/模具/规格或计价来源已经变化，请重新加载核对；本地输入保留')
    # Revalidate assignments sourced from legacy data before any arithmetic.
    from app.schemas.costing import SimpleCalculation
    from pydantic import ValidationError
    try:
        calculation = SimpleCalculation.model_validate(calculation.model_dump())
    except ValidationError:
        raise HTTPException(422, '来源中的重量、利用率或费率超出有效范围，请核对资料')
    return dict(calculation=calculation.model_dump(mode='json'), result=calculate_simple(calculation),
                context=context, source_token=token)
