"""Claim derived tasks without granting access or changing business status."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.workbench_assignment import WorkbenchAssignment, WorkbenchAssignmentEvent


def is_manager(user) -> bool:
    if getattr(user, "is_switched", False):
        return False
    if user.role_level >= 3:
        return True
    position = (user.position or "").casefold()
    return user.role_level >= 2 and any(marker in position for marker in (
        "主管", "经理", "组长", "负责人", "部长", "manager", "supervisor", "team lead", "director",
    ))


def _department(department: str) -> str:
    value = (department or "").strip().casefold()
    for canonical, aliases in {
        "production": {"prod", "production", "生产", "生产部", "制造"},
        "warehouse": {"warehouse", "仓库", "原料仓库", "仓储"},
        "development": {"design", "engineering", "development", "开发", "开发部", "研发"},
        "sales": {"sales", "business", "业务", "业务部"},
        "quality": {"quality", "qc", "品管", "品管部"},
    }.items():
        if value in aliases:
            return canonical
    return value


def storage_key(task) -> str:
    # Existing global production/shipping records keep one ownership record.
    return f"{getattr(task, 'company', None) or 'global'}|{task.key}"


def _actionable(task) -> bool:
    return getattr(task, "actionable", True) and not getattr(task, "blocked_reason", None)


async def _find_task(db, user, task_key: str, company: str, task_loader, *, require_actionable: bool = True):
    tasks = await task_loader(db, user, company=company)
    task = next((item for item in tasks if item.key == task_key and item.scope == "team"), None)
    if task is None:
        raise HTTPException(404, "事项已完成、已转交或不在当前岗位范围，请刷新待办。")
    if require_actionable and not _actionable(task):
        raise HTTPException(409, "事项仍在等待前序条件，暂不能认领或指派。")
    return task


async def _lock_source(db, task) -> None:
    """Serialize ownership checks against the actual source row update."""
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.nonconforming import NonconformingRecord
    from app.models.production import ProductionPlan
    from app.models.quote_group import QuoteGroup
    from app.models.shipping_order import ShippingOrder, ShippingOrderLine

    model = {"production_plan": ProductionPlan, "shipping_order": ShippingOrder,
             "customer_inquiry": CustomerInquiry, "quote_group": QuoteGroup,
             "nonconforming_record": NonconformingRecord}.get(task.source_type)
    if model is None:
        return
    source_id = task.source_id if task.source_type == "nonconforming_record" else int(task.source_id)
    if task.source_type == "quote_group":
        # Technical review writes the inquiry before its quote group. Match
        # that order so a concurrent handoff cannot deadlock on reverse locks.
        inquiry_id = (await db.execute(select(QuoteGroup.inquiry_id).where(QuoteGroup.id == source_id))).scalar_one_or_none()
        if inquiry_id is not None:
            await db.execute(select(CustomerInquiry).where(CustomerInquiry.id == inquiry_id)
                             .with_for_update().execution_options(populate_existing=True))
    source = (await db.execute(select(model).where(model.id == source_id).with_for_update()
                               .execution_options(populate_existing=True))).scalar_one_or_none()
    if source is None:
        raise HTTPException(409, "原单已被移除，请刷新待办。")
    if task.source_type == "shipping_order" and task.source_line_id:
        await db.execute(select(ShippingOrderLine).where(ShippingOrderLine.id == int(task.source_line_id))
                         .with_for_update().execution_options(populate_existing=True))


async def eligible_assignees(db, user, task_key: str, company: str, task_loader) -> list[dict]:
    if not is_manager(user):
        raise HTTPException(403, "只有获授权主管可以查看可指派人员。")
    task = await _find_task(db, user, task_key, company, task_loader)
    users = (await db.execute(select(User).order_by(User.real_name, User.id))).scalars().all()
    candidates = []
    for candidate in users:
        if not getattr(candidate, "is_active", True):
            continue
        if user.role_level < 3 and _department(candidate.dept) != _department(user.dept):
            continue
        if can_receive_task(task, candidate, company):
            candidates.append({"id": candidate.id, "name": candidate.real_name or candidate.username,
                               "department": candidate.dept, "position": candidate.position})
    return candidates


def can_receive_task(task, user, company: str) -> bool:
    """Check source queue eligibility without fetching every user's workbench.

    The caller has already derived this current task from its authorized source.
    Reuse the same role predicates that create team queues; neither title text
    nor display department labels grant access. Mutations still re-read source
    eligibility under its row lock before changing any assignment.
    """
    from app.services.workbench_service import role_queues
    from app.services.workbench_sources import DEVELOPMENT, SALES, _department_queue, _nc_action

    if task.scope != "team" or not _actionable(task) or getattr(user, "is_switched", False):
        return False
    if task.company is not None and task.company != company:
        return False
    if task.source_type == "production_plan":
        return user.role_level >= 2 and task.step_key in {"materials", "scheduling"} and task.step_key in role_queues(user)
    if task.source_type == "shipping_order":
        queue = {"label": "label", "cancel_label": "label", "shipping": "shipping"}.get(task.step_key)
        return queue is not None and queue in role_queues(user)
    if task.source_type == "customer_inquiry":
        return task.step_key == "technical_review" and _department_queue(user, DEVELOPMENT)
    if task.source_type == "quote_group":
        return task.step_key == "pricing" and _department_queue(user, SALES)
    if task.source_type == "nonconforming_record":
        if task.company not in {"tianyue", "gaibo"}:
            return False
        action = {"confirm": "confirm", "verify_import": "confirm", "prepare": "prepare",
                  "start": "start", "submit": "submit", "inspect": "inspect"}.get(task.step_key)
        if task.step_key.startswith("step:") and len(task.step_key) > len("step:"):
            action = "finish_step"
        return action is not None and _nc_action(user, action)
    return False


async def apply_assignments(db, tasks: list, user) -> list:
    team = [task for task in tasks if task.scope == "team"]
    if not team:
        return tasks
    keys = [storage_key(task) for task in team]
    rows = (await db.execute(select(WorkbenchAssignment).where(WorkbenchAssignment.task_key.in_(keys))
                             .execution_options(populate_existing=True))).scalars().all()
    records = {record.task_key: record for record in rows}
    ids = {record.assignee_id for record in rows if record.assignee_id is not None}
    users = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all() if ids else []
    names = {person.id: person.real_name or person.username for person in users}
    result = []
    preview = getattr(user, "is_switched", False)
    manager = is_manager(user)
    for task in tasks:
        if task.scope != "team":
            result.append(task)
            continue
        record = records.get(storage_key(task))
        # The stable task key identifies the workflow step. Draft/progress edits
        # update the source revision but do not remove its current handler.
        assignee_id = record.assignee_id if record is not None else None
        # Removed accounts cannot retain actionable ownership.
        if assignee_id not in names:
            assignee_id = None
        state = record.state if assignee_id is not None else "unassigned"
        enriched = task.model_copy(update={
            "assignee_id": assignee_id, "assignee_name": names.get(assignee_id),
            "assignment_state": state, "assignment_version": record.version if record else 0,
            "can_claim": not preview and assignee_id is None and _actionable(task),
            "can_release": not preview and assignee_id is not None and (assignee_id == user.id or manager),
            "can_assign": not preview and manager and _actionable(task),
        })
        result.append(enriched)
        if not preview and assignee_id == user.id:
            result.append(enriched.model_copy(update={"scope": "mine"}))
    return result


async def change_assignment(db, user, request, action: str, task_loader) -> dict:
    if getattr(user, "is_switched", False):
        raise HTTPException(403, "部门预览为只读；返回本人身份后才能办理任务分派。")
    if action == "assign" and not is_manager(user):
        raise HTTPException(403, "只有获授权主管可以指派任务。")
    task = await _find_task(db, user, request.task_key, request.company, task_loader,
                            require_actionable=action != "release")
    await _lock_source(db, task)
    task = await _find_task(db, user, request.task_key, request.company, task_loader,
                            require_actionable=action != "release")
    if task.source_revision != request.source_revision:
        raise HTTPException(409, "原单已更新，请刷新待办后重试。")
    key = storage_key(task)
    record = (await db.execute(select(WorkbenchAssignment).where(WorkbenchAssignment.task_key == key)
                               .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    version = record.version if record else 0
    if version != request.expected_version:
        raise HTTPException(409, "事项归属已被其他人更新，请刷新待办。")
    previous = record.assignee_id if record is not None else None
    if action == "claim":
        if previous is not None:
            raise HTTPException(409, "事项已被认领或指派，请刷新待办。")
        target_id, state = user.id, "claimed"
    elif action == "release":
        if previous is None:
            raise HTTPException(409, "事项当前无人受理，请刷新待办。")
        if previous != user.id and not is_manager(user):
            raise HTTPException(403, "只能退回本人受理的事项。")
        target_id, state = None, "unassigned"
    else:
        target_id = request.assignee_id
        state = "assigned" if target_id is not None else "unassigned"
        if target_id is not None:
            target = await db.get(User, target_id)
            if target is None or not getattr(target, "is_active", True):
                raise HTTPException(422, "受理人不存在或不可用。")
            if user.role_level < 3 and _department(user.dept) != _department(target.dept):
                raise HTTPException(403, "只能指派给本部门具备办理权限的人员。")
            try:
                await _find_task(db, target, task.key, request.company, task_loader)
            except HTTPException:
                raise HTTPException(403, "受理人没有该事项的岗位办理权限。") from None
        if previous == target_id:
            raise HTTPException(409, "事项归属未改变，请刷新待办。")
    now = datetime.utcnow()
    values = dict(source_revision=task.source_revision, assignee_id=target_id, state=state,
                  version=version + 1, updated_by=user.id, updated_at=now)
    if record is None:
        try:
            async with db.begin_nested():
                record = WorkbenchAssignment(task_key=key, **values)
                db.add(record)
                await db.flush()
        except IntegrityError:
            raise HTTPException(409, "事项刚被其他人更新，请刷新待办。") from None
    else:
        changed = await db.execute(update(WorkbenchAssignment)
                                   .where(WorkbenchAssignment.id == record.id, WorkbenchAssignment.version == version)
                                   .values(**values).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, "事项归属已被其他人更新，请刷新待办。")
    db.add(WorkbenchAssignmentEvent(task_key=key, source_revision=task.source_revision, action=action,
                                   version=version + 1, actor_id=user.id, actor_name=user.real_name or user.username,
                                   previous_assignee_id=previous, assignee_id=target_id, created_at=now))
    await db.flush()
    target_name = None
    if target_id is not None:
        target = await db.get(User, target_id)
        target_name = target.real_name or target.username if target else None
    return {"task_key": task.key, "version": version + 1, "assignee_id": target_id,
            "assignee_name": target_name, "assignment_state": state}
