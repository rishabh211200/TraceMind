"""Configuration models and default service profiles for TraceSim."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.domain.incident import IncidentScenario


class LatencyDistributionType(StrEnum):
    """Supported statistical distributions for service latency."""

    LOGNORMAL = "LOGNORMAL"
    GAMMA = "GAMMA"
    NORMAL = "NORMAL"


class ServiceConfig(BaseModel):
    """Operational and performance baseline parameters for a simulated service."""

    name: str = Field(..., description="Service identifier")
    baseline_latency_ms: float = Field(
        default=50.0, ge=1.0, description="Nominal mean latency in ms"
    )
    latency_sigma: float = Field(default=0.35, ge=0.01, description="Lognormal variance parameter")
    distribution_type: LatencyDistributionType = Field(default=LatencyDistributionType.LOGNORMAL)
    spike_probability: float = Field(
        default=0.02, ge=0.0, le=1.0, description="Natural tail spike rate"
    )
    spike_multiplier: float = Field(
        default=3.5, ge=1.0, description="Latency multiplier during natural spike"
    )
    capacity: int = Field(
        default=100, ge=1, description="Max concurrent request processing capacity"
    )
    baseline_failure_rate: float = Field(
        default=0.005, ge=0.0, le=1.0, description="Base transient error rate"
    )
    timeout_ms: float = Field(default=2500.0, ge=10.0, description="Client timeout threshold in ms")
    max_retries: int = Field(
        default=2, ge=0, description="Maximum client retry attempts on failure/timeout"
    )
    retry_backoff_ms: float = Field(
        default=100.0, ge=0.0, description="Base exponential backoff step in ms"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Downstream service dependencies"
    )
    cache_hit_rate: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Cache hit probability if caching"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkloadPreset(StrEnum):
    """Standard workload size presets."""

    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    CUSTOM = "CUSTOM"


WORKLOAD_SIZES: dict[WorkloadPreset, int] = {
    WorkloadPreset.SMALL: 1000,
    WorkloadPreset.MEDIUM: 10000,
    WorkloadPreset.LARGE: 100000,
}


class ExportFormat(StrEnum):
    """Supported dataset serialization formats."""

    JSONL = "JSONL"
    PARQUET = "PARQUET"
    ALL = "ALL"


class SimulationConfig(BaseModel):
    """Top-level simulation execution configuration."""

    seed: int = Field(default=42, description="Master pseudo-random seed for determinism")
    workflow_count: int = Field(
        default=1000, ge=1, description="Total workflow executions to simulate"
    )
    workload_preset: WorkloadPreset = Field(default=WorkloadPreset.CUSTOM)
    arrival_rate_per_second: float = Field(
        default=20.0, ge=0.1, description="Nominal workflows started per sim-second"
    )
    incident_scenario: IncidentScenario | None = Field(
        default=None, description="Explicit incident to inject"
    )
    incident_probability: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Stochastic incident rate"
    )
    incident_duration_workflows: int = Field(
        default=150, ge=5, description="Workflows affected per incident window"
    )
    output_dir: Path = Field(
        default=Path("data/generated"), description="Target directory for exported datasets"
    )
    export_format: ExportFormat = Field(default=ExportFormat.ALL, description="Export file format")
    services: dict[str, ServiceConfig] = Field(
        default_factory=dict, description="Custom service configs"
    )


def get_default_service_configs() -> dict[str, ServiceConfig]:
    """Produce the default set of simulated distributed microservice profiles."""
    return {
        "auth-service": ServiceConfig(
            name="auth-service",
            baseline_latency_ms=22.0,
            latency_sigma=0.25,
            capacity=300,
            baseline_failure_rate=0.002,
            timeout_ms=800.0,
            max_retries=2,
            retry_backoff_ms=50.0,
        ),
        "customer-service": ServiceConfig(
            name="customer-service",
            baseline_latency_ms=45.0,
            latency_sigma=0.30,
            capacity=220,
            baseline_failure_rate=0.004,
            timeout_ms=1500.0,
            max_retries=2,
            retry_backoff_ms=80.0,
            dependencies=["inventory-service"],
            cache_hit_rate=0.85,
        ),
        "inventory-service": ServiceConfig(
            name="inventory-service",
            baseline_latency_ms=65.0,
            latency_sigma=0.35,
            capacity=180,
            baseline_failure_rate=0.006,
            timeout_ms=2000.0,
            max_retries=3,
            retry_backoff_ms=120.0,
            dependencies=["pricing-service"],
        ),
        "pricing-service": ServiceConfig(
            name="pricing-service",
            baseline_latency_ms=38.0,
            latency_sigma=0.28,
            capacity=250,
            baseline_failure_rate=0.003,
            timeout_ms=1200.0,
            max_retries=2,
            retry_backoff_ms=60.0,
            dependencies=["payment-service"],
        ),
        "payment-service": ServiceConfig(
            name="payment-service",
            baseline_latency_ms=145.0,
            latency_sigma=0.45,
            capacity=110,
            baseline_failure_rate=0.012,
            timeout_ms=3500.0,
            max_retries=3,
            retry_backoff_ms=200.0,
            dependencies=["order-service"],
        ),
        "order-service": ServiceConfig(
            name="order-service",
            baseline_latency_ms=50.0,
            latency_sigma=0.30,
            capacity=190,
            baseline_failure_rate=0.004,
            timeout_ms=2000.0,
            max_retries=2,
            retry_backoff_ms=90.0,
            dependencies=["notification-service"],
        ),
        "notification-service": ServiceConfig(
            name="notification-service",
            baseline_latency_ms=28.0,
            latency_sigma=0.25,
            capacity=350,
            baseline_failure_rate=0.002,
            timeout_ms=1000.0,
            max_retries=2,
            retry_backoff_ms=50.0,
        ),
    }
