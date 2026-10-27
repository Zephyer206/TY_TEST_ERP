"""Queue ownership, workflow transitions, date boundaries and API contract."""

from datetime import date, datetime, timezone
from types import SimpleNamespace as Record

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.api.workbench import router
from app.database import get_db
from app.schemas.workbench import WorkbenchTask
from app.services.workbench_service import build_page, plan_tasks, role_queues, shipping_tasks


def user(**changes):
    return Record(**(dict(id=7, role_level=2, dept="sales", position="业务", real_name="业务用户", username="sales") | changes))


def plan(**changes):
    return Record(**(dict(id=25, created_by=7, status="planned", machine_id=None, material_status="pending",
                        total_qty=100, due_date=datetime(2026, 10, 17), is_urgent=False,
                        created_at=None, updated_at=None) | changes))


def line(**changes):
    return Record(**(dict(id=10, ordered_qty=20, cancelled_qty=0, shipment_lines=[], label_confirmation=None,
                        customer_part_no_snapshot="P-10", part_name_snapshot="垫片", planned_ship_date=date(2026, 10, 17),
                        cancellation_consents=[]) | changes))


def order(**changes):
    return Record(**(dict(id=4, order_no="SO-4", status="pending", created_by=7, po_no="PO-4",
                        last_modified_at=None, created_at=None, lines=[line()]) | changes))


def test_creator_is_tracking_owner_not_production_assignee():
    actor = user()
    tasks = plan_tasks(plan(), None, None, actor, role_queues(actor))
    assert [(t.scope, t.title) for t in tasks] == [("created", "待资材确认")]
    assert tasks[0].route == "/production?plan_id=25"


def test_production_moves_between_role_queues_and_leaves_after_scheduling():
    material_user = user(dept="materials", position="资材")
    scheduler = user(id=8, dept="prod", position="生产组长")
    assert any(t.scope == "team" for t in plan_tasks(plan(), None, None, material_user, role_queues(material_user)))
    assert not plan_tasks(plan(), None, None, scheduler, role_queues(scheduler))
    ready = plan(material_status="ready")
    assert not [t for t in plan_tasks(ready, None, None, material_user, role_queues(material_user)) if t.scope == "team"]
    task = plan_tasks(ready, None, None, scheduler, role_queues(scheduler))[0]
    assert task.title == "待排产" and task.route.endswith("scheduling?plan_id=25")
    assert not plan_tasks(plan(status="queued", machine_id=5), None, None, scheduler, role_queues(scheduler))
    assert not plan_tasks(plan(status="cancelled"), None, None, material_user, role_queues(material_user))


@pytest.mark.parametrize("dept,level,expected", [("prod", 1, set()), ("warehouse", 1, {"label", "shipping"}),
                                               ("engineering", 2, set()), ("prod", 2, {"scheduling"}),
                                               ("admin", 4, {"materials", "scheduling", "label", "shipping"})])
def test_role_queue_boundaries(dept, level, expected):
    assert role_queues(user(dept=dept, role_level=level, position="员工")) == expected


def test_private_drafts_do_not_enter_shared_queue():
    actor = user()
    assert shipping_tasks(order(status="draft", created_by=8), None, actor, {"shipping", "label"}) == []
    tasks = shipping_tasks(order(status="draft"), None, actor, set())
    assert len(tasks) == 1 and tasks[0].scope == "mine" and tasks[0].due_date is None


def test_shipping_transitions_and_terminal_lines():
    warehouse = user(id=9, dept="warehouse", role_level=1)
    queues = role_queues(warehouse)
    assert shipping_tasks(order(), None, warehouse, queues)[0].title == "确认标签"
    ready = line(label_confirmation=Record(id=1))
    assert shipping_tasks(order(lines=[ready]), None, warehouse, queues)[0].title == "确认发货"
    assert shipping_tasks(order(lines=[line(shipment_lines=[Record(qty=20)])]), None, warehouse, queues) == []
    assert shipping_tasks(order(lines=[line(cancelled_qty=20)]), None, warehouse, queues) == []


def test_pending_cancellation_blocks_dispatch_and_keeps_responsibilities_separate():
    consent = Record(id=6, status="pending", business_confirmed_by=None, label_confirmed_by=None)
    pending_order = order(lines=[line(label_confirmation=Record(id=1), cancellation_consents=[consent])])
    sales_tasks = shipping_tasks(pending_order, None, user(), set())
    assert [t.title for t in sales_tasks if t.scope == "mine"] == ["确认取消申请"]
    warehouse = user(id=9, dept="warehouse", role_level=1)
    tasks = shipping_tasks(pending_order, None, warehouse, role_queues(warehouse))
    assert [t.title for t in tasks] == ["确认取消申请"]
    consent.label_confirmed_by = 9
    assert shipping_tasks(pending_order, None, warehouse, role_queues(warehouse)) == []


def task(key, **changes):
    return WorkbenchTask(**(dict(key=key, scope="team", module="shipping", document_no=f"SO-{key}",
                                title="确认发货", summary="垫片", customer="客户甲", role="仓库",
                                due_date=date(2026, 10, 17), route="/shipping-orders/4") | changes))


def test_business_day_counts_filters_and_pagination_are_consistent():
    # At 17:00 UTC it is already the following business day in Shanghai.
    tasks = [task("today"), task("late", due_date=date(2026, 10, 16)), task("none", due_date=None),
             task("personal", scope="mine"), task("other", module="production", summary="其他零件")]
    options = dict(acceptance_mode=True, scope="team", now=datetime(2026, 10, 16, 17, tzinfo=timezone.utc))
    page = build_page(tasks, user(), **options, module="shipping", search="客户甲", page_size=2)
    assert page.today == date(2026, 10, 17)
    assert page.counts.mine == 1 and page.counts.team == 3
    assert page.stats.pending == 3 and page.stats.today == 1 and page.stats.overdue == 1
    assert page.total == 3 and [t.key for t in page.items] == ["late", "today"]
    assert build_page(tasks, user(), **options, due="undated").items[0].key == "none"
    assert build_page(tasks, user(), **options, due="overdue").total == 1
    assert build_page(tasks, user(), **options, search="not-found").total == 0
    assert build_page(tasks, user(), **options, page=999, page_size=2).page == 2


@pytest.mark.asyncio
async def test_api_uses_authenticated_identity_and_validates_query(monkeypatch):
    from app.api import workbench
    received = []

    async def load(_db, actor, company="tianyue"):
        received.append(actor.id)
        return [task("one", scope="mine")]

    async def fake_db():
        yield object()

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user] = lambda: user()
    test_app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(workbench, "load_tasks", load)
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/workbench?scope=mine&user_id=999")
        assert response.status_code == 200
        assert response.json()["identity"]["id"] == 7 and received == [7]
        assert response.json()["items"][0]["key"] == "one"
        for query in ("scope=all", "page=0", "page_size=1000", "due=invalid"):
            assert (await client.get(f"/api/v1/workbench?{query}")).status_code == 422
