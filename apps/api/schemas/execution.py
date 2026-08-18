"""Pydantic v2 schemas for workflow executions, trace events, and DAG trees."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.common import PaginationMeta


class ExecutionSummaryResponse(BaseModel):
    """Workflow execution record summary response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_definition_id: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float
    status: str
    retry_count: int
    error_count: int
    failure_reason: str | None
    incident_id: str | None
    is_incident_affected: bool
    metadata: dict[str, Any]


class TraceEventResponse(BaseModel):
    """Individual span lifecycle event schema."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    timestamp: datetime
    execution_id: str
    workflow_id: str
    service: str
    operation: str
    event_type: str
    status: str
    latency_ms: float
    parent_event_id: str | None
    correlation_id: str | None
    metadata: dict[str, Any]


class TraceTreeNodeResponse(BaseModel):
    """Reconstructed recursive DAG tree node with child spans."""

    event_id: str
    service: str
    operation: str
    event_type: str
    status: str
    latency_ms: float
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    children: list["TraceTreeNodeResponse"] = Field(default_factory=list)


class ExecutionListResponse(BaseModel):
    """Paginated list of workflow executions."""

    items: list[ExecutionSummaryResponse]
    pagination: PaginationMeta
