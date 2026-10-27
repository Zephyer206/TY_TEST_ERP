"""Task handoffs mirror existing source workflow transitions without DB writes."""

from datetime import date, datetime, timezone
from types import SimpleNamespace as Record

import pytest

from app.services import nonconforming_workflow as workflow
from app.services.workbench_service import build_page, plan_tasks, role_queues
from app.services.workbench_sources import inquiry_tasks, load_additional_tasks, nonconforming_tasks, quote_tasks


def actor(**changes):
    return Record(**(dict(id=7, role_level=2, dept="sales", position="业务", real_name="测试业务", username="sales") | changes))


def inquiry(**changes):
    return Record(**(dict(id=12, inquiry_no="RFQ-12", project_name="客户支架", created_by=7, due_date=date(2026, 10, 25),
                        status="报价中", technical_review="待评审", updated_at=datetime(2026, 10, 20), created_at=None) | changes))


def quote(**changes):
    return Record(**(dict(id=31, group_no="QG-31", project_name="客户支架", created_by=8, status="待报价",
                        updated_at=datetime(2026, 10, 21), created_at=None) | changes))


def defect_payload(**changes):
    return workflow.empty_draft() | dict(
        id="defect-12", no="NC-12", company="tianyue", status="pending_confirmation", quantity=10,
        customer="客户甲", partNo="P-1", partName="支架", source="厂内检验", description="毛刺超标",
        disposition="rework", treatment="去除毛刺并检验", assignee="源单执行负责人", plannedDate="2026-10-25", week="2026-10-19",
        priority=1, moldReady=False, paused=False, acceptedQty=0, scrappedQty=0, otherQty=0,
        planSteps=[dict(id="step-1", kind="rework", requirement="去除毛刺", completedAt="", completedBy="", result="")],
        inspectionItems=[dict(id="check-1", name="毛刺", standard="无毛刺")], submission=None, actualDate="", history=[],
        createdAt="2026-10-20T00:00:00Z") | changes


def defect(payload=None, **changes):
    row = payload or defect_payload()
    return Record(**(dict(id=row["id"], record_no=row["no"], company=row["company"], status=row["status"],
                        part_no=row["partNo"], payload=row, revision=2, updated_at=datetime(2026, 10, 21)) | changes))


@pytest.mark.parametrize("review_status", ["待评审", "评审中", "待补充"])
def test_inquiry_department_queue_and_creator_tracking_are_distinct(review_status):
    engineer = actor(id=8, dept="engineering")
    tasks = inquiry_tasks(inquiry(technical_review=review_status), "客户甲", engineer)
    assert [(item.scope, item.owner_department) for item in tasks] == [("team", "开发部")]
    assert tasks[0].route == "/projects/rfq?review=technical&inquiry_id=12"
    assert tasks[0].next_role == "业务报价" and tasks[0].completion_requirements
    if review_status == "待补充":
        assert tasks[0].title == "补充技术评审资料" and tasks[0].owner_role == "技术评审"
        assert tasks[0].route.startswith("/projects/rfq?review=technical")
    assert [item.scope for item in inquiry_tasks(inquiry(), "客户甲", actor())] == ["created"]
    assert inquiry_tasks(inquiry(created_by=99), "客户甲", actor(id=8, dept="engineering", role_level=1)) == []
    assert inquiry_tasks(inquiry(technical_review="已完成"), "客户甲", engineer) == []
    assert inquiry_tasks(inquiry(status="已取消"), "客户甲", engineer) == []


def test_quote_handoff_is_business_work_not_technical_creator_ownership():
    reviewed = inquiry(technical_review="已完成")
    business_tasks = quote_tasks(quote(), reviewed, "客户甲", actor())
    assert [item.scope for item in business_tasks] == ["team", "created"]
    assert business_tasks[0].route.endswith("?group_id=31")
    engineer_tasks = quote_tasks(quote(), reviewed, "客户甲", actor(id=8, dept="engineering"))
    assert [item.scope for item in engineer_tasks] == ["created"]
    for status in ("已报价", "已提交审批", "已审批", "已定点"):
        assert quote_tasks(quote(status=status), reviewed, "客户甲", actor()) == []


def test_quote_waits_for_real_technical_review_completion():
    task = quote_tasks(quote(), inquiry(), "客户甲", actor())[0]
    assert not task.actionable and task.blocked_reason == "前序技术评审尚未完成"
    assert quote_tasks(quote(), inquiry(technical_review="已完成"), "客户甲", actor())[0].actionable


def test_nonconforming_uses_source_department_permissions_including_lv3_boundary():
    row = defect()
    qc = actor(id=9, dept="quality", role_level=1)
    tasks = nonconforming_tasks(row, qc)
    assert [item.step_key for item in tasks] == ["confirm"]
    assert tasks[0].company == "tianyue" and "record=defect-12" in tasks[0].route
    assert tasks[0].source_assignee == "源单执行负责人"
    assert tasks[0].assignee_id is None and tasks[0].assignment_state == "unassigned"
    assert nonconforming_tasks(row, actor(dept="engineering")) == []
    assert nonconforming_tasks(row, actor(dept="boss", role_level=3)) == []
    assert nonconforming_tasks(row, actor(dept="admin", role_level=4))[0].step_key == "confirm"


def test_nonconforming_preparation_and_execution_wait_are_separate_tasks():
    row = defect(defect_payload(status="pending"))
    prepare = nonconforming_tasks(row, actor(dept="engineering"))
    assert [(item.step_key, item.actionable) for item in prepare] == [("prepare", True)]
    execution = nonconforming_tasks(row, actor(dept="prod", role_level=1))
    assert len(execution) == 1 and execution[0].step_key == "start"
    assert not execution[0].actionable and "模具尚未就绪" in execution[0].blocked_reason
    assert row.payload["moldReady"] is False  # projection never mutates source state


def test_nonconforming_full_source_workflow_moves_tasks_and_partial_counts_correctly():
    qc = actor(id=9, dept="quality", role_level=1)
    engineering = actor(id=8, dept="engineering")
    production = actor(id=10, dept="prod", role_level=1)
    row = defect_payload()
    row = workflow.apply_action(row, "confirm", {}, qc)
    assert nonconforming_tasks(defect(row), engineering)[0].step_key == "prepare"
    row = workflow.apply_action(row, "prepare", {"ready": True}, engineering)
    assert nonconforming_tasks(defect(row), engineering) == []
    assert nonconforming_tasks(defect(row), production)[0].actionable
    row = workflow.apply_action(row, "start", {}, production)
    assert nonconforming_tasks(defect(row), production)[0].step_key == "step:step-1"
    row = workflow.apply_action(row, "finish_step", {"stepId": "step-1", "note": "已去毛刺"}, production)
    assert nonconforming_tasks(defect(row), production)[0].step_key == "submit"
    row = workflow.apply_action(row, "submit", {"result": {"good": 4, "note": "本轮完成4件"}}, production)
    assert nonconforming_tasks(defect(row), production) == []
    assert nonconforming_tasks(defect(row), qc)[0].step_key == "inspect"
    evidence = {"quantityChecked": True, "checks": [{"id": "check-1", "actual": "无毛刺", "passed": True}]}
    row = workflow.apply_action(row, "inspect", {"passed": True, "note": "通过", "evidence": evidence}, qc)
    assert row["acceptedQty"] == 4 and workflow.remaining(row) == 6
    returned = nonconforming_tasks(defect(row), production)
    assert returned[0].step_key == "step:step-1" and "6 件" in returned[0].summary
    row = workflow.apply_action(row, "finish_step", {"stepId": "step-1", "note": "剩余已完成"}, production)
    row = workflow.apply_action(row, "submit", {"result": {"good": 6, "note": "剩余完成6件"}}, production)
    row = workflow.apply_action(row, "inspect", {"passed": True, "note": "通过", "evidence": evidence}, qc)
    assert row["status"] == "closed" and workflow.remaining(row) == 0
    assert nonconforming_tasks(defect(row), qc) == []


def test_nonconforming_inspection_rejection_returns_execution_without_counting_acceptance():
    qc = actor(dept="quality")
    row = defect_payload(status="inspection", submission={"good": 10, "scrap": 0, "other": 0, "note": "处理完成"})
    row = workflow.apply_action(row, "inspect", {"passed": False, "note": "毛刺仍超标"}, qc)
    assert row["status"] == "processing" and row["acceptedQty"] == 0
    assert nonconforming_tasks(defect(row), actor(dept="engineering"))[0].step_key == "prepare"
    assert any(item.step_key == "step:step-1" and not item.actionable for item in nonconforming_tasks(defect(row), actor(dept="prod")))


@pytest.mark.parametrize("inspection_passes", [True, False])
def test_repeated_nonconforming_rounds_never_reuse_prior_task_identity(inspection_passes):
    qc = actor(id=9, dept="quality")
    production = actor(id=10, dept="prod", role_level=1)
    row = workflow.apply_action(defect_payload(moldReady=True), "confirm", {}, qc)
    row = workflow.apply_action(row, "start", {}, production)
    first_step_key = nonconforming_tasks(defect(row), production)[0].key
    row = workflow.apply_action(row, "finish_step", {"stepId": "step-1", "note": "首轮去毛刺"}, production)
    first_submit_key = nonconforming_tasks(defect(row), production)[0].key
    row = workflow.apply_action(row, "submit", {"result": {"good": 4, "note": "首轮4件"}}, production)
    first_inspection_key = nonconforming_tasks(defect(row), qc)[0].key
    evidence = {"quantityChecked": True, "checks": [{"id": "check-1", "actual": "无毛刺", "passed": True}]}
    row = workflow.apply_action(row, "inspect", {"passed": inspection_passes, "note": "本轮验收", "evidence": evidence}, qc)
    second_step = nonconforming_tasks(defect(row), production)[0]
    assert second_step.step_key == "step:step-1" and second_step.key != first_step_key
    assert workflow.remaining(row) == (6 if inspection_passes else 10)
    row = workflow.apply_action(row, "finish_step", {"stepId": "step-1", "note": "下一轮去毛刺"}, production)
    assert nonconforming_tasks(defect(row), production)[0].key != first_submit_key
    row = workflow.apply_action(row, "submit", {"result": {"good": 4, "note": "下一轮4件"}}, production)
    assert nonconforming_tasks(defect(row), qc)[0].key != first_inspection_key


def test_return_reconfirm_creates_new_start_task_but_draft_edits_keep_handler_identity():
    qc = actor(id=9, dept="quality")
    production = actor(id=10, dept="prod")
    row = defect_payload(moldReady=True)
    first_confirm = nonconforming_tasks(defect(row), qc)[0].key
    # A normal edit creates history and changes the source revision but is still
    # the same confirmation task, so its existing handler must remain.
    draft = {key: row[key] for key in workflow.empty_draft()}
    draft["description"] = "补充尺寸异常说明"
    row = workflow.apply_action(row, "edit", {"draft": draft}, qc)
    assert nonconforming_tasks(defect(row, revision=3), qc)[0].key == first_confirm
    row = workflow.apply_action(row, "confirm", {}, qc)
    first_start = nonconforming_tasks(defect(row), production)[0].key
    # Readiness/progress metadata edits within a step do not change its round.
    row = workflow.apply_action(row, "prepare", {"ready": True}, actor(dept="engineering"))
    assert nonconforming_tasks(defect(row, revision=4), production)[0].key == first_start
    row = workflow.apply_action(row, "return", {"reason": "重新核对方案"}, qc)
    assert nonconforming_tasks(defect(row), qc)[0].key != first_confirm
    row = workflow.apply_action(row, "confirm", {}, qc)
    assert nonconforming_tasks(defect(row), production)[0].key != first_start


def test_long_valid_source_identifiers_fit_persisted_assignment_key():
    row = defect_payload(id="r" * 120, status="processing", moldReady=True,
                         planSteps=[dict(id="s" * 150, kind="rework", requirement="返工", completedAt="", completedBy="", result="")])
    task = nonconforming_tasks(defect(row), actor(dept="prod"))[0]
    assert len(f"{task.company}|{task.key}") <= 240
    assert task.source_id == "r" * 120 and task.step_key == "step:" + "s" * 150


def test_imported_unreviewed_progress_is_blocked_and_has_quality_recovery_task():
    row = defect(defect_payload(status="processing", importedProgress=True, importInfo={"reviewed": False}))
    qc = nonconforming_tasks(row, actor(dept="quality"))
    assert any(item.step_key == "verify_import" and item.actionable for item in qc)
    production = nonconforming_tasks(row, actor(dept="prod"))
    assert production and all(not item.actionable and "导入进度" in item.blocked_reason for item in production)


def test_task_step_identity_changes_at_production_handoff():
    user = actor(dept="admin", role_level=4)
    plan = Record(id=13, created_by=99, status="planned", machine_id=None, material_status="pending", total_qty=50,
                  due_date=None, is_urgent=False, updated_at=None, created_at=None)
    before = plan_tasks(plan, None, None, user, role_queues(user))[0]
    plan.material_status = "ready"
    after = plan_tasks(plan, None, None, user, role_queues(user))[0]
    assert before.key != after.key and before.source_revision != after.source_revision
    assert before.source_type == "production_plan" and before.source_id == "13"
    assert before.next_role == "生产排产" and after.next_role == "生产执行"


def test_blocked_statistics_filters_and_coverage_are_truthful():
    tasks = nonconforming_tasks(defect(defect_payload(status="pending")), actor(dept="admin", role_level=4))
    options = dict(acceptance_mode=False, scope="team", now=datetime(2026, 10, 25, 9, tzinfo=timezone.utc))
    page = build_page(tasks, actor(), **options)
    assert page.total == 2 and page.stats.pending == 1 and page.stats.blocked == 1
    assert page.stats.today == 1
    assert build_page(tasks, actor(), **options, due="blocked").total == 1
    assert build_page(tasks, actor(), **options, due="today").total == 1
    coverage = {item.key: item for item in page.coverage}
    assert coverage["nonconforming"].status == "active" and coverage["finance_hr"].status == "not_connected"
    switched = build_page([], actor(is_switched=True), **options)
    assert switched.identity.is_switched


@pytest.mark.asyncio
async def test_loader_scopes_quality_tasks_to_selected_company_without_db_writes():
    statements = []
    rows = [defect(defect_payload(company="gaibo"))]

    class Result:
        def __init__(self, result):
            self.result = result

        def all(self):
            return self.result

        def scalars(self):
            return self

    class Database:
        async def execute(self, statement):
            statements.append(statement)
            return Result(rows if len(statements) == 3 else [])

    tasks = await load_additional_tasks(Database(), actor(dept="quality"), "gaibo")
    assert [task.company for task in tasks] == ["gaibo"]
    compiled = statements[-1].compile()
    assert "company" in str(compiled) and "gaibo" in compiled.params.values()
    assert all(statement.get_execution_options().get("populate_existing") is True for statement in statements)
