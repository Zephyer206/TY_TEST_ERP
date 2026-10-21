from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

Company = Literal['tianyue', 'gaibo']
Action = Literal['edit', 'confirm', 'return', 'prepare', 'start', 'finish_step', 'submit', 'inspect', 'move']

class DefectDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer: str = Field(max_length=300)
    partNo: str = Field(max_length=200)
    partName: str = Field(max_length=300)
    batchNo: str = Field(default='', max_length=300)
    source: str = Field(default='', max_length=60)
    quantity: StrictInt = Field(ge=1, le=1000000000)
    quantityVerified: StrictBool = True
    description: str = Field(max_length=6000)
    disposition: Literal['', 'rework', 'sorting', 'scrap', 'other'] = ''
    treatment: str = Field(default='', max_length=6000)
    assignee: str = Field(default='', max_length=300)
    plannedDate: str = Field(default='', max_length=10)
    week: str = Field(default='', max_length=10)
    trace: dict[str, Any] = Field(default_factory=dict)
    quantityLots: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    planSteps: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    inspectionItems: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    release: dict[str, Any] = Field(default_factory=dict)

class RecordAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=1)
    action: Action
    payload: dict[str, Any] = Field(default_factory=dict)

class MoldDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default='', max_length=120)
    company: Company
    revision: StrictInt | None = Field(default=None, ge=1)
    partNo: str = Field(max_length=200)
    location: str = Field(default='', max_length=300)
    availability: Literal['available', 'maintenance', 'unavailable']
    photos: list[str] = Field(default_factory=list, max_length=4)
    defectIds: list[str] = Field(default_factory=list, max_length=1000)

class WorkspaceResponse(BaseModel):
    records: list[dict[str, Any]]
    molds: list[dict[str, Any]]
    workbook: dict[str, Any] | None
    actor: dict[str, Any]
    serverTime: str
    createdId: str | None = None
