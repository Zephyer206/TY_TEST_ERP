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
        tasks.append(WorkbenchTask(key=f"plan:{plan.id}:team", scope="team", title=stage,
                                   role="资材" if queue == "materials" else "生产计划", **base))
    if plan.created_by == user.id and user.role_level >= 2:
        tasks.append(WorkbenchTask(key=f"plan:{plan.id}:created", scope="created", title=stage,
                                   role="流程跟进", action_label="查看进度", **base))
    return tasks


def shipping_tasks(order, customer, user, queues: set[str]) -> list[WorkbenchTask]:
    tasks = []
    route = f"/shipping-orders/{order.id}"
    base = dict(module="shipping", document_no=order.order_no, customer=customer,
                route=route, updated_at=order.last_modified_at or order.created_at)
    if order.status == "draft":
        if order.created_by == user.id:
            tasks.append(WorkbenchTask(key=f"order:{order.id}:draft", scope="mine", title="提交发货订单",
                                       summary=order.po_no or "订单草稿", role="创建人", **base))
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
    return tasks


async def load_tasks(db, user) -> list[WorkbenchTask]:
    queues = role_queues(user)
    tasks = []
    if user.role_level >= 2:
        query = (select(ProductionPlan, Part, Customer.name)
                 .outerjoin(Part, Part.id == ProductionPlan.part_id)
                 .outerjoin(Customer, Customer.id == Part.customer_id)
                 .where(or_(ProductionPlan.status.is_(None), ProductionPlan.status.notin_(PLAN_TERMINAL))))
        if not queues.intersection({"materials", "scheduling"}):
            query = query.where(ProductionPlan.created_by == user.id)
        for plan, part, customer in (await db.execute(query)).all():
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
    for order, customer in (await db.execute(query)).all():
        tasks.extend(shipping_tasks(order, customer or order.temporary_customer_name, user, queues))
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
    stats = WorkbenchStats(pending=len(selected), today=sum(t.due_date == today for t in selected),
                           overdue=sum(t.due_date is not None and t.due_date < today for t in selected))
    selected = [t for t in selected if due == "all" or
                (due == "today" and t.due_date == today) or
                (due == "overdue" and t.due_date is not None and t.due_date < today) or
                (due == "undated" and t.due_date is None)]
    selected.sort(key=lambda t: (not (t.due_date and t.due_date < today), not t.urgent,
                                  t.due_date or date.max, t.key))
    total = len(selected)
    page = min(page, max(1, (total + page_size - 1) // page_size))
    return WorkbenchPage(
        identity=WorkbenchIdentity(id=user.id, name=user.real_name or user.username,
                                   department=user.dept, position=user.position,
                                   administrator=user.role_level >= 3, acceptance_mode=acceptance_mode),
        today=today, generated_at=now, counts=counts, stats=stats,
        items=selected[(page - 1) * page_size:page * page_size], total=total, page=page, page_size=page_size)
