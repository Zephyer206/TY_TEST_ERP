from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.shipping_order import ShippingLineCreate, ShippingOrderCreate
from app.services.shipping_order_service import shipment_totals


def test_formal_order_defaults_and_repeated_lines_are_valid():
    payload = ShippingOrderCreate(
        customer_id=4,
        po_no="PO-REPEAT-1",
        lines=[
            ShippingLineCreate(customer_part_no="A-1", part_name="零件 A", ordered_qty=10, planned_ship_date=date.today()),
            ShippingLineCreate(customer_part_no="A-1", part_name="零件 A", ordered_qty=20, planned_ship_date=date.today() + timedelta(days=1)),
        ],
    )
    assert payload.order_type == "formal"
    assert len(payload.lines) == 2
    assert payload.lines[0].customer_part_no == payload.lines[1].customer_part_no


def test_order_line_rejects_non_positive_quantity():
    with pytest.raises(ValidationError):
        ShippingLineCreate(customer_part_no="A-1", part_name="零件 A", ordered_qty=0, planned_ship_date=date.today())


def test_repeated_shipment_line_entries_are_aggregated_before_remainder_check():
    entries = [
        type("Line", (), {"order_line_id": 11, "qty": 6})(),
        type("Line", (), {"order_line_id": 11, "qty": 5})(),
        type("Line", (), {"order_line_id": 12, "qty": 2})(),
    ]
    assert shipment_totals(entries) == {11: 11, 12: 2}
