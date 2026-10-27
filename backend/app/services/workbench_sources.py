"""Read-only projections of the existing inquiry, quote and quality workflows.

Task ownership follows the source operation's permission floor. A workbench task
does not grant permission or update the source business record.
"""

from datetime import date, datetime
from hashlib import sha256
from urllib.parse import urlencode

from sqlalchemy import select

from app.models.customer import Customer
from app.models.customer_inquiry import CustomerInquiry
from app.models.nonconforming import NonconformingRecord
from app.models.quote_group import QuoteGroup
from app.schemas.workbench import WorkbenchCoverage, WorkbenchTask
from app.services.nonconforming_workflow import ROLES, active_step, has_rework, remaining

DEVELOPMENT = {"engineering", "design", "development", "tech", "开发", "开发部", "技术", "技术部"}
SALES = {"sales", "business", "业务", "业务部"}
INQUIRY_TERMINAL = {"已关闭", "已取消", "已定点", "closed", "cancelled", "completed"}
NC_ROUND_BOUNDARIES = {"确认处理方案", "退回待确认", "部分验收通过", "验收不通过"}


def source_revision(record, step: str) -> str:
    value = getattr(record, "revision", None)
    if value is None:
        value = getattr(record, "updated_at", None) or getattr(record, "last_modified_at", None) or getattr(record, "created_at", None)
    return f"{step}:{value.isoformat() if isinstance(value, datetime) else value or ''}"


def _department_queue(user, departments: set[str]) -> bool:
    return user.role_level >= 2 and (user.role_level >= 4 or (user.dept or "").strip().lower() in departments)


def _nc_action(user, action: str) -> bool:
    # Keep this identical to require_action in nonconforming_workflow.
    return user.role_level >= 4 or user.dept in ROLES[action]


def _date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value) if value else None
    except (ValueError, TypeError):
        return None


def nonconforming_round(row: dict) -> str:
    """Identify a source workflow incarnation, not an ordinary save revision.

    Inspections reset the same step IDs for the remaining/rejected quantity;
    return and reconfirm can also recreate a previously handled step. Source
    history is append-only and includes event IDs, so a fresh round never
    inherits the assignment of that earlier incarnation. Draft and progress
    edits retain the most recent boundary and therefore the current handler.
    """
    boundaries = [entry for entry in row.get("history", []) if entry.get("action") in NC_ROUND_BOUNDARIES]
    if not boundaries:
        return "initial"
    latest = boundaries[0]  # Source workflow inserts newest history first.
    identity = f"{len(boundaries)}:{latest.get('id', '')}:{latest.get('at', '')}:{latest['action']}"
    return sha256(identity.encode("utf-8")).hexdigest()[:16]


def inquiry_tasks(inquiry, customer, user) -> list[WorkbenchTask]:
    if inquiry.status in INQUIRY_TERMINAL or inquiry.technical_review == "已完成":
        return []
    if inquiry.technical_review not in {"待评审", "评审中", "待补充"}:
        return []
    step = "technical_review"
    base = dict(module="inquiry", document_no=inquiry.inquiry_no, customer=customer,
                title="补充技术评审资料" if inquiry.technical_review == "待补充" else "完成技术评审",
                summary=inquiry.project_name, due_date=_date(inquiry.due_date),
                updated_at=inquiry.updated_at or inquiry.created_at,
                source_type="customer_inquiry", source_id=str(inquiry.id), step_key=step,
                source_revision=source_revision(inquiry, step), owner_department="开发部",
                owner_role="技术评审", role="技术评审", next_role="业务报价",
                route=f"/projects/rfq?review=technical&inquiry_id={inquiry.id}",
                completion_requirements=["核对客户图纸与零件技术资料", "补齐材料、工艺及冲床类型并完成技术评审；原单完成后自动转入报价组"])
    result = []
    if _department_queue(user, DEVELOPMENT):
        result.append(WorkbenchTask(key=f"inquiry:{inquiry.id}:{step}", scope="team", **base))
    if inquiry.created_by == user.id:
        result.append(WorkbenchTask(key=f"inquiry:{inquiry.id}:created", scope="created", action_label="查看进度", **base))
    return result


def quote_tasks(group, inquiry, customer, user) -> list[WorkbenchTask]:
    # The current source service supports quote entry and save only. There is no
    # approval command, so approved/submitted rows must not create fake tasks.
    if group.status != "待报价":
        return []
    step = "pricing"
    blocked = "前序技术评审尚未完成" if inquiry and inquiry.technical_review != "已完成" else None
    base = dict(module="quote", document_no=group.group_no, customer=customer,
                title="完成客户报价", summary=group.project_name,
                due_date=_date(inquiry.due_date) if inquiry else None,
                updated_at=group.updated_at or group.created_at,
                source_type="quote_group", source_id=str(group.id), step_key=step,
                source_revision=source_revision(group, step), owner_department="业务部",
                owner_role="业务报价", role="业务报价", next_role="客户报价跟进",
                route=f"/projects/quotes?group_id={group.id}", blocked_reason=blocked, actionable=not blocked,
                completion_requirements=["核对已通过评审的技术资料与推荐方案", "填写材料、费用和产品报价，在原报价组保存为已报价"])
    result = []
    if _department_queue(user, SALES):
        result.append(WorkbenchTask(key=f"quote:{group.id}:{step}", scope="team", **base))
    # The source creates quotes on technical review; that creator can track but
    # does not automatically become the sales handling owner.
    if group.created_by == user.id or (inquiry and inquiry.created_by == user.id):
        result.append(WorkbenchTask(key=f"quote:{group.id}:created", scope="created", action_label="查看进度", **base))
    return result


def nonconforming_tasks(model, user) -> list[WorkbenchTask]:
    if model.status == "closed":
        return []
    row = model.payload
    if remaining(row) <= 0:
        return []
    status = model.status
    round_key = nonconforming_round(row)
    common = dict(module="nonconforming", document_no=model.record_no, customer=row.get("customer") or None,
                  summary=f"{row.get('partNo', model.part_no)} · {row.get('partName', '')} · 待处理 {remaining(row):,} 件",
                  due_date=_date(row.get("plannedDate")), updated_at=model.updated_at,
                  source_type="nonconforming_record", source_id=str(model.id), company=model.company,
                  source_assignee=row.get("assignee") or None,
                  route="/nonconforming?" + urlencode({"company": model.company, "record": model.id}))
    tasks = []

    def add(step, title, role, department, action, requirements, next_role, blocked=None):
        if not _nc_action(user, action):
            return
        # Imported record and step identifiers may each be long. Preserve them
        # in source metadata while bounding the persisted ownership key.
        identity = "\0".join((model.company, str(model.id), step, round_key))
        task_key = "nc:" + sha256(identity.encode("utf-8")).hexdigest()
        tasks.append(WorkbenchTask(key=task_key, scope="team", title=title,
                                  step_key=step, role=role, owner_role=role, owner_department=department,
                                  source_revision=source_revision(model, step), completion_requirements=requirements,
                                  next_role=next_role, blocked_reason=blocked, actionable=not blocked, **common))

    if status == "pending_confirmation":
        add("confirm", "确认不良品处理方案", "品管确认", "品管部", "confirm",
            ["核实不良数量、来源与隔离信息", "确认处置方式、执行负责人、计划日期、顺序步骤及验收标准"], "开发准备 / 生产执行")
        return tasks
    imported_unreviewed = row.get("importedProgress") and not (row.get("importInfo") or {}).get("reviewed")
    if imported_unreviewed and status in {"pending", "processing"}:
        add("verify_import", "复核导入进度与处理方案", "品管复核", "品管部", "confirm",
            ["在原单填写原因并退回待确认", "核对导入进度与处理方案，重新确认后继续执行"], "生产执行")
    step = active_step(row)
    rework_wait = has_rework(row) and not row.get("moldReady") and (
        any(item["kind"] == "rework" and not item.get("completedAt") for item in row.get("planSteps", [])) or not row.get("planSteps"))
    if status in {"pending", "processing"} and rework_wait and not imported_unreviewed:
        add("prepare", "准备返工模具", "开发准备", "开发部", "prepare",
            ["根据已确认的返工方案完成模具准备", "在原单记录返工模具已就绪"], "生产执行")
    blocked = "导入进度尚未复核，需退回待确认并重新确认方案" if imported_unreviewed else None
    if not blocked and (step["kind"] if step else row.get("disposition")) == "rework" and not row.get("moldReady"):
        blocked = "返工模具尚未就绪，等待开发准备"
    if status == "pending":
        add("start", "开始不良品处理", "处理执行", "生产部 / 品管部", "start",
            ["确认当前步骤的前序条件与返工模具状态", "按原单已确认方案开工并记录处理进度"], "处理执行", blocked)
    elif status == "processing":
        if step:
            add(f"step:{step['id']}", "完成当前处理步骤", "处理执行", "生产部 / 品管部", "finish_step",
                [step.get("requirement") or "按已确认方案完成当前步骤", "填写本步实际处理情况，按顺序完成后再提交品质验收"], "下一处理步骤 / 品管验收", blocked)
        else:
            add("submit", "提交处理结果验收", "处理执行", "生产部 / 品管部", "submit",
                ["核实本轮合格、报废或其他处置数量", "填写结果说明，在原单提交品质验收"], "品管验收", blocked)
    elif status == "inspection":
        add("inspect", "验收不良品处理结果", "品管验收", "品管部", "inspect",
            ["逐项记录实测结果并判定验收项目", "核对实物数量及放行要求；失败退回处理，全部数量验收后原单关闭"], "生产继续处理 / 后续工序")
    return tasks


async def load_additional_tasks(db, user, company: str) -> list[WorkbenchTask]:
    tasks = []
    inquiry_query = select(CustomerInquiry, Customer.name).outerjoin(Customer, Customer.id == CustomerInquiry.customer_id)
    if not _department_queue(user, DEVELOPMENT):
        inquiry_query = inquiry_query.where(CustomerInquiry.created_by == user.id)
    inquiry_query = inquiry_query.where(CustomerInquiry.technical_review.in_(("待评审", "评审中", "待补充")))
    for inquiry, customer in (await db.execute(inquiry_query.execution_options(populate_existing=True))).all():
        tasks.extend(inquiry_tasks(inquiry, customer, user))
    quote_query = (select(QuoteGroup, CustomerInquiry, Customer.name)
                   .outerjoin(CustomerInquiry, CustomerInquiry.id == QuoteGroup.inquiry_id)
                   .outerjoin(Customer, Customer.id == QuoteGroup.customer_id)
                   .where(QuoteGroup.status == "待报价"))
    if not _department_queue(user, SALES):
        quote_query = quote_query.where((QuoteGroup.created_by == user.id) | (CustomerInquiry.created_by == user.id))
    for group, inquiry, customer in (await db.execute(quote_query.execution_options(populate_existing=True))).all():
        tasks.extend(quote_tasks(group, inquiry, customer, user))
    if any(_nc_action(user, action) for action in ("confirm", "prepare", "start", "inspect")):
        nc_query = select(NonconformingRecord).where(NonconformingRecord.company == company, NonconformingRecord.status != "closed")
        for record in (await db.execute(nc_query.execution_options(populate_existing=True))).scalars().all():
            tasks.extend(nonconforming_tasks(record, user))
    return tasks


def coverage() -> list[WorkbenchCoverage]:
    return [WorkbenchCoverage(key=key, label=label, status=status, description=description) for key, label, status, description in [
        ("inquiry", "技术评审", "active", "客户询价待评审与待补充资料，完成后转入报价组"),
        ("quote", "业务报价", "active", "待报价组；保存已报价后自动移出，不包含未建设的审批流程"),
        ("production", "资材与排产", "active", "未排产计划的资材确认、生产排产与本人发起进度"),
        ("shipping", "标签与发货", "active", "草稿、标签确认、实发确认及取消申请确认"),
        ("nonconforming", "不良品处置", "active", "按当前公司与源流程权限显示确认、返工准备、执行和验收"),
        ("production_execution", "生产工序与检验", "not_connected", "开工报工、首件、巡检、全检包装与喷涂任务尚未接入共用队列"),
        ("equipment", "设备维修保养", "not_connected", "设备工单尚未接入共用队列"),
        ("finance_hr", "会计与人事", "not_connected", "对应业务数据源与岗位任务尚未建设"),
    ]]
