"""Workflow graph structures and execution tracking schemas."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ExecutionStatus(StrEnum):
    """Lifecycle status of a workflow execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class WorkflowNodeType(StrEnum):
    """Types of graph nodes in a workflow."""

    START = "START"
    SERVICE = "SERVICE"
    DECISION = "DECISION"
    PARALLEL = "PARALLEL"
    JOIN = "JOIN"
    END = "END"


class WorkflowNode(BaseModel):
    """A single operational or structural node within a workflow graph."""

    id: str = Field(..., description="Node identifier within the workflow")
    name: str = Field(..., description="Human-readable node name")
    node_type: WorkflowNodeType = Field(default=WorkflowNodeType.SERVICE)
    service_name: str | None = Field(
        default=None, description="Associated service name if applicable"
    )
    operation: str | None = Field(default=None, description="Operation to execute")
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    """A directed edge connecting workflow nodes."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    condition: str | None = Field(default=None, description="Conditional routing expression")
    weight: float = Field(default=1.0, ge=0.0, description="Routing probability or cost weight")


class WorkflowDefinition(BaseModel):
    """Structural definition of a distributed workflow graph."""

    id: str = Field(..., description="Unique workflow identifier (e.g. order_processing)")
    tenant_id: str = Field(default="tenant_system", description="Owning multi-tenant organization ID")
    name: str = Field(..., description="Display name of the workflow")
    version: str = Field(default="1.0.0", description="Semantic workflow version")
    description: str = Field(default="", description="Workflow operational description")
    nodes: list[WorkflowNode] = Field(default_factory=list, description="Workflow nodes")
    edges: list[WorkflowEdge] = Field(default_factory=list, description="Workflow edges")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )


class WorkflowExecution(BaseModel):
    """Record of a specific workflow execution instance."""

    id: str = Field(default_factory=lambda: f"exec_{uuid4().hex[:12]}")
    tenant_id: str = Field(default="tenant_system", description="Owning multi-tenant organization ID")
    workflow_definition_id: str = Field(..., description="Associated workflow definition ID")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Execution start timestamp"
    )
    completed_at: datetime | None = Field(
        default=None, description="Execution completion timestamp"
    )
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    total_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Aggregate workflow duration in ms"
    )
    retry_count: int = Field(default=0, ge=0, description="Total retries triggered across services")
    error_count: int = Field(default=0, ge=0, description="Total errors encountered")
    failure_reason: str | None = Field(default=None, description="Explanation if execution failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution run metadata")

