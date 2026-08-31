"""TraceMind canonical trace event schemas."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Supported distributed trace event types."""

    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    SERVICE_STARTED = "SERVICE_STARTED"
    SERVICE_COMPLETED = "SERVICE_COMPLETED"
    SERVICE_FAILED = "SERVICE_FAILED"
    SERVICE_TIMEOUT = "SERVICE_TIMEOUT"
    RETRY_STARTED = "RETRY_STARTED"
    RETRY_COMPLETED = "RETRY_COMPLETED"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    DATABASE_QUERY = "DATABASE_QUERY"
    QUEUE_PUBLISHED = "QUEUE_PUBLISHED"
    QUEUE_CONSUMED = "QUEUE_CONSUMED"


class EventStatus(StrEnum):
    """Execution status for an event."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    RETRY = "RETRY"
    PENDING = "PENDING"


class TraceEvent(BaseModel):
    """Canonical trace event emitted during workflow execution."""

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    tenant_id: str = Field(default="tenant_system", description="Owning multi-tenant organization ID")
    execution_id: str = Field(..., description="Unique workflow execution run ID")
    workflow_id: str = Field(..., description="Workflow definition identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Event emission timestamp in UTC",
    )
    service: str = Field(..., description="Name of the executing service")
    operation: str = Field(..., description="Operation/step performed")
    event_type: EventType = Field(..., description="Event classification")
    status: EventStatus = Field(default=EventStatus.SUCCESS, description="Execution outcome")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Operation duration in milliseconds")
    parent_event_id: str | None = Field(default=None, description="Parent trace event ID")
    correlation_id: str | None = Field(default=None, description="Distributed correlation ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary trace context")

