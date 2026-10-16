import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.api.parts import _apply_part_filters
from app.main import app
from app.models.part import Part
from app.schemas.packaging import InventoryAdjustmentRequest
from app.schemas.warehouse import FinishedGoodsInventoryItem, FinishedGoodsInventoryReconcile, FinishedGoodsLedgerEntry, FinishedGoodsLocationUpdate, FinishedGoodsReviewResolve


def test_finished_goods_management_contract_is_exposed():
    paths = app.openapi()["paths"]
    assert paths["/api/v1/warehouse/finished-goods/{inventory_id}/location"]["patch"]
    assert paths["/api/v1/warehouse/finished-goods/{inventory_id}/adjust"]["post"]
    assert paths["/api/v1/warehouse/finished-goods/review/{row_id}/resolve"]["post"]
    assert paths["/api/v1/warehouse/finished-goods/{inventory_id}/ledger"]["get"]
    assert paths["/api/v1/warehouse/finished-goods/{inventory_id}/ledger/entry"]["post"]
    assert paths["/api/v1/warehouse/finished-goods/{inventory_id}/ledger/reconcile"]["post"]


def test_finished_goods_management_payloads_validate():
    assert FinishedGoodsLocationUpdate(location="A-01").location == "A-01"
    assert InventoryAdjustmentRequest(quantity=-2, reason="盘点差异").quantity == -2
    payload = FinishedGoodsReviewResolve(part_id=4455, stock_qty=12, location="B-02")
    assert payload.part_id == 4455
    assert payload.stock_qty == 12


def test_finished_goods_inventory_item_exposes_shipping_windows():
    item = FinishedGoodsInventoryItem(
        id=1, part_id=2, customer_part_no="C-001", part_name="零件", customer_name="客户",
        stock_qty=20, reserved_qty=3, available_qty=17,
        last_month_shipped_qty=4, last_3_month_shipped_qty=11,
        last_update_at="2026-09-28T00:00:00Z",
    )
    assert item.last_month_shipped_qty == 4
    assert item.last_3_month_shipped_qty == 11


def test_finished_goods_ledger_entry_accepts_income_and_expense():
    assert FinishedGoodsLedgerEntry(transaction_type="incoming", quantity=5, reason="生产入库").quantity == 5
    assert FinishedGoodsLedgerEntry(transaction_type="outgoing", quantity=2, reason="发货").transaction_type == "outgoing"
    historical = FinishedGoodsLedgerEntry(
        transaction_type="incoming", quantity=3, reason="补录", occurred_on="2026-09-29", affects_stock=False
    )
    assert historical.occurred_on.isoformat() == "2026-09-29"
    assert historical.affects_stock is False
    assert FinishedGoodsInventoryReconcile(physical_stock=18, reason="盘点").physical_stock == 18


@pytest.mark.asyncio
async def test_finished_goods_customer_part_no_search_matches_fragments(
    client: AsyncClient, db, lv1_headers
):
    candidate = (await db.execute(text("""
        SELECT p.customer_part_no
        FROM parts p
        JOIN finished_goods_inventory i ON i.part_id = p.id
        WHERE p.is_deleted = FALSE
          AND NULLIF(BTRIM(p.customer_part_no), '') IS NOT NULL
          AND LENGTH(BTRIM(p.customer_part_no)) >= 3
        ORDER BY p.id
        LIMIT 1
    """))).scalar_one()
    fragment = candidate.strip()[:3]

    response = await client.get(
        "/api/v1/warehouse/finished-goods",
        params={"customer_part_no": fragment, "page_size": 200},
        headers=lv1_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(fragment.lower() in (item["customer_part_no"] or "").lower() for item in payload["items"])


@pytest.mark.asyncio
async def test_parts_search_matches_canonical_customer_number_fragments(
    db,
):
    candidate = (await db.execute(text("""
        SELECT p.customer_part_no
        FROM parts p
        WHERE p.is_deleted = FALSE
          AND NULLIF(BTRIM(p.customer_part_no), '') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM part_customer_aliases a
              WHERE a.part_id = p.id AND a.is_active = TRUE
                AND a.data_quality_status = 'approved'
          )
        ORDER BY p.id
        LIMIT 1
    """))).scalar_one_or_none()
    if not candidate:
        pytest.skip("当前数据库没有仅使用规范客户件号的零件样本")
    fragment = candidate.strip()[:3]

    query = _apply_part_filters(
        select(Part.customer_part_no), fragment, None, None, None,
    )
    values = (await db.execute(query)).scalars().all()
    assert any(fragment.lower() in (value or "").lower() for value in values)
