"""Ownership, authorization and stale-task acceptance on an isolated SQLite DB."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.api.workbench import AssignmentRequest, AssignRequest, effective_actor, router
from app.database import Base, get_db
from app.models.user import User
from app.models.production import ProductionPlan
from app.models.workbench_assignment import WorkbenchAssignment, WorkbenchAssignmentEvent
from app.schemas.workbench import WorkbenchTask
from app.services.workbench_assignment_service import apply_assignments, can_receive_task, change_assignment, eligible_assignees
from app.services.workbench_service import build_page


@pytest_asyncio.fixture
async def isolated_assignments(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workbench-ownership.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=[
            User.__table__, ProductionPlan.__table__, WorkbenchAssignment.__table__, WorkbenchAssignmentEvent.__table__,
        ]))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all([
            User(id=1, username="wb-warehouse-a", password="test-only", real_name="仓库甲", dept="warehouse", role_level=1, position="收发员"),
            User(id=2, username="wb-warehouse-b", password="test-only", real_name="仓库乙", dept="warehouse", role_level=1, position="收发员"),
            User(id=3, username="wb-manager", password="test-only", real_name="仓库主管", dept="warehouse", role_level=2, position="仓库主管"),
            User(id=4, username="wb-sales", password="test-only", real_name="业务甲", dept="sales", role_level=2, position="业务员"),
            User(id=5, username="wb-admin", password="test-only", real_name="管理员", dept="admin", role_level=4, position="系统管理员"),
        ])
        await session.commit()
    yield factory
    await engine.dispose()


def source(revision="label:1", company=None):
    return WorkbenchTask(key="line:1:label", scope="team", module="shipping", document_no="SO-WB-1",
                         title="确认标签", summary="测试任务", role="标签", route="/shipping-orders/1",
                         source_revision=revision, company=company)


def loader(task=None):
    task = task or source()

    async def load(_db, user, company="tianyue"):
        return [task] if user.dept == "warehouse" or user.role_level >= 4 else []
    return load


def request(version=0, revision="label:1", **changes):
    return AssignmentRequest(task_key="line:1:label", source_revision=revision, expected_version=version, **changes)


@pytest.mark.asyncio
async def test_claim_enters_mine_and_release_preserves_team_and_audit(isolated_assignments):
    async with isolated_assignments() as db:
        user = await db.get(User, 1)
        claimed = await change_assignment(db, user, request(), "claim", loader())
        assert claimed["version"] == 1 and claimed["assignment_state"] == "claimed"
        tasks = await apply_assignments(db, [source()], user)
        assert [item.scope for item in tasks] == ["team", "mine"]
        assert all(item.assignee_id == user.id and item.can_release and not item.can_claim for item in tasks)
        page = build_page(tasks, user, acceptance_mode=False)
        assert page.counts.mine == 1 and page.counts.team == 1
        released = await change_assignment(db, user, request(1), "release", loader())
        assert released["version"] == 2 and released["assignee_id"] is None
        tasks = await apply_assignments(db, [source()], user)
        assert len(tasks) == 1 and tasks[0].scope == "team" and tasks[0].can_claim
        events = (await db.execute(select(WorkbenchAssignmentEvent).order_by(WorkbenchAssignmentEvent.version))).scalars().all()
        assert [(item.action, item.version, item.actor_id) for item in events] == [("claim", 1, 1), ("release", 2, 1)]


@pytest.mark.asyncio
async def test_source_lock_refreshes_cached_completed_plan_before_claim(isolated_assignments):
    async with isolated_assignments() as db:
        db.add(ProductionPlan(id=77, status="planned", material_status="pending", created_by=1))
        await db.commit()
        user = await db.get(User, 1)
        cached = await db.get(ProductionPlan, 77)
        reads = 0

        async def changing_source(_db, _user, company="tianyue"):
            nonlocal reads
            reads += 1
            plan = await _db.get(ProductionPlan, 77)
            if reads == 1:
                async with isolated_assignments() as other:
                    await other.execute(update(ProductionPlan).where(ProductionPlan.id == 77).values(status="completed"))
                    await other.commit()
            if plan.status == "completed":
                return []
            return [source().model_copy(update={"source_type": "production_plan", "source_id": "77"})]

        with pytest.raises(HTTPException) as retired:
            await change_assignment(db, user, request(), "claim", changing_source)
        assert retired.value.status_code == 404
        assert cached.status == "completed" and reads == 2
        assert not (await db.execute(select(WorkbenchAssignment))).scalars().all()


@pytest.mark.asyncio
async def test_assignment_overlay_refreshes_cached_assignment_after_release(isolated_assignments):
    async with isolated_assignments() as db:
        user = await db.get(User, 1)
        await change_assignment(db, user, request(), "claim", loader())
        held = (await db.execute(select(WorkbenchAssignment))).scalar_one()
        assert held.assignee_id == 1
        await change_assignment(db, user, request(1), "release", loader())
        tasks = await apply_assignments(db, [source()], user)
        assert len(tasks) == 1 and tasks[0].assignee_id is None and tasks[0].assignment_version == 2
        assert held.assignee_id is None and held.version == 2


@pytest.mark.asyncio
async def test_cross_role_and_completed_tasks_cannot_claim(isolated_assignments):
    async with isolated_assignments() as db:
        for user_id, task_loader in [(4, loader()), (1, lambda *_args, **_kwargs: None)]:
            user = await db.get(User, user_id)
            if user_id == 1:
                async def completed(_db, _user, company="tianyue"):
                    return []
                task_loader = completed
            with pytest.raises(HTTPException) as error:
                await change_assignment(db, user, request(), "claim", task_loader)
            assert error.value.status_code == 404
        assert not (await db.execute(select(WorkbenchAssignment))).scalars().all()


@pytest.mark.asyncio
async def test_revision_version_and_other_owner_are_guarded(isolated_assignments):
    async with isolated_assignments() as db:
        user = await db.get(User, 1)
        with pytest.raises(HTTPException) as stale:
            await change_assignment(db, user, request(revision="label:0"), "claim", loader())
        assert stale.value.status_code == 409
        await change_assignment(db, user, request(), "claim", loader())
        other = await db.get(User, 2)
        with pytest.raises(HTTPException) as version:
            await change_assignment(db, other, request(), "claim", loader())
        assert version.value.status_code == 409
        with pytest.raises(HTTPException) as owner:
            await change_assignment(db, other, request(1), "release", loader())
        assert owner.value.status_code == 403
        with pytest.raises(HTTPException) as owned:
            await change_assignment(db, other, request(1), "claim", loader())
        assert owned.value.status_code == 409


@pytest.mark.asyncio
async def test_assignment_validates_manager_and_target_source_eligibility(isolated_assignments):
    async with isolated_assignments() as db:
        user, manager = await db.get(User, 1), await db.get(User, 3)
        mutation = AssignRequest(**request().model_dump(), assignee_id=2)
        with pytest.raises(HTTPException) as forbidden:
            await change_assignment(db, user, mutation, "assign", loader())
        assert forbidden.value.status_code == 403
        invalid_target = mutation.model_copy(update={"assignee_id": 4})
        with pytest.raises(HTTPException) as target:
            await change_assignment(db, manager, invalid_target, "assign", loader())
        assert target.value.status_code == 403
        options_source = source().model_copy(update={"source_type": "shipping_order", "step_key": "label"})
        candidates = await eligible_assignees(db, manager, source().key, "tianyue", loader(options_source))
        assert {item["id"] for item in candidates} == {1, 2, 3}
        assigned = await change_assignment(db, manager, mutation, "assign", loader())
        assert assigned["assignee_id"] == 2 and assigned["assignment_state"] == "assigned"
        target_user = await db.get(User, 2)
        assert [item.scope for item in await apply_assignments(db, [source()], target_user)] == ["team", "mine"]


@pytest.mark.asyncio
async def test_assignee_options_load_source_once_for_all_candidate_users(isolated_assignments):
    task = source().model_copy(update={"source_type": "shipping_order", "step_key": "label"})
    calls = []

    async def load_once(_db, user, company="tianyue"):
        calls.append((user.id, company))
        assert len(calls) == 1, "Options must not load every candidate's full workbench."
        return [task]

    async with isolated_assignments() as db:
        manager = await db.get(User, 3)
        candidates = await eligible_assignees(db, manager, task.key, "tianyue", load_once)
        assert {item["id"] for item in candidates} == {1, 2, 3}
        assert calls == [(manager.id, "tianyue")]


@pytest.mark.parametrize("source_type,step,dept,level,position,expected", [
    ("production_plan", "materials", "materials", 2, "资材", True),
    ("production_plan", "materials", "prod", 2, "生产主管", False),
    ("production_plan", "scheduling", "prod", 1, "操作工", False),
    ("production_plan", "scheduling", "prod", 2, "生产主管", True),
    ("production_plan", "production_progress", "admin", 4, "系统管理员", False),
    ("shipping_order", "label", "warehouse", 1, "收发员", True),
    ("shipping_order", "cancel_label", "warehouse", 1, "收发员", True),
    ("shipping_order", "shipping", "sales", 2, "业务员", False),
    ("shipping_order", "cancel_business", "sales", 2, "业务员", False),
    ("customer_inquiry", "technical_review", "engineering", 1, "工程师", False),
    ("customer_inquiry", "technical_review", "engineering", 2, "工程师", True),
    ("customer_inquiry", "technical_review", "boss", 3, "老板", False),
    ("customer_inquiry", "technical_review", "admin", 4, "系统管理员", True),
    ("quote_group", "pricing", "sales", 2, "业务员", True),
    ("quote_group", "pricing", "engineering", 2, "工程师", False),
    ("nonconforming_record", "confirm", "quality", 1, "品管", True),
    ("nonconforming_record", "verify_import", "quality", 1, "品管", True),
    ("nonconforming_record", "confirm", "boss", 3, "老板", False),
    ("nonconforming_record", "confirm", "admin", 4, "系统管理员", True),
    ("nonconforming_record", "prepare", "engineering", 1, "工程师", True),
    ("nonconforming_record", "start", "prod", 1, "操作工", True),
    ("nonconforming_record", "step:operation-1", "prod", 1, "操作工", True),
    ("nonconforming_record", "submit", "quality", 1, "品管", True),
    ("nonconforming_record", "inspect", "prod", 2, "生产主管", False),
    ("nonconforming_record", "unknown", "admin", 4, "系统管理员", False),
    ("unknown", "label", "admin", 4, "系统管理员", False),
])
def test_assignee_source_step_permissions_match_existing_queues(source_type, step, dept, level, position, expected):
    task = source().model_copy(update={"source_type": source_type, "step_key": step,
                                       "company": "tianyue" if source_type == "nonconforming_record" else None})
    user = SimpleNamespace(dept=dept, role_level=level, position=position)
    assert can_receive_task(task, user, "tianyue") is expected


def test_assignee_options_reject_company_mismatch_blocked_and_preview_tasks():
    task = source().model_copy(update={"source_type": "nonconforming_record", "step_key": "confirm", "company": "tianyue"})
    user = SimpleNamespace(dept="quality", role_level=1, position="品管")
    assert can_receive_task(task, user, "tianyue")
    assert not can_receive_task(task, user, "gaibo")
    assert not can_receive_task(task.model_copy(update={"company": None}), user, "tianyue")
    assert not can_receive_task(task.model_copy(update={"blocked_reason": "等待前序"}), user, "tianyue")
    assert not can_receive_task(task.model_copy(update={"scope": "created"}), user, "tianyue")
    user.is_switched = True
    assert not can_receive_task(task, user, "tianyue")


@pytest.mark.asyncio
async def test_blocked_tasks_cannot_claim_but_owner_can_release(isolated_assignments):
    async with isolated_assignments() as db:
        user = await db.get(User, 1)
        blocked = source().model_copy(update={"blocked_reason": "等待前序", "actionable": False})
        with pytest.raises(HTTPException) as error:
            await change_assignment(db, user, request(), "claim", loader(blocked))
        assert error.value.status_code == 409
        await change_assignment(db, user, request(), "claim", loader())
        tasks = await apply_assignments(db, [blocked], user)
        assert not tasks[0].can_claim and tasks[0].can_release
        await change_assignment(db, user, request(1), "release", loader(blocked))


@pytest.mark.asyncio
async def test_source_edit_retains_handler_but_handoff_uses_new_task_key(isolated_assignments):
    async with isolated_assignments() as db:
        user = await db.get(User, 1)
        await change_assignment(db, user, request(), "claim", loader())
        changed = source("label:2")
        tasks = await apply_assignments(db, [changed], user)
        assert len(tasks) == 2 and tasks[0].assignee_id == user.id and tasks[0].assignment_version == 1
        other = await db.get(User, 2)
        with pytest.raises(HTTPException) as taken:
            await change_assignment(db, other, request(1, "label:2"), "claim", loader(changed))
        assert taken.value.status_code == 409
        with pytest.raises(HTTPException) as stale:
            await change_assignment(db, user, request(1, "label:1"), "release", loader(changed))
        assert stale.value.status_code == 409
        released = await change_assignment(db, user, request(1, "label:2"), "release", loader(changed))
        assert released["version"] == 2
        next_step = source("shipping:1").model_copy(update={"key": "line:1:shipping"})
        next_tasks = await apply_assignments(db, [next_step], user)
        assert len(next_tasks) == 1 and next_tasks[0].assignee_id is None and next_tasks[0].can_claim


@pytest.mark.asyncio
async def test_company_assignment_keys_are_independent(isolated_assignments):
    async with isolated_assignments() as db:
        user = await db.get(User, 1)
        await change_assignment(db, user, request(), "claim", loader(source(company="tianyue")))
        tasks = await apply_assignments(db, [source(company="gaibo")], user)
        assert tasks[0].assignment_version == 0 and tasks[0].assignee_id is None


@pytest.mark.asyncio
async def test_concurrent_first_claim_has_one_owner_and_one_audit(isolated_assignments):
    async def claim(user_id):
        async with isolated_assignments() as db:
            user = await db.get(User, user_id)
            try:
                result = await change_assignment(db, user, request(), "claim", loader())
                await db.commit()
                return result["assignee_id"]
            except HTTPException as error:
                await db.rollback()
                return error.status_code
    outcomes = await asyncio.gather(claim(1), claim(2))
    assert sorted(outcomes) in ([1, 409], [2, 409])
    async with isolated_assignments() as db:
        assert len((await db.execute(select(WorkbenchAssignment))).scalars().all()) == 1
        assert len((await db.execute(select(WorkbenchAssignmentEvent))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_effective_context_preview_reduces_identity_and_denies_mutation(isolated_assignments, monkeypatch):
    from app.api import workbench
    async def active(_db, _user_id):
        return SimpleNamespace(is_active=True, switched_to_dept="warehouse", switched_to_role_level=1,
                               original_dept="admin", original_role_level=4, switch_type="to_warehouse",
                               switched_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(hours=1))
    monkeypatch.setattr(workbench.admin_service, "get_active_context_switch", active)
    async with isolated_assignments() as db:
        admin = await db.get(User, 5)
        actor = await effective_actor(db, admin)
        assert actor.id == admin.id and actor.dept == "warehouse" and actor.role_level == 1 and actor.is_switched
        assert actor.position != "系统管理员" and not actor.is_tech
        tasks = await apply_assignments(db, [source()], actor)
        assert not any(item.can_claim or item.can_release or item.can_assign for item in tasks)
        with pytest.raises(HTTPException) as error:
            await change_assignment(db, actor, request(), "claim", loader())
        assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_api_assignment_contract_is_authenticated(isolated_assignments, monkeypatch):
    from app.api import workbench
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    async with isolated_assignments() as db:
        actor = await db.get(User, 1)
        async def db_override():
            yield db
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: actor
        monkeypatch.setattr(workbench, "load_tasks", loader())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/workbench/tasks/claim", json={**request().model_dump(), "user_id": 2})
            assert response.status_code == 200 and response.json()["assignee_id"] == 1
            page = await client.get("/api/v1/workbench?scope=mine")
            assert page.status_code == 200 and page.json()["counts"]["mine"] == 1
            invalid = await client.post("/api/v1/workbench/tasks/release", json={**request(1).model_dump(), "expected_version": -1})
            assert invalid.status_code == 422
