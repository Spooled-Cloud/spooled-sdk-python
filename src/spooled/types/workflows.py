"""
Workflow-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WorkflowStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class WorkflowResponse(BaseModel):
    """Workflow response model."""

    id: str
    name: str
    status: WorkflowStatus
    total_jobs: int | None = None  # Not always returned
    completed_jobs: int | None = None  # Not always returned
    failed_jobs: int | None = None  # Not always returned
    progress_percent: float | None = None  # Not always returned
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class WorkflowJobDefinition(BaseModel):
    """Job definition within a workflow."""

    key: str = Field(..., min_length=1, max_length=100)
    queue_name: str = Field(..., min_length=1, max_length=100)
    payload: dict[str, Any]
    depends_on: list[str] | None = None
    dependency_mode: Literal["all", "any"] | None = None
    priority: int | None = Field(default=None, ge=-100, le=100)
    max_retries: int | None = Field(default=None, ge=0, le=100)
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)

    model_config = {"extra": "forbid"}


class WorkflowJobMapping(BaseModel):
    """Mapping from job key to job ID."""

    key: str
    job_id: str


class CreateWorkflowParams(BaseModel):
    """Parameters for creating a workflow."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    jobs: list[WorkflowJobDefinition]
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class CreateWorkflowResponse(BaseModel):
    """Response from creating a workflow."""

    workflow_id: str
    job_ids: list[WorkflowJobMapping]


class ListWorkflowsParams(BaseModel):
    """Parameters for listing workflows."""

    status: WorkflowStatus | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class JobDependency(BaseModel):
    """A job dependency."""

    job_id: str
    status: str
    completed: bool


class JobWithDependencies(BaseModel):
    """Job with its dependencies."""

    job_id: str
    dependencies: list[JobDependency]
    dependency_mode: Literal["all", "any"]
    dependencies_met: bool


class AddDependenciesParams(BaseModel):
    """Parameters for adding dependencies to a job."""

    dependency_job_ids: list[str]
    dependency_mode: Literal["all", "any"] = Field(default="all")

    model_config = {"extra": "forbid"}


class AddDependenciesResponse(BaseModel):
    """Response from adding dependencies."""

    job_id: str
    added_count: int


class WorkflowJob(BaseModel):
    """A job within a workflow."""

    id: str
    key: str
    queue_name: str
    status: str
    payload: dict[str, Any]
    priority: int = 0
    depends_on: list[str] | None = None
    dependency_mode: Literal["all", "any"] | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowJobStatus(BaseModel):
    """Status summary of a job within a workflow."""

    key: str
    job_id: str
    status: str
    progress: float | None = None
