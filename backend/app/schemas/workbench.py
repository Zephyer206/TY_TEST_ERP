"""Read-only personal workbench contract, derived from business records."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskScope = Literal["mine", "team", "created"]
TaskModule = Literal["production", "shipping", "inquiry", "quote", "nonconforming"]
DueFilter = Literal["all", "today", "overdue", "undated", "blocked"]


class WorkbenchIdentity(BaseModel):
    id: int
    name: str
    department: str
    position: str | None = None
    administrator: bool
    acceptance_mode: bool
    is_switched: bool = False


class WorkbenchTask(BaseModel):
    key: str
    scope: TaskScope
    module: TaskModule
    document_no: str
    title: str
    summary: str
    customer: str | None = None
    role: str
    due_date: date | None = None
    urgent: bool = False
    updated_at: datetime | None = None
    route: str
    action_label: str = "去处理"
    source_type: str = ""
    source_id: str = ""
    source_line_id: str | None = None
    step_key: str = ""
    source_revision: str = ""
    company: str | None = None
    owner_department: str = ""
    owner_role: str = ""
    source_assignee: str | None = None
    assignee_id: int | None = None
    assignee_name: str | None = None
    assignment_version: int = 0
    assignment_state: Literal["unassigned", "claimed", "assigned"] = "unassigned"
    can_claim: bool = False
    can_release: bool = False
    can_assign: bool = False
    actionable: bool = True
    blocked_reason: str | None = None
    completion_requirements: list[str] = Field(default_factory=list)
    next_role: str | None = None


class WorkbenchCounts(BaseModel):
    mine: int = 0
    team: int = 0
    created: int = 0


class WorkbenchStats(BaseModel):
    pending: int = 0
    today: int = 0
    overdue: int = 0
    blocked: int = 0


class WorkbenchCoverage(BaseModel):
    key: str
    label: str
    status: Literal["active", "not_connected"]
    description: str


class WorkbenchPage(BaseModel):
    identity: WorkbenchIdentity
    today: date
    generated_at: datetime
    counts: WorkbenchCounts
    stats: WorkbenchStats
    items: list[WorkbenchTask] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    coverage: list[WorkbenchCoverage] = Field(default_factory=list)
