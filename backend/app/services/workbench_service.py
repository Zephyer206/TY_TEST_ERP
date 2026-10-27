"""Build task queues without changing business status or inventing assignees.

An unassigned production/shipping operation belongs to a role queue. Only
creator-owned drafts and an explicit creator confirmation are personal tasks.
Creating a plan does not make its material/scheduling work a personal task.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.part import Part
from app.models.production import ProductionPlan
from app.models.shipping_order import ShippingOrder, ShippingOrderLine
from app.schemas.workbench import (
    DueFilter, TaskModule, TaskScope, WorkbenchCounts, WorkbenchIdentity,
    WorkbenchPage, WorkbenchStats, WorkbenchTask,
)
from app.services.shipping_order_service import actor_kind, derive_order_status, remaining_qty
from app.services.workbench_sources import coverage, load_additional_tasks, source_revision

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
PLAN_TERMINAL = {"completed", "cancelled", "closed"}
ORDER_TERMINAL = {"completed", "cancelled", "completed_with_cancellation"}


def role_queues(user) -> set[str]:
    """Respect route role levels and existing department/position metadata."""
    if user.role_level >= 3:
        return {"materials", "scheduling", "label", "shipping"}
    description = f"{user.dept or ''} {user.position or ''}".lower()
    queues = set()
    if user.role_level >= 2:
        if any(word in description for word in ("material", "purchas", "procurement", "资材", "采购")):
            queues.add("materials")
        if any(word in description for word in ("prod", "生产", "制造", "排产")):
            queues.add("scheduling")
    if any(word in description for word in ("warehouse", "label", "仓库", "标签", "仓储")):
        queues.update(("label", "shipping"))
    return queues


def plan_tasks(plan, part, customer, user, queues: set[str]) -> list[WorkbenchTask]:
    if plan.status in PLAN_TERMINAL:
        return []
    name = part.internal_name if part else "未关联零件"
    part_no = part.customer_part_no if part else None
    summary = " · ".join(filter(None, (part_no, name, f"目标 {plan.total_qty or 0:,} 件")))
    due = plan.due_date.date() if isinstance(plan.due_date, datetime) else plan.due_date
    unscheduled = plan.machine_id is None and plan.status in (None, "planned")
    stage = "待资材确认" if plan.material_status != "ready" else "待排产"
    route = f"/production?plan_id={plan.id}"
    if plan.material_status == "ready" or plan.machine_id is not None:
        route = f"/production/scheduling?plan_id={plan.id}"
    if plan.status == "queued":
        stage = "等待生产"
    elif plan.status == "in_progress":
        stage = "生产中"
    base = dict(module="production", document_no=f"生产计划 #{plan.id}", summary=summary,
                customer=customer, due_date=due, urgent=bool(plan.is_urgent),
                updated_at=plan.updated_at or plan.created_at, route=route)
    tasks = []
    queue = "materials" if plan.material_status != "ready" else "scheduling"
    if unscheduled and queue in queues:
        tasks.append(WorkbenchTask(key=f"plan:{plan.id}:{queue}", scope="team", title=stage,
                                   role="资材" if queue == "materials" else "生产计划", **base))
    if plan.created_by == user.id and user.role_level >= 2:
        tasks.append(WorkbenchTask(key=f"plan:{plan.id}:created", scope="created", title=stage,
                                   role="流程跟进", action_label="查看进度", **base))
    for task in tasks:
        task.source_type = "production_plan"
        task.source_id = str(plan.id)
        task.step_key = queue if unscheduled else "production_progress"
        task.source_revision = source_revision(plan, task.step_key) + f":{plan.status}:{plan.material_status}:{plan.machine_id}"
        task.owner_department = "原料仓库" if queue == "materials" and unscheduled else "生产部"
        task.owner_role = "资材确认" if queue == "materials" and unscheduled else "生产排产" if unscheduled else "生产执行"
        task.next_role = "生产排产" if queue == "materials" and unscheduled else "生产执行"
        task.completion_requirements = (["核实可用物料与预计可用日期", "在原生产计划完成资材确认，物料就绪后交生产排产"]
                                        if queue == "materials" and unscheduled else
                                        ["确认物料已就绪并选择合适机台与排产时间", "在原排产页面完成排产，任务转入生产执行"] if unscheduled else
                                        ["在原生产页面跟进计划进度", "原业务服务完成或取消计划后移出进行中记录"])
    return tasks


def shipping_tasks(order, customer, user, queues: set[str]) -> list[WorkbenchTask]:
    tasks = []
    route = f"/shipping-orders/{order.id}"
    base = dict(module="shipping", document_no=order.order_no, customer=customer,
                route=route, updated_at=order.last_modified_at or order.created_at)
    if order.status == "draft":
        if order.created_by == user.id:
            tasks.append(WorkbenchTask(key=f"order:{order.id}:draft", scope="mine", title="提交发货订单",
                                       summary=order.po_no or "订单草稿", role="创建人", source_type="shipping_order",
                                       source_id=str(order.id), step_key="draft", source_revision=source_revision(order, "draft"),
                                       owner_department="业务部", owner_role="订单创建人", next_role="标签确认",
                                       completion_requirements=["核对客户、PO、零件数量及计划发货日", "在原订单提交有效明细，正式订单按原业务校验库存与预占"], **base))
        return tasks
    status = derive_order_status(order)
    if status in ORDER_TERMINAL:
        return tasks
    active_lines = [line for line in order.lines if remaining_qty(line) > 0]
    for line in active_lines:
        summary = f"{line.customer_part_no_snapshot} · {line.part_name_snapshot} · 待发 {remaining_qty(line):,} 件"
        pending = [c for c in line.cancellation_consents if c.status == "pending"]
        # A cancellation under review needs confirmation before further dispatch.
        if pending:
            consent = max(pending, key=lambda c: c.id)
            if consent.business_confirmed_by is None and order.created_by == user.id and actor_kind(user) == "business":
                tasks.append(WorkbenchTask(key=f"consent:{consent.id}:business", scope="mine", title="确认取消申请",
                                           summary=summary, role="业务确认", due_date=line.planned_ship_date, **base))
            if consent.label_confirmed_by is None and "label" in queues:
                tasks.append(WorkbenchTask(key=f"consent:{consent.id}:label", scope="team", title="确认取消申请",
                                           summary=summary, role="标签确认", due_date=line.planned_ship_date, **base))
            continue
        queue = "shipping" if line.label_confirmation else "label"
        if queue in queues:
            tasks.append(WorkbenchTask(key=f"line:{line.id}:{queue}", scope="team",
                                       title="确认发货" if queue == "shipping" else "确认标签",
                                       summary=summary, role="仓库" if queue == "shipping" else "标签",
                                       due_date=line.planned_ship_date, **base))
    if order.created_by == user.id and active_lines:
        stages = {"pending": "待标签确认", "ready_to_ship": "待发货", "partially_shipped": "部分发货"}
        tasks.append(WorkbenchTask(key=f"order:{order.id}:created", scope="created", title=stages.get(status, "处理中"),
                                   summary=f"{order.po_no or '未填写 PO'} · {len(active_lines)} 条未完成明细",
                                   role="流程跟进", due_date=min(line.planned_ship_date for line in active_lines),
                                   action_label="查看进度", **base))
    for task in tasks:
        task.source_type = "shipping_order"
        task.source_id = str(order.id)
        task.owner_department = "业务部" if task.scope == "mine" else "全检部"
        task.owner_role = task.role
        line = next((item for item in active_lines if task.key.startswith(f"line:{item.id}:")), None)
        consent = next(((item, consent) for item in active_lines for consent in item.cancellation_consents
                        if task.key.startswith(f"consent:{consent.id}:")), None)
        if line is not None:
            task.source_line_id = str(line.id)
            task.step_key = "shipping" if line.label_confirmation else "label"
            task.source_revision = source_revision(order, task.step_key) + f":{status}:{remaining_qty(line)}:{getattr(line, 'updated_at', '')}"
            task.next_role = "发货确认" if task.step_key == "label" else "业务交付跟进"
            task.completion_requirements = (["核对客户标签版本、件号、数量和订单匹配", "在原发货明细确认标签后交发货岗位"] if task.step_key == "label" else
                                            ["核对标签、剩余数量和库存门槛", "在原发货订单记录实际发出数量与物流，未发部分继续保留待办"])
        elif consent is not None:
            line, item = consent
            task.source_line_id = str(line.id)
            task.step_key = "cancel_business" if task.scope == "mine" else "cancel_label"
            task.source_revision = source_revision(order, task.step_key) + f":{item.id}:{item.business_confirmed_by}:{item.label_confirmed_by}:{remaining_qty(line)}"
            task.next_role = "另一确认岗位 / 原单剩余需求重算"
            task.completion_requirements = ["核对本次取消数量与原因", "仅完成当前岗位的取消确认；双方确认后由原业务服务更新需求"]
        else:
            task.step_key = "order_progress"
            task.source_revision = source_revision(order, task.step_key) + f":{status}"
            task.owner_role = "当前流程岗位"
            task.next_role = "标签确认 / 发货确认"
            task.completion_requirements = ["跟进原单当前岗位与剩余未发明细", "全部明细发出或取消后，原单完成并移出进行中记录"]
    return tasks


async def load_tasks(db, user, company: str = "tianyue") -> list[WorkbenchTask]:
    queues = role_queues(user)
    tasks = []
    if user.role_level >= 2:
        query = (select(ProductionPlan, Part, Customer.name)
                 .outerjoin(Part, Part.id == ProductionPlan.part_id)
                 .outerjoin(Customer, Customer.id == Part.customer_id)
                 .where(or_(ProductionPlan.status.is_(None), ProductionPlan.status.notin_(PLAN_TERMINAL))))
        if not queues.intersection({"materials", "scheduling"}):
            query = query.where(ProductionPlan.created_by == user.id)
        for plan, part, customer in (await db.execute(query.execution_options(populate_existing=True))).all():
            tasks.extend(plan_tasks(plan, part, customer, user, queues))
    query = (select(ShippingOrder, Customer.name)
             .outerjoin(Customer, Customer.id == ShippingOrder.customer_id)
             .where(or_(ShippingOrder.created_by == user.id,
                        ShippingOrder.status != "draft") if queues.intersection({"label", "shipping"})
                    else ShippingOrder.created_by == user.id)
             .where(ShippingOrder.status.notin_(ORDER_TERMINAL))
             .options(selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.shipment_lines),
                      selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.label_confirmation),
                      selectinload(ShippingOrder.lines).selectinload(ShippingOrderLine.cancellation_consents)))
    for order, customer in (await db.execute(query.execution_options(populate_existing=True))).all():
        tasks.extend(shipping_tasks(order, customer or order.temporary_customer_name, user, queues))
    tasks.extend(await load_additional_tasks(db, user, company))
    return tasks


def build_page(tasks: list[WorkbenchTask], user, *, acceptance_mode: bool,
               scope: TaskScope = "mine", module: TaskModule | None = None, search: str = "",
               due: DueFilter = "all", page: int = 1, page_size: int = 15,
               now: datetime | None = None) -> WorkbenchPage:
    now = now or datetime.now(BUSINESS_TIMEZONE)
    today = now.astimezone(BUSINESS_TIMEZONE).date()
    keyword = search.strip().casefold()
    matching = [task for task in tasks if (not module or task.module == module) and
                (not keyword or keyword in " ".join(filter(None, (task.document_no, task.title, task.summary, task.customer))).casefold())]
    counts = WorkbenchCounts(**{key: sum(t.scope == key for t in matching) for key in ("mine", "team", "created")})
    selected = [task for task in matching if task.scope == scope]
    actionable = [task for task in selected if task.actionable and not task.blocked_reason]
    stats = WorkbenchStats(pending=len(actionable), today=sum(t.due_date == today for t in actionable),
                           overdue=sum(t.due_date is not None and t.due_date < today for t in actionable),
                           blocked=sum(bool(task.blocked_reason) or not task.actionable for task in selected))
    selected = [t for t in selected if due == "all" or
                (due == "today" and t.actionable and not t.blocked_reason and t.due_date == today) or
                (due == "overdue" and t.actionable and not t.blocked_reason and t.due_date is not None and t.due_date < today) or
                (due == "undated" and t.due_date is None) or
                (due == "blocked" and (t.blocked_reason or not t.actionable))]
    selected.sort(key=lambda t: (not (t.due_date and t.due_date < today), not t.urgent,
                                  t.due_date or date.max, t.key))
    total = len(selected)
    page = min(page, max(1, (total + page_size - 1) // page_size))
    return WorkbenchPage(
        identity=WorkbenchIdentity(id=user.id, name=user.real_name or user.username,
                                   department=user.dept, position=user.position,
                                   administrator=user.role_level >= 3, acceptance_mode=acceptance_mode,
                                   is_switched=getattr(user, "is_switched", False)),
        today=today, generated_at=now, counts=counts, stats=stats,
        items=selected[(page - 1) * page_size:page * page_size], total=total, page=page, page_size=page_size,
        coverage=coverage())
