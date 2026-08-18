"""Pydantic v2 schemas for workflow topology definitions and statistics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowNode(BaseModel):
    """Workflow DAG step node schema."""

    id: str = Field(description="Unique node identifier within workflow DAG")
    name: str = Field(description="Descriptive step name")
    service: str = Field(description="Target microservice name")
    operation: str = Field(description="Operation / method name")
    timeout_ms: float | None = Field(default=None, description="Optional step timeout override")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Step metadata")


class WorkflowEdge(BaseModel):
    """Workflow DAG directed transition edge."""

    from_node: str = Field(description="Source node ID")
    to_node: str = Field(description="Target destination node ID")
    condition: str | None = Field(default=None, description="Optional branching condition")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Edge metadata")


class WorkflowDefinitionCreate(BaseModel):
    """Payload for registering a new workflow DAG definition."""

    id: str = Field(min_length=1, max_length=64, description="Unique workflow definition ID")
    name: str = Field(min_length=1, max_length=128, description="Human-readable workflow name")
    version: str = Field(default="1.0.0", description="Semantic version string")
    description: str | None = Field(default=None, description="Workflow functional description")
    nodes: list[WorkflowNode] = Field(min_length=1, description="Ordered list of DAG nodes")
    edges: list[WorkflowEdge] = Field(default_factory=list, description="Directed DAG edges")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Workflow metadata")


class WorkflowDefinitionUpdate(BaseModel):
    """Payload for updating an existing workflow definition."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    version: str | None = Field(default=None)
    description: str | None = Field(default=None)
    nodes: list[WorkflowNode] | None = Field(default=None)
    edges: list[WorkflowEdge] | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)


class WorkflowDefinitionResponse(BaseModel):
    """Complete workflow definition schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: str
    description: str | None
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    node_count: int
    edge_count: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowStatsResponse(BaseModel):
    """Aggregate execution statistics for a workflow definition."""

    workflow_definition_id: str
    total_executions: int
    completed_count: int
    failed_count: int
    timeout_count: int
    success_rate_percent: float
    error_rate_percent: float
    mean_duration_ms: float
    median_p50_duration_ms: float
    p95_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    incident_affected_count: int
