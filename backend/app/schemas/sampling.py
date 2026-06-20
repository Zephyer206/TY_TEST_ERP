"""Pydantic schemas for sampling task management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.sampling import SamplingTaskState


class SamplingTaskBase(BaseModel):
    """Base schema for sampling task."""

    part_id: int
    customer_id: int
    quote_id: Optional[int] = None
    sample_qty: int = Field(ge=1)
    order_date: datetime
    planned_completion_date: datetime


class SamplingTaskCreate(SamplingTaskBase):
    """Schema for creating a sampling task."""

    pass


class SamplingTaskUpdate(BaseModel):
    """Schema for updating a sampling task."""

    sample_qty: Optional[int] = Field(default=None, ge=1)
    planned_completion_date: Optional[datetime] = None
    is_urgent: Optional[bool] = None
    assigned_machine_id: Optional[int] = None


class SamplingTaskReview(BaseModel):
    """Schema for submitting review result."""

    passed: bool
    notes: Optional[str] = Field(default=None, max_length=500)


class SamplingTaskApprove(BaseModel):
    """Schema for boss approval."""

    approved: bool
    notes: Optional[str] = Field(default=None, max_length=500)


class SamplingTaskCancel(BaseModel):
    """Schema for cancelling a sampling task."""

    reason: str = Field(max_length=500)


class SamplingTaskResponse(SamplingTaskBase):
    """Schema for sampling task response."""

    id: int
    task_no: str
    state: SamplingTaskState
    actual_completion_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    is_urgent: bool
    review_notes: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    cancel_reason: Optional[str] = None
    approved_by: Optional[int] = None
    approver_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    assigned_machine_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SamplingTaskListResponse(BaseModel):
    """Schema for sampling task list (summary)."""

    id: int
    task_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    customer_id: int
    customer_name: Optional[str] = None
    state: SamplingTaskState
    sample_qty: int
    order_date: datetime
    planned_completion_date: datetime
    actual_completion_date: Optional[datetime] = None
    is_urgent: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SamplingKanbanResponse(BaseModel):
    """Schema for sampling kanban board."""

    id: int
    task_no: str
    part_id: int
    part_no: Optional[str] = None
    part_name: Optional[str] = None
    customer_id: int
    customer_name: Optional[str] = None
    state: SamplingTaskState
    sample_qty: int
    order_date: datetime
    planned_completion_date: datetime
    is_urgent: bool
    is_overdue: bool  # Computed field
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
