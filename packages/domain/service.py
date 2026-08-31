"""Domain schemas representing distributed services and their operational baselines."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ServiceDefinition(BaseModel):
    """Definition and performance baseline for a distributed service."""

    id: str = Field(default_factory=lambda: f"srv_{uuid4().hex[:8]}")
    tenant_id: str = Field(
        default="tenant_system", description="Owning multi-tenant organization ID"
    )
    name: str = Field(..., description="Unique service name (e.g. auth-service)")
    version: str = Field(default="1.0.0", description="Semantic service version")
    capacity: int = Field(default=100, description="Max concurrent request capacity")
    baseline_latency_ms: float = Field(
        default=50.0, ge=0.0, description="Expected nominal latency in ms"
    )
    baseline_failure_rate: float = Field(
        default=0.01, ge=0.0, le=1.0, description="Nominal failure probability [0.0 - 1.0]"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="List of downstream dependency service names"
    )
    retry_limit: int = Field(default=3, ge=0, description="Maximum automated retries")
    timeout_ms: float = Field(default=2000.0, ge=0.0, description="Client timeout threshold in ms")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom service metadata")
