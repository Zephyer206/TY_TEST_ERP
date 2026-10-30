"""Pure Decimal calculation used by BOTH quotation and costing endpoints."""
from decimal import Decimal, ROUND_HALF_UP
from app.schemas.costing import MaterialCalculation, SimpleCalculation

RULE_VERSION = 'simple-2026-10-29.1'
SIX = Decimal('0.000001')


def number(value):
    return None if value is None else str(value.quantize(SIX, rounding=ROUND_HALF_UP))


def calculate_material(data: MaterialCalculation) -> dict:
    issues = []
    gross = data.gross_weight_g
    gross_source = 'recorded'
    if data.net_weight_g is None:
        gross = data.quoted_gross_weight_g
        gross_source = 'quote'
    elif gross is None and all(v is not None for v in (data.thickness, data.width, data.pitch, data.density)):
        gross = data.thickness * data.width * data.pitch * data.density / Decimal(1000) / data.pieces_per_blank
        gross_source = 'specification'
    net = data.net_weight_g
    basis = 'measured' if net is not None else 'quote_utilization'
    if gross is None:
        issues.append('投料重缺失：有净重时请补规格/密度或投料重；无净重时请补报价投料重')
    if net is None:
        if data.utilization_pct is None:
            issues.append('无实测净重，请补报价材料利用率')
        elif gross is not None:
            net = gross * data.utilization_pct / Decimal(100)
    if gross is not None and net is not None and net > gross:
        issues.append('净重大于单件投料重，请核对规格和出件分配')
    if data.material_price is None:
        issues.append('材料单价待补充')
    if data.scrap_price is None:
        issues.append('废料单价待补充；明确无回收价值时填写 0')
    amount = None
    if not issues:
        amount = (gross * data.material_price - (gross-net) * data.scrap_price) / Decimal(1000)
        if amount < 0:
            issues.append('废料回收金额超过投料金额，请核对单价')
            amount = None
    return dict(amount=number(amount), gross_weight_g=number(gross), net_weight_g=number(net),
                net_weight_basis=basis, gross_weight_source=gross_source, issues=issues)


def quotation_material(data: MaterialCalculation) -> dict:
    """A quotation's own dimensional estimate becomes its quoted gross weight."""
    data = data.model_copy(deep=True)
    if data.quoted_gross_weight_g is None and all(v is not None for v in (data.thickness,data.width,data.pitch,data.density)):
        data.quoted_gross_weight_g = data.thickness*data.width*data.pitch*data.density/Decimal(1000)/data.pieces_per_blank
    return calculate_material(data)


def calculate_simple(data: SimpleCalculation) -> dict:
    material = calculate_material(data.material)
    issues = list(material['issues'])
    known = Decimal(material['amount'] or '0')
    surface = Decimal(0)
    surface_known = True
    charges = []
    if data.treatment_status == 'pending':
        issues.append('表面处理要求待确认')
        surface_known = False
    if data.treatment_status == 'required' and not data.treatments:
        issues.append('表面处理费用待补充')
        surface_known = False
    if data.treatment_status == 'none' and data.treatments:
        issues.append('零件无需表面处理，不能重复加入处理费用')
        surface_known = False
    seen = set()
    for charge in data.treatments:
        amount = None
        error = None
        if charge.item_key in seen:
            error = '同一表面处理重复计费'
        seen.add(charge.item_key)
        if not error:
            if charge.rate is None:
                error = '费率待补充'
            elif charge.method == 'piece':
                amount = charge.rate
            elif charge.method == 'batch':
                if charge.quantity is None:
                    error = '批次分摊数量待补充'
                else:
                    amount = charge.rate / charge.quantity
            elif material['net_weight_g'] is None:
                error = '计费净重待补充'
            else:
                amount = Decimal(material['net_weight_g']) / Decimal(1000) * charge.rate
        if not charge.source.strip():
            error = error or '收费依据待补充'
        if error:
            issues.append(f'{charge.name}：{error}')
            surface_known = False
            amount = None
        else:
            surface += amount
            known += amount
        charges.append(dict(item_key=charge.item_key, name=charge.name, amount=number(amount)))
    optional = []
    for category, entries in [('special_cost', data.special_costs), ('tooling_amortization', [data.tooling_amortization])]:
        for entry in entries:
            amount = None
            if entry.selected:
                if entry.amount is None or not entry.source.strip() or (category == 'special_cost' and not entry.name.strip()):
                    issues.append(f'{entry.name or ("模摊" if category == "tooling_amortization" else "特殊成本")}：金额/名称/依据待补充')
                else:
                    amount = entry.amount
                    known += amount
            optional.append(dict(category=category, name=entry.name, selected=entry.selected, amount=number(amount)))
    comparison = None
    if data.reference_price is not None:
        comparison_issues = []
        if issues:
            comparison_issues.append('本次简易成本尚有缺项')
        if data.comparison_basis == 'unknown':
            comparison_issues.append('请核对成本与售价的币种、单位和含税口径')
        difference = data.reference_price - known if not comparison_issues else None
        rate = difference / data.reference_price * Decimal(100) if difference is not None and data.reference_price > 0 else None
        if data.reference_price == 0:
            comparison_issues.append('参考售价为 0，不计算差额率')
        comparison = dict(reference_price=number(data.reference_price), basis=data.comparison_basis,
            difference=number(difference), difference_rate_pct=number(rate), issues=comparison_issues,
            scope='售价与简易成本差额，不代表完整利润')
    return dict(rule_version=RULE_VERSION, mode='basic', currency='CNY', unit='元/件', comparison=comparison,
                material=material, surface_amount=number(surface) if surface_known else None,
                treatments=charges, optional_costs=optional, known_subtotal=number(known),
                total=number(known) if not issues else None,
                completeness='incomplete' if issues else 'complete', issues=issues)
