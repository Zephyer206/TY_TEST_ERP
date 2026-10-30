from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.costing import MaterialCalculation, SimpleCalculation, OptionalCost, SurfaceTreatment
from app.services.costing_calculator import calculate_material, calculate_simple


def material(**overrides):
    return MaterialCalculation(**dict(gross_weight_g=20, net_weight_g=12,
        material_price=10, scrap_price=2, **overrides))


def test_actual_and_quotation_utilization_have_the_same_cost():
    actual = calculate_material(material())
    quoted = calculate_material(MaterialCalculation(quoted_gross_weight_g=20,
        utilization_pct=60, material_price=10, scrap_price=2))
    assert actual['amount'] == quoted['amount'] == '0.184000'
    assert quoted['net_weight_basis'] == 'quote_utilization'
    assert quoted['net_weight_g'] == '12.000000'


def test_missing_prices_and_utilization_do_not_mean_zero_or_full_utilization():
    result = calculate_material(MaterialCalculation(quoted_gross_weight_g=20, material_price=10))
    assert result['amount'] is None
    assert any('利用率' in x for x in result['issues'])
    assert any('废料单价' in x for x in result['issues'])


@pytest.mark.parametrize('special,mold,total', [(False,False,'0.184000'),(True,False,'0.284000'),
    (False,True,'0.384000'),(True,True,'0.484000')])
def test_optional_costs_are_independent(special, mold, total):
    result = calculate_simple(SimpleCalculation(material=material(), treatment_status='none',
        special_costs=[OptionalCost(selected=special, name='特殊要求', amount='.1', source='测试依据')],
        tooling_amortization=OptionalCost(selected=mold, amount='.2', source='合同单件模摊')))
    assert result['total'] == total


def test_selected_unknown_cost_blocks_only_the_selected_scope():
    data = SimpleCalculation(material=material(), treatment_status='none', tooling_amortization=OptionalCost(selected=True))
    assert calculate_simple(data)['total'] is None
    data.tooling_amortization.selected = False
    assert calculate_simple(data)['total'] == '0.184000'


def test_invalid_physical_inputs_and_surface_states():
    assert calculate_material(MaterialCalculation(gross_weight_g=10, net_weight_g=12, material_price=10, scrap_price=2))['amount'] is None
    with pytest.raises(ValidationError):
        MaterialCalculation(utilization_pct=101)
    with pytest.raises(ValidationError):
        MaterialCalculation(material_price='NaN')
    with pytest.raises(ValidationError):
        SurfaceTreatment(status='required')


def test_specification_weight_and_confirmed_allocation():
    result = calculate_material(MaterialCalculation(thickness='.4', width=68, pitch=73, density='7.93',
        pieces_per_blank=2, net_weight_g=3, material_price=10, scrap_price=0))
    assert result['gross_weight_g'] == '7.872904'


def test_reference_comparison_requires_known_scope_and_tax_basis():
    data=SimpleCalculation(material=material(),treatment_status='none',reference_price=1)
    assert calculate_simple(data)['comparison']['difference'] is None
    data.comparison_basis='both_tax_excluded'
    result=calculate_simple(data)
    assert result['comparison']['difference']=='0.816000'
    assert result['comparison']['difference_rate_pct']=='81.600000'
    data.reference_price=Decimal('0')
    assert calculate_simple(data)['comparison']['difference_rate_pct'] is None


def test_malformed_quotation_rule_snapshot_is_rejected_before_calculation():
    from app.schemas.costing import QuotationPreview
    with pytest.raises(ValidationError):
        QuotationPreview(material={}, surface_rule_snapshot={'rate': 'bad'})
