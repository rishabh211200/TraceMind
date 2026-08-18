"""Pydantic v2 schemas for service catalog, baseline profiles, and graph topology."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ServiceResponse(BaseModel):
    """Registered microservice profile schema."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    service_type: str
    capacity: int
    baseline_latency_ms: float
    baseline_failure_rate: float
    timeout_ms: float
    max_retries: int
    retry_backoff_ms: float
    dependencies: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceUpdate(BaseModel):
    """Payload for modifying a service's baseline parameters."""

    capacity: int | None = Field(default=None, ge=1, le=10000)
    baseline_latency_ms: float | None = Field(default=None, ge=0.0)
    baseline_failure_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    timeout_ms: float | None = Field(default=None, ge=1.0)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    retry_backoff_ms: float | None = Field(default=None, ge=0.0)
    dependencies: list[Any] | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)


class ServiceLatencyStatsResponse(BaseModel):
    """Database-side latency percentile distribution response schema."""

    service: str
    count: int
    mean_latency_ms: float
    median_p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float


class ServiceHealthResponse(BaseModel):
    """Service operational reliability and error rate summary schema."""

    service: str
    total_events: int
    failure_count: int
    error_rate_percent: float
    retry_count: int
    retry_rate_percent: float
    timeout_count: int
    timeout_rate_percent: float
    latency: ServiceLatencyStatsResponse


class TopologyNode(BaseModel):
    """Graph topology node representing a service or infrastructure component."""

    id: str = Field(description="Service identifier")
    name: str = Field(description="Display name")
    type: str = Field(description="Service category (BUSINESS, CACHE, DATABASE, GATEWAY)")
    capacity: int = Field(description="Concurrency worker capacity")
    baseline_latency_ms: float = Field(description="Baseline response latency in ms")


class TopologyEdge(BaseModel):
    """Directed dependency edge between two services."""

    from_service: str = Field(description="Caller / upstream service")
    to_service: str = Field(description="Callee / downstream dependency")
    relationship_type: str = Field(
        description="Dependency type (HTTP_RPC, CACHE_LOOKUP, DB_QUERY, GATEWAY_CALL)"
    )
    call_weight: float = Field(default=1.0, description="Relative call frequency or weight")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceTopologyResponse(BaseModel):
    """Complete service graph topology response for graph visualizers."""

    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    total_services: int
    total_dependencies: int
