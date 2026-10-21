"""Read-only personal workbench contract, derived from business records."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskScope = Literal["mine", "team", "created"]
TaskModule = Literal["production", "shipping"]
DueFilter = Literal["all", "today", "overdue", "undated"]


class WorkbenchIdentity(BaseModel):
    id: int
    name: str
    department: str
    position: str | None = None
    administrator: bool
    acceptance_mode: bool


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


class WorkbenchCounts(BaseModel):
    mine: int = 0
    team: int = 0
    created: int = 0


class WorkbenchStats(BaseModel):
    pending: int = 0
    today: int = 0
    overdue: int = 0


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
