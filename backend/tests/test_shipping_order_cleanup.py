from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.shipping_order_service import cleanup_drafts


def test_cleanup_cutoff_is_seven_days(monkeypatch):
    captured = {}

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [11, 12]

    class FakeSession:
        def __init__(self):
            self.added = []

        async def execute(self, query):
            captured["query"] = str(query)
            return FakeResult()

        def add(self, item):
            self.added.append(item)

    now = datetime(2026, 8, 22, 12, 0, 0)
    ids = __import__("asyncio").run(cleanup_drafts(FakeSession(), now=now, dry_run=True))
    assert ids == [11, 12]
    assert "shipping_orders" in captured["query"]
    assert "shipping_orders.status" in captured["query"]


def test_cleanup_writes_system_audit_before_delete():
    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [99]

    class FakeSession:
        def __init__(self):
            self.added = []
            self.executed = []

        async def execute(self, query):
            self.executed.append(str(query))
            return FakeResult()

        def add(self, item):
            self.added.append(item)

    session = FakeSession()
    ids = __import__("asyncio").run(cleanup_drafts(session, now=datetime(2026, 8, 22), dry_run=False))
    assert ids == [99]
    assert session.added[0].entity_type == "shipping_order_cleanup"
    assert "DELETE FROM shipping_orders" in session.executed[-1]
