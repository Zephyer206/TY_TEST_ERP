"""Engineering linkage must never rewrite commercial quote values."""

from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException

from app.api import quote_groups
from app.api.quote_groups import _item_response, ensure_quote_group, sync_quote_group_press
from app.models.customer_inquiry import CustomerInquiry
from app.models.quote_group import QuoteGroup, QuoteGroupItem
from app.services.quote_press_service import press_metadata, sync_quote_presses


def part(part_no="L", **changes):
    values = dict(id=10, sequence=1, customer_part_no=part_no, part_name="支架", cavity_count=2,
                  press_tonnage=160, tooling_cost=Decimal("12000"), tooling_lead_time=30,
                  product_price=Decimal("2.85"), annual_usage=24000,
                  technical_snapshot={"key": "pair-1", "toolingCost": "12000", "pressTonnage": "160"})
    return QuoteGroupItem(**(values | changes))


def inquiry(**changes):
    values = dict(id=42, customer_id=7, technical_review="已完成", technical_data=[{
        "key": "pair-1", "customerPartNo": "L", "customerPartNo2": "R", "isLeftRightPair": True,
        "pressTonnageSource": "type", "pressTypeKey": "200-dual-axis", "pressTonnage": "200",
        "pressTypeLabel": "200T 双轴", "pressIsDualAxis": True,
        "toolingCost": "99999",  # An unrelated engineering estimate must not change the quote.
    }])
    return CustomerInquiry(**(values | changes))


def group(items=None, **changes):
    values = dict(id=3, inquiry_id=42, status="已报价", tooling_cost=Decimal("9600"),
                  material_unit_price=Decimal("12.5"), surface_treatment_fee=Decimal("0.2"),
                  profit_margin=Decimal("18"), items=items if items is not None else [part()])
    return QuoteGroup(**(values | changes))


def test_syncs_both_left_right_parts_without_changing_any_price_or_status():
    quote = group([part(), part("R", id=11, sequence=2)])
    original_prices = [(item.product_price, item.tooling_cost, item.annual_usage) for item in quote.items]
    changed = sync_quote_presses(quote, inquiry())
    assert changed == 2
    assert all(item.press_tonnage == 200 and item.technical_snapshot["pressTypeKey"] == "200-dual-axis" for item in quote.items)
    assert all(item.technical_snapshot["toolingCost"] == "12000" for item in quote.items)
    assert [(item.product_price, item.tooling_cost, item.annual_usage) for item in quote.items] == original_prices
    assert quote.tooling_cost == Decimal("9600") and quote.material_unit_price == Decimal("12.5")
    assert quote.surface_treatment_fee == Decimal("0.2") and quote.profit_margin == Decimal("18")
    assert quote.status == "已报价"
    updated_at = quote.updated_at
    assert sync_quote_presses(quote, inquiry()) == 0 and quote.updated_at == updated_at


@pytest.mark.parametrize("status", ["已提交审批", "已审批", "已定点"])
def test_locked_quote_snapshots_remain_unchanged(status):
    quote = group(status=status)
    original = deepcopy(quote.items[0].technical_snapshot)
    with pytest.raises(HTTPException) as exc:
        sync_quote_presses(quote, inquiry())
    assert exc.value.status_code == 409
    assert quote.items[0].technical_snapshot == original and quote.items[0].press_tonnage == 160


@pytest.mark.parametrize("status", ["待评审", "评审中", "待补充"])
def test_unapproved_inquiry_cannot_refresh_a_quote(status):
    with pytest.raises(HTTPException) as exc:
        sync_quote_presses(group(), inquiry(technical_review=status))
    assert exc.value.status_code == 409


def test_unmatched_later_part_does_not_partially_sync_earlier_parts():
    quote = group([part(), part("WRONG", id=11, sequence=2)])
    original = deepcopy(quote.items[0].technical_snapshot)
    with pytest.raises(HTTPException):
        sync_quote_presses(quote, inquiry())
    assert quote.items[0].press_tonnage == 160 and quote.items[0].technical_snapshot == original


def test_ambiguous_customer_part_number_does_not_guess_a_match():
    source = inquiry()
    source.technical_data = [dict(source.technical_data[0], key="one"), dict(source.technical_data[0], key="two")]
    with pytest.raises(HTTPException):
        sync_quote_presses(group(), source)


def test_stable_key_disambiguates_duplicate_part_numbers():
    source = inquiry()
    source.technical_data = [source.technical_data[0], dict(source.technical_data[0], key="other", pressTonnage="400")]
    quote = group()
    assert sync_quote_presses(quote, source) == 1 and quote.items[0].press_tonnage == 200


def test_manual_input_clears_previous_type_and_axis_metadata():
    quote = group()
    sync_quote_presses(quote, inquiry())
    source = inquiry()
    source.technical_data[0] = dict(source.technical_data[0], pressTonnage="250", pressTonnageSource="manual")
    sync_quote_presses(quote, source)
    snapshot = quote.items[0].technical_snapshot
    assert snapshot["pressTypeKey"] is None and snapshot["pressIsDualAxis"] is None
    assert snapshot["pressTonnageSource"] == "manual" and snapshot["pressMachineId"] is None


def test_legacy_tonnage_only_quote_stays_manual_without_assumed_axis_type():
    result = _item_response(part(press_tonnage=80, technical_snapshot={"pressTonnage": "80"}))
    data = result.model_dump()
    assert data["press_type_label"] == "80T" and data["press_tonnage_source"] == "manual"
    assert data["press_type_key"] is None and data["press_is_dual_axis"] is None
    assert "technical_snapshot" not in data


def test_new_quote_response_exposes_type_and_axis_fields():
    data = inquiry().technical_data[0]
    result = _item_response(part(press_tonnage=200, technical_snapshot=data)).model_dump()
    assert result["press_type_key"] == "200-dual-axis"
    assert result["press_type_label"] == "200T 双轴" and result["press_is_dual_axis"] is True
    assert result["press_tonnage_source"] == "type"


def test_sole_dual_axis_capacity_preserves_short_label_and_true_axis_metadata():
    metadata = press_metadata({"pressTypeKey": "300-dual-axis", "pressTypeLabel": "300T", "pressIsDualAxis": True}, 300)
    assert metadata["press_type_label"] == "300T" and metadata["press_is_dual_axis"] is True


@pytest.mark.asyncio
async def test_reapproval_refreshes_existing_group_without_recreating_or_repricing():
    quote = group()
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: quote)))
    result = await ensure_quote_group(db, inquiry(), user_id=9)
    assert result is quote and result.items[0].press_tonnage == 200
    assert result.items[0].product_price == Decimal("2.85") and result.status == "已报价"


@pytest.mark.asyncio
async def test_reapproval_retains_locked_group_snapshot():
    quote = group(status="已审批")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: quote)))
    await ensure_quote_group(db, inquiry(), user_id=9)
    assert quote.items[0].press_tonnage == 160


@pytest.mark.asyncio
async def test_sync_endpoint_commits_only_engineering_update(monkeypatch):
    quote = group()
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(unique=lambda: SimpleNamespace(first=lambda: quote)))
    db = SimpleNamespace(execute=AsyncMock(return_value=result), get=AsyncMock(return_value=inquiry()), commit=AsyncMock())
    monkeypatch.setattr(quote_groups, "_response", AsyncMock(return_value=quote))
    response = await sync_quote_group_press(3, db, SimpleNamespace(id=9, role_level=4))
    db.commit.assert_awaited_once()
    assert response.status == "已报价" and response.items[0].press_tonnage == 200


def test_sync_contract_and_press_fields_are_exposed():
    app = FastAPI()
    app.include_router(quote_groups.router)
    schema = app.openapi()
    assert "post" in schema["paths"]["/quote-groups/{group_id}/sync-press"]
    fields = schema["components"]["schemas"]["QuoteGroupItemResponse"]["properties"]
    assert {"press_type_key", "press_type_label", "press_is_dual_axis", "press_tonnage_source"} <= fields.keys()
