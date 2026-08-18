"""Pydantic v2 schemas for simulation control and chaos injection."""

from typing import Any

from pydantic import BaseModel, Field


class ChaosScenarioInfo(BaseModel):
    """Chaos scenario metadata schema."""

    scenario_type: str = Field(description="Unique scenario enum identifier")
    name: str = Field(description="Human-readable scenario name")
    description: str = Field(description="Scenario description and failure dynamics")
    severity: str = Field(description="Incident severity level (LOW, MEDIUM, HIGH, CRITICAL)")
    affected_services: list[str] = Field(description="Services degraded during scenario")
    ground_truth_root_cause: str = Field(description="Deterministic root cause explanation")
    default_parameters: dict[str, Any] = Field(description="Default degradation multipliers")


class SimulationGenerateRequest(BaseModel):
    """Payload for triggering synthetic workflow simulation."""

    workflow_count: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of synthetic workflows to simulate (1 to 10,000)",
    )
    seed: int | None = Field(
        default=None,
        description="Deterministic random seed (optional; random if omitted)",
    )
    incident_scenario: str | None = Field(
        default=None,
        description="Specific chaos scenario to inject (e.g. DATABASE_LATENCY, PAYMENT_LATENCY_DEGRADATION)",
    )
    arrival_rate_rps: float = Field(
        default=10.0,
        gt=0.0,
        le=1000.0,
        description="Poisson workflow arrival rate in requests per second",
    )
    persist_to_db: bool = Field(
        default=True,
        description="Whether to persist generated executions and spans into PostgreSQL/TimescaleDB",
    )


class SimulationGenerateResponse(BaseModel):
    """Summary response from synthetic simulation run."""

    seed: int
    workflows_requested: int
    executions_generated: int
    events_generated: int
    incidents_generated: int
    generation_wall_time_ms: float
    persisted_to_db: bool
    persisted_executions_count: int
    persisted_events_count: int
    persistence_wall_time_ms: float | None = None
    summary_statistics: dict[str, Any]


class ChaosInjectionRequest(BaseModel):
    """Payload for targeted chaos injection experiment."""

    scenario_type: str = Field(
        description="Chaos scenario identifier (e.g. DATABASE_LATENCY, SERVICE_FAILURE, RETRY_STORM)"
    )
    workflow_count: int = Field(
        default=100, ge=1, le=5000, description="Workflow count during chaos experiment"
    )
    seed: int | None = Field(default=None, description="Optional deterministic seed")
    arrival_rate_rps: float = Field(default=10.0, gt=0.0, le=1000.0)
    parameters: dict[str, Any] | None = Field(
        default=None, description="Optional custom override parameters"
    )
    persist_to_db: bool = Field(default=True, description="Whether to persist chaos dataset")


class ChaosInjectionResponse(BaseModel):
    """Result of targeted chaos injection run."""

    incident_id: str
    scenario_type: str
    affected_services: list[str]
    ground_truth_root_cause: str
    total_executions: int
    executions_affected: int
    mean_latency_ms: float
    error_rate_percent: float
    retry_rate_percent: float
    persisted_to_db: bool
