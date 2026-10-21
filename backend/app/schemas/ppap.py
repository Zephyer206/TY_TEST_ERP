"""Validated PPAP commands. Status is maintained on a whole submission."""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Company = Literal['tianyue', 'gaibo']
SubmissionStatus = Literal['submitted', 'supplement', 'temporary', 'approved', 'rejected']


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class LinkInput(Command):
    key: str = Field(min_length=1, max_length=80)
    drawing_version: str = Field(default='', max_length=100)
    tooling_no: str = Field(default='', max_length=200)
    mold_type: str = Field(default='', max_length=100)


class ArchiveInput(Command):
    name: str = Field(min_length=1, max_length=500)
    customer_key: str = Field(min_length=1, max_length=80)
    owner: str = Field(min_length=1, max_length=100)
    planned_date: Optional[date] = None
    remark: str = Field(default='', max_length=6000)
    links: list[LinkInput] = Field(default_factory=list, max_length=200)


class ArchiveUpdate(ArchiveInput):
    revision: int = Field(ge=1)


class FolderInput(Command):
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    parent_id: Optional[str] = None


class FolderRename(Command):
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)


class SubmissionInput(Command):
    revision: int = Field(ge=1)
    submitted_date: Optional[date] = None
    remark: str = Field(default='', max_length=6000)


class FeedbackInput(Command):
    revision: int = Field(ge=1)
    status: SubmissionStatus
    feedback: str = Field(default='', max_length=6000)
    approved_date: Optional[date] = None
    valid_until: Optional[date] = None
    conditions: str = Field(default='', max_length=6000)
    evidence_version_id: Optional[str] = None
