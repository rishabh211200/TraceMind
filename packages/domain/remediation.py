"""Domain entities and value objects for Autonomous Closed-Loop Remediation."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(StrEnum):
    """Supported operational remediation action types."""

    CIRCUIT_BREAK = "CIRCUIT_BREAK"
    TRAFFIC_DIVERT = "TRAFFIC_DIVERT"
    CONCURRENCY_THROTTLE = "CONCURRENCY_THROTTLE"
    RETRY_BACKOFF_ADAPT = "RETRY_BACKOFF_ADAPT"
    CACHE_FALLBACK_ACTUATE = "CACHE_FALLBACK_ACTUATE"


class ExecutionMode(StrEnum):
    """Operating execution mode governing autonomous decision boundaries."""

    AUTONOMOUS = "AUTONOMOUS"
    SUPERVISED = "SUPERVISED"
    ADVISORY = "ADVISORY"


class ActionPlanStatus(StrEnum):
    """Lifecycle status of a remediation action plan."""

    STAGED = "STAGED"
    EXECUTING = "EXECUTING"
    ACTIVE_VERIFYING = "ACTIVE_VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class StateSnapshot(BaseModel):
    """Complete verbatim state snapshot of the active service routing and mesh configuration."""

    routing_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Path identifier to active fractional traffic routing weight.",
    )
    circuit_states: dict[str, str] = Field(
        default_factory=dict,
        description="Service or path identifier to circuit breaker state (CLOSED, OPEN, HALF_OPEN).",
    )
    concurrency_limits: dict[str, int] = Field(
        default_factory=dict,
        description="Service identifier to maximum in-flight concurrent request ceiling.",
    )
    retry_multipliers: dict[str, float] = Field(
        default_factory=dict,
        description="Service identifier to exponential retry backoff multiplier.",
    )
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the configuration snapshot was captured.",
    )


class RemediationPolicy(BaseModel):
    """Declarative policy rule defining automated and supervised mitigation thresholds."""

    id: str
    tenant_id: str = Field(
        default="tenant_system", description="Owning multi-tenant organization ID"
    )
    name: str
    workflow_definition_id: str = Field(
        default="*",
        description="Target workflow definition ID or '*' for global match.",
    )
    incident_category: str = Field(
        default="*",
        description="Target RCA incident fault signature (e.g. DATABASE_IOPS_SATURATION) or '*'.",
    )
    action_type: ActionType
    execution_mode: ExecutionMode = ExecutionMode.SUPERVISED
    max_blast_radius: float = Field(
        default=0.25,
        ge=0.01,
        le=0.50,
        description="Maximum permitted traffic diversion or throttling percentage.",
    )
    cooldown_seconds: int = Field(
        default=300,
        ge=10,
        description="Cooldown duration before the same component can be modified again.",
    )
    verification_timeout_seconds: int = Field(
        default=45,
        ge=5,
        le=300,
        description="Real-time telemetry verification monitoring window.",
    )
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SafetyCheckReport(BaseModel):
    """Detailed result of deterministic safety invariant evaluation."""

    is_safe: bool
    blast_radius_passed: bool
    anti_flapping_passed: bool
    acyclicity_passed: bool
    capacity_headroom_passed: bool
    checks_details: dict[str, str] = Field(default_factory=dict)
    rejection_reasons: list[str] = Field(default_factory=list)
    recommended_mode: ExecutionMode = ExecutionMode.ADVISORY


class RemediationActionPlan(BaseModel):
    """Actionable remediation plan synthesized from Root Cause Analysis and Pareto Optimization."""

    id: str
    tenant_id: str = Field(
        default="tenant_system", description="Owning multi-tenant organization ID"
    )
    policy_id: str | None = None
    workflow_definition_id: str
    incident_id: str | None = None
    trigger_rca_id: str | None = None
    action_type: ActionType
    execution_mode: ExecutionMode
    status: ActionPlanStatus = ActionPlanStatus.STAGED
    target_service: str
    target_parameters: dict[str, Any] = Field(default_factory=dict)
    blast_radius_pct: float = Field(ge=0.0, le=1.0)
    idempotency_key: str
    expected_savings: dict[str, float] = Field(default_factory=dict)
    pre_actuation_state_snapshot: StateSnapshot
    post_actuation_state_snapshot: StateSnapshot | None = None
    health_baseline: dict[str, float] = Field(default_factory=dict)
    post_health_metrics: dict[str, float] | None = None
    safety_report: SafetyCheckReport | None = None
    execution_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_at: datetime | None = None
    completed_at: datetime | None = None
