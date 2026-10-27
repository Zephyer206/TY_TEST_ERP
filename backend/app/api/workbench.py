"""Server-scoped queues and auditable task ownership."""

from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.schemas.admin import DEPT_ROLE_MAPPINGS
from app.schemas.workbench import DueFilter, TaskModule, TaskScope, WorkbenchPage
from app.services import admin_service
from app.services.workbench_assignment_service import apply_assignments, change_assignment, eligible_assignees
from app.services.workbench_service import build_page, load_tasks

router = APIRouter(prefix="/workbench", tags=["Workbench"])
Company = Literal["tianyue", "gaibo"]


class AssignmentRequest(BaseModel):
    task_key: str = Field(min_length=1, max_length=200)
    source_revision: str = Field(max_length=300)
    expected_version: int = Field(ge=0)
    company: Company = "tianyue"


class AssignRequest(AssignmentRequest):
    assignee_id: int | None = Field(default=None, ge=1)


class AssignmentResponse(BaseModel):
    task_key: str
    version: int
    assignee_id: int | None
    assignee_name: str | None
    assignment_state: Literal["unassigned", "claimed", "assigned"]


class Assignee(BaseModel):
    id: int
    name: str
    department: str
    position: str | None


class AssigneesResponse(BaseModel):
    items: list[Assignee]


async def effective_actor(db, user):
    """Apply the existing LV4 preview context only to this workbench."""
    if user.role_level < 4:
        return user
    switched = await admin_service.get_active_context_switch(db, user.id)
    role = admin_service.get_effective_role(user, switched)
    if not role["is_switched"]:
        return user
    return SimpleNamespace(id=user.id, username=user.username, real_name=user.real_name,
                           dept=role["dept"], role_level=role["role_level"],
                           position=DEPT_ROLE_MAPPINGS.get(role["dept"], {}).get("role_name", "部门预览"),
                           is_tech=False, is_switched=True)


@router.get("", response_model=WorkbenchPage)
async def get_workbench(
    db: DbSession, current_user: CurrentUser,
    scope: TaskScope = "mine", module: TaskModule | None = None,
    search: str = Query(default="", max_length=120), due: DueFilter = "all",
    page: int = Query(default=1, ge=1), page_size: int = Query(default=15, ge=1, le=100),
    company: Company = "tianyue",
) -> WorkbenchPage:
    actor = await effective_actor(db, current_user)
    tasks = await load_tasks(db, actor, company=company)
    return build_page(await apply_assignments(db, tasks, actor), actor,
                      acceptance_mode=settings.AUTH_DISABLED, scope=scope, module=module,
                      search=search, due=due, page=page, page_size=page_size)


@router.get("/tasks/assignees", response_model=AssigneesResponse)
async def get_assignees(
    db: DbSession, current_user: CurrentUser,
    task_key: str = Query(min_length=1, max_length=200), company: Company = "tianyue",
) -> AssigneesResponse:
    actor = await effective_actor(db, current_user)
    return AssigneesResponse(items=await eligible_assignees(db, actor, task_key, company, load_tasks))


@router.post("/tasks/claim", response_model=AssignmentResponse)
async def claim_task(request: AssignmentRequest, db: DbSession, current_user: CurrentUser):
    actor = await effective_actor(db, current_user)
    return await change_assignment(db, actor, request, "claim", load_tasks)


@router.post("/tasks/release", response_model=AssignmentResponse)
async def release_task(request: AssignmentRequest, db: DbSession, current_user: CurrentUser):
    actor = await effective_actor(db, current_user)
    return await change_assignment(db, actor, request, "release", load_tasks)


@router.post("/tasks/assign", response_model=AssignmentResponse)
async def assign_task(request: AssignRequest, db: DbSession, current_user: CurrentUser):
    actor = await effective_actor(db, current_user)
    return await change_assignment(db, actor, request, "assign", load_tasks)
