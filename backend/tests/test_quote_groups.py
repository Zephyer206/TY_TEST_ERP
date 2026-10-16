"""Contract and persistence-shaping tests for quotation groups."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.api.quote_groups import assert_quote_group_editable, ensure_quote_group, router
from app.models.customer_inquiry import CustomerInquiry
from app.models.quote_group import QuoteGroup
from app.schemas.quote_group import QuoteGroupUpdate


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    async def execute(self, _statement):
        return _ScalarResult(self.existing)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


def test_quote_group_contract_paths_are_exposed():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    paths = set(app.openapi()["paths"])
    assert "/api/v1/quote-groups" in paths
    assert "/api/v1/quote-groups/{group_id}" in paths
    assert "get" in app.openapi()["paths"]["/api/v1/quote-groups"]
    assert "post" in app.openapi()["paths"]["/api/v1/quote-groups"]
    assert "patch" in app.openapi()["paths"]["/api/v1/quote-groups/{group_id}"]


@pytest.mark.asyncio
async def test_ensure_quote_group_expands_left_right_pair_into_two_items():
    inquiry = CustomerInquiry(
        id=42,
        customer_id=7,
        project_name="左右件项目",
        technical_data=[
            {
                "key": "pair-1",
                "customerPartNo": "L-001",
                "customerPartNo2": "R-001",
                "partName": "支架",
                "isLeftRightPair": True,
                "material": "SUS301",
                "thickness": "0.8",
                "cavityCount": "2",
            }
        ],
    )
    db = _FakeDb()

    group = await ensure_quote_group(db, inquiry, user_id=9)

    assert db.added == [group]
    assert len(group.items) == 2
    assert [item.customer_part_no for item in group.items] == ["L-001", "R-001"]
    assert all(item.pair_key == "pair-1" for item in group.items)
    assert group.material_name == "SUS301"


@pytest.mark.asyncio
async def test_ensure_quote_group_is_idempotent_for_existing_inquiry():
    existing = SimpleNamespace(id=3)
    inquiry = CustomerInquiry(id=42, customer_id=7, project_name="已存在", technical_data=[])
    db = _FakeDb(existing=existing)

    result = await ensure_quote_group(db, inquiry, user_id=9)

    assert result is existing
    assert db.added == []


def test_locked_quote_group_rejects_updates_with_conflict():
    group = QuoteGroup(status="已定点")

    with pytest.raises(Exception) as exc:
        assert_quote_group_editable(group)

    assert getattr(exc.value, "status_code", None) == 409


def test_quote_group_update_contract_carries_group_and_item_values():
    payload = QuoteGroupUpdate(
        quote_path="直接开量产模具",
        tooling_cost=15000,
        material_unit_price=12.5,
        items=[{"product_price": 2.85, "annual_usage": 24000}],
    )

    assert payload.quote_path == "直接开量产模具"
    assert payload.items[0].product_price == Decimal("2.85")
    assert payload.items[0].annual_usage == 24000
