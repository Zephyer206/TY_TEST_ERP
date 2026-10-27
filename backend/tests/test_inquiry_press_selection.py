"""Press type selection, axis classification, compatibility and draft persistence."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException

from app.api import customer_inquiries
from app.api.customer_inquiries import TechnicalReviewInput, review_customer_inquiry
from app.api.machines import router as machines_router
from app.api.quote_groups import ensure_quote_group
from app.models.customer_inquiry import CustomerInquiry
from app.services.inquiry_technical_service import resolve_inquiry_presses
from app.services.press_type_service import classify_press, list_installed_press_types


def press(tonnage=200, model="200T（双)", **changes):
    return SimpleNamespace(**(dict(id=5, machine_no="P-005", name="冲床", machine_type=model,
                                  tonnage=tonnage, is_deleted=False) | changes))


def db_with_types(machines=None):
    rows = machines if machines is not None else [press(), press(160, "160T (双）"), press(200, "200T"), press(160, "160T")]
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))
    return SimpleNamespace(execute=AsyncMock(return_value=result), get=AsyncMock())


@pytest.mark.parametrize("model,dual", [
    ("200T", False), ("200T（双)", True), ("160T (双）", True),
    ("200T双轴", True), ("200T双轴（料架）", True), ("200T（双)料架", False), (None, False),
])
def test_classification_distinguishes_press_axes_from_dual_feeders(model, dual):
    kind = classify_press(press(model=model))
    assert kind.is_dual_axis is dual
    assert kind.label == ("200T 双轴" if dual else "200T")


@pytest.mark.asyncio
async def test_types_deduplicate_machines_and_keep_standard_and_dual_separate():
    db = db_with_types([press(), press(id=6), press(160, "160T (双）"), press(200, "200T"),
                        press(160, "160T"), press(300, "300T (双）"), press(400, "400T（双)")])
    options = await list_installed_press_types(db)
    assert [(option.key, option.label, option.machine_count) for option in options] == [
        ("160-standard", "160T", 1), ("160-dual-axis", "160T 双轴", 1),
        ("200-standard", "200T", 1), ("200-dual-axis", "200T 双轴", 2),
        ("300-dual-axis", "300T", 1), ("400-dual-axis", "400T", 1),
    ]
    assert "is_deleted" in str(db.execute.call_args.args[0])


@pytest.mark.asyncio
async def test_type_snapshot_is_authoritative_and_never_assigns_a_machine():
    original = {"partName": "支架", "pressTonnageSource": "type", "pressTypeKey": "200-dual-axis",
                "pressTonnage": "999", "pressIsDualAxis": False, "pressMachineId": 5}
    item, = await resolve_inquiry_presses(db_with_types(), [original], completing=True)
    assert item["pressTonnage"] == "200"
    assert item["pressTypeLabel"] == "200T 双轴"
    assert item["pressIsDualAxis"] is True and item["pressMachineId"] is None
    assert original["pressTonnage"] == "999"


@pytest.mark.asyncio
async def test_manual_exception_clears_type_and_legacy_machine_references():
    db = db_with_types()
    item, = await resolve_inquiry_presses(db, [{"pressTonnageSource": "manual", "pressTonnage": "250",
                                             "pressTypeKey": "200-dual-axis", "pressMachineId": 5}])
    assert item["pressTypeKey"] is None and item["pressMachineId"] is None
    assert item["pressIsDualAxis"] is None and item["pressTonnage"] == "250"
    db.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["0", "-10", "1.5", "abc", "NaN", "Infinity", "2147483648", True])
async def test_invalid_manual_tonnages_are_rejected(value):
    with pytest.raises(HTTPException) as exc:
        await resolve_inquiry_presses(SimpleNamespace(), [{"pressTonnageSource": "manual", "pressTonnage": value}])
    assert exc.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["999-dual-axis", "200-single-machine", ["200-dual-axis"], 5])
async def test_unavailable_or_invalid_types_are_rejected(key):
    with pytest.raises(HTTPException) as exc:
        await resolve_inquiry_presses(db_with_types(), [{"pressTonnageSource": "type", "pressTypeKey": key}])
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_legacy_machine_selection_converts_to_type_without_binding():
    db = db_with_types()
    db.get.return_value = press()
    item, = await resolve_inquiry_presses(db, [{"pressTonnageSource": "machine", "pressMachineId": 5}])
    assert item["pressTonnageSource"] == "type" and item["pressTypeKey"] == "200-dual-axis"
    assert item["pressMachineId"] is None


@pytest.mark.asyncio
async def test_legacy_handwritten_tonnage_is_preserved():
    item, = await resolve_inquiry_presses(SimpleNamespace(), [{"pressTonnage": "160", "customerPartNo": "OLD"}])
    assert item["pressTonnageSource"] == "manual" and item["pressTonnage"] == "160"


@pytest.mark.asyncio
async def test_draft_can_be_incomplete_but_review_requires_a_type_or_tonnage():
    original = {"partName": "支架", "pressTonnageSource": "type"}
    item, = await resolve_inquiry_presses(SimpleNamespace(), [original])
    assert item["pressTonnage"] == ""
    with pytest.raises(HTTPException):
        await resolve_inquiry_presses(SimpleNamespace(), [original], completing=True)


@pytest.mark.asyncio
async def test_tonnage_cannot_bypass_type_selection_without_manual_mode():
    with pytest.raises(HTTPException):
        await resolve_inquiry_presses(SimpleNamespace(), [{"pressTonnageSource": "type", "pressTonnage": "200"}])


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["external", {}, [], 1])
async def test_invalid_source_returns_validation_error(source):
    with pytest.raises(HTTPException) as exc:
        await resolve_inquiry_presses(SimpleNamespace(), [{"pressTonnageSource": source}])
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_draft_save_commits_without_changing_review_status(monkeypatch):
    inquiry = CustomerInquiry(id=42, customer_id=7, technical_review="待评审")
    db = db_with_types()
    db.get.return_value = inquiry
    db.commit, db.refresh = AsyncMock(), AsyncMock()
    monkeypatch.setattr(customer_inquiries, "_load_response", AsyncMock(return_value=inquiry))
    await review_customer_inquiry(42, TechnicalReviewInput(technical_data=[{
        "pressTypeKey": "160-dual-axis", "pressTonnageSource": "type", "partName": "支架",
    }]), db, SimpleNamespace(id=9, role_level=4))
    assert inquiry.technical_review == "待评审" and inquiry.technical_data[0]["pressTypeLabel"] == "160T 双轴"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_type_does_not_mutate_inquiry_or_commit():
    inquiry = CustomerInquiry(id=42, customer_id=7, technical_review="待评审", technical_data=[{"pressTonnage": "160"}])
    db = db_with_types()
    db.get.return_value, db.commit = inquiry, AsyncMock()
    with pytest.raises(HTTPException):
        await review_customer_inquiry(42, TechnicalReviewInput(status="已完成", technical_data=[{
            "pressTonnageSource": "type", "pressTypeKey": "999-dual-axis",
        }]), db, SimpleNamespace(id=9, role_level=4))
    assert inquiry.technical_review == "待评审" and inquiry.technical_data == [{"pressTonnage": "160"}]
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_return_for_supplement_allows_incomplete_technical_data(monkeypatch):
    inquiry = CustomerInquiry(id=42, customer_id=7, technical_review="待评审")
    db = SimpleNamespace(get=AsyncMock(return_value=inquiry), commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(customer_inquiries, "_load_response", AsyncMock(return_value=inquiry))
    await review_customer_inquiry(42, TechnicalReviewInput(status="待补充", technical_data=[{}]), db, SimpleNamespace(id=9, role_level=4))
    assert inquiry.technical_review == "待补充" and inquiry.technical_data[0]["pressTonnage"] == ""


@pytest.mark.asyncio
async def test_type_and_axes_survive_left_right_quote_snapshots():
    items = await resolve_inquiry_presses(db_with_types(), [{
        "key": "pair", "customerPartNo": "L", "customerPartNo2": "R", "isLeftRightPair": True,
        "pressTypeKey": "200-dual-axis", "pressTonnageSource": "type", "cavityCount": "2",
    }], completing=True)
    inquiry = CustomerInquiry(id=42, customer_id=7, project_name="左右件", technical_data=items)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)), add=lambda value: None, flush=AsyncMock())
    group = await ensure_quote_group(db, inquiry, user_id=9)
    assert len(group.items) == 2
    assert all(item.press_tonnage == 200 and item.technical_snapshot["pressIsDualAxis"] for item in group.items)
    assert all(item.technical_snapshot["pressMachineId"] is None for item in group.items)


def test_contract_exposes_type_catalog_before_numeric_machine_route():
    app = FastAPI()
    app.include_router(customer_inquiries.router)
    app.include_router(machines_router)
    paths = app.openapi()["paths"]
    assert "get" in paths["/machines/press-types"]
    contract = app.openapi()["components"]["schemas"]["TechnicalReviewInput"]
    assert "status" not in contract.get("required", [])
    assert "pressTypeKey" in contract["properties"]["technical_data"]["description"]
