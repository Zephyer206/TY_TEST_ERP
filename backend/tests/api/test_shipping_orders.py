import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.shipping_orders import _assert_draft_owner, contract_router, router
from app.models.shipping_order import ShippingOrder
from app.schemas.shipping_order import LogisticsInput, ShippingLineCreate, ShipmentConfirmRequest, ShipmentLineInput


def test_shipping_contract_paths_are_exposed():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(contract_router, prefix="/api/v1")
    # FastAPI 0.1xx exposes included routers lazily, so ``app.routes`` may
    # contain private ``_IncludedRouter`` wrappers without a ``path`` field.
    # OpenAPI is the public contract and remains stable across both behaviors.
    paths = set(app.openapi()["paths"])
    assert "/api/v1/shipping-orders/{order_id}/shipments/confirm" in paths
    assert "/api/v1/shipping-order-lines/{line_id}/label-confirm" in paths
    assert "/api/v1/shipping-shipments/{shipment_id}/logistics" in paths


def test_logistics_requires_carrier_or_tracking_number():
    with pytest.raises(ValueError):
        LogisticsInput()
    assert LogisticsInput(carrier_name="顺丰").carrier_name == "顺丰"
    assert LogisticsInput(tracking_no="SF-1").tracking_no == "SF-1"


def test_shipment_payload_supports_multiple_logistics_rows():
    payload = ShipmentConfirmRequest(
        lines=[ShipmentLineInput(order_line_id=1, qty=10)],
        logistics=[LogisticsInput(carrier_name="顺丰"), LogisticsInput(carrier_name="京东物流", tracking_no="JD-2")],
    )
    assert len(payload.logistics) == 2


def test_submitted_order_visibility_is_not_creator_restricted():
    order = ShippingOrder(id=7, created_by=1, status="pending")
    other_user = type("User", (), {"id": 2})()
    _assert_draft_owner(order, other_user)


def test_draft_visibility_is_creator_restricted():
    order = ShippingOrder(id=8, created_by=1, status="draft")
    other_user = type("User", (), {"id": 2})()
    with pytest.raises(Exception) as exc:
        _assert_draft_owner(order, other_user)
    assert getattr(exc.value, "status_code", None) == 403
