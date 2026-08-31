"""Domain schemas for chaos injection and incident tracking."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class IncidentScenario(StrEnum):
    """Synthetic chaos and failure injection scenarios."""

    TRAFFIC_SPIKE = "TRAFFIC_SPIKE"
    PAYMENT_LATENCY_DEGRADATION = "PAYMENT_LATENCY_DEGRADATION"
    DATABASE_LATENCY = "DATABASE_LATENCY"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    MEMORY_PRESSURE = "MEMORY_PRESSURE"
    RETRY_STORM = "RETRY_STORM"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    CASCADING_FAILURE = "CASCADING_FAILURE"


class Severity(StrEnum):
    """Incident severity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Incident(BaseModel):
    """Record of a synthetic incident with ground-truth causal information."""

    id: str = Field(default_factory=lambda: f"inc_{uuid4().hex[:10]}")
    tenant_id: str = Field(default="tenant_system", description="Owning multi-tenant organization ID")
    scenario_type: IncidentScenario = Field(..., description="Categorical incident scenario")
    severity: Severity = Field(default=Severity.MEDIUM, description="Impact severity")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Incident start timestamp"
    )
    ended_at: datetime | None = Field(default=None, description="Incident recovery timestamp")
    affected_services: list[str] = Field(
        default_factory=list, description="Services directly impacted"
    )
    ground_truth_root_cause: str = Field(
        ..., description="True causal factor for ML/reasoning evaluation"
    )
    description: str = Field(default="", description="Technical narrative of the incident")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Simulation injection parameters"
    )

