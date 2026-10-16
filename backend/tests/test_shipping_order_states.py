from types import SimpleNamespace

from app.services.shipping_order_service import add_cancellation_consent, derive_line_status, derive_order_status, promote_formal_lines_from_qualified_inventory, remaining_qty, shipped_qty


def line(**overrides):
    value = {
        "ordered_qty": 100,
        "cancelled_qty": 0,
        "shipment_lines": [],
        "label_confirmation": None,
    }
    value.update(overrides)
    return SimpleNamespace(**value)


def test_partial_shipment_quantity_arithmetic():
    item = line(shipment_lines=[SimpleNamespace(qty=60)])
    assert shipped_qty(item) == 60
    assert remaining_qty(item) == 40
    assert derive_line_status(item) == "partially_shipped"


def test_ready_to_ship_requires_label_confirmation():
    item = line(label_confirmation=SimpleNamespace(id=1))
    assert derive_line_status(item) == "ready_to_ship"


def test_remaining_cancel_after_partial_shipment_is_terminal():
    item = line(cancelled_qty=40, shipment_lines=[SimpleNamespace(qty=60)])
    assert remaining_qty(item) == 0
    assert derive_line_status(item) == "partially_shipped_remaining_cancelled"


def test_order_status_completed_with_cancellation():
    shipped = line(ordered_qty=10, shipment_lines=[SimpleNamespace(qty=10)])
    cancelled = line(ordered_qty=10, cancelled_qty=10)
    order = SimpleNamespace(status="pending", lines=[shipped, cancelled])
    assert derive_order_status(order) == "completed_with_cancellation"


def test_two_party_cancellation_completes_only_after_both_confirmations():
    import asyncio

    class Session:
        def __init__(self):
            self.items = []

        def add(self, item):
            self.items.append(item)

        async def flush(self):
            return None

    line_obj = line(ordered_qty=10, label_confirmation=SimpleNamespace(id=1))
    line_obj.shipment_lines = []
    consent = SimpleNamespace(
        business_confirmed_by=2,
        business_confirmed_at=None,
        label_confirmed_by=None,
        label_confirmed_at=None,
        cancel_qty=10,
        reason="客户取消",
        status="pending",
        completed_at=None,
        line=line_obj,
        id=1,
    )
    business = SimpleNamespace(id=3, dept="sales", position="业务")
    label = SimpleNamespace(id=4, username="label-user", dept="warehouse", position="标签")
    session = Session()
    asyncio.run(add_cancellation_consent(session, consent, label))
    assert consent.status == "completed"
    assert line_obj.cancelled_qty == 10


def test_qualified_inventory_hook_promotes_formal_lines_without_inventory_mutation():
    import asyncio

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return self.rows

    class Session:
        def __init__(self, rows):
            self.rows = rows
            self.items = []

        async def execute(self, _query):
            return Result(self.rows)

        def add(self, item):
            self.items.append(item)

        async def flush(self):
            return None

    order = SimpleNamespace(order_type="formal", status="pending")
    line_obj = line(ordered_qty=10, order=order, id=9)
    user = SimpleNamespace(id=5, username="inventory-hook")
    session = Session([line_obj])
    promoted = asyncio.run(promote_formal_lines_from_qualified_inventory(session, [9], user, "FG-REF-1"))
    assert promoted == [line_obj]
    assert line_obj.status == "ready_to_ship"
    assert len(session.items) == 2  # label confirmation + audit entry
