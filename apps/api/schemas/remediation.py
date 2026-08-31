"""Pydantic v2 schemas for Remediation API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.domain.remediation import (
    ActionPlanStatus,
    ActionType,
    ExecutionMode,
    SafetyCheckReport,
    StateSnapshot,
)


class RemediationPlanSynthesizeRequest(BaseModel):
    """Request to synthesize an actionable remediation plan from diagnostics."""

    workflow_definition_id: str = Field(description="Target workflow definition ID")
    incident_id: str | None = Field(default=None, description="Optional incident or execution ID")
    incident_category: str | None = Field(default=None, description="RCA incident fault category")
    root_cause_service: str | None = Field(default=None, description="Root cause culprit service")
    preferred_action: ActionType | None = Field(
        default=None, description="Preferred action type override"
    )
    diagnostic_confidence: float = Field(default=0.98, ge=0.0, le=1.0)


class RemediationPlanExecuteRequest(BaseModel):
    """Request to authorize and execute a staged remediation plan."""

    operator_notes: str | None = Field(
        default=None, description="Optional operator authorization notes"
    )
    simulated_post_telemetry: dict[str, float] | None = Field(
        default=None, description="Optional simulated post-actuation health metrics"
    )


class RemediationPolicyCreate(BaseModel):
    """Request payload to create or update a declarative remediation policy."""

    name: str = Field(min_length=3, max_length=255)
    workflow_definition_id: str = Field(default="*")
    incident_category: str = Field(default="*")
    action_type: ActionType
    execution_mode: ExecutionMode = ExecutionMode.SUPERVISED
    max_blast_radius: float = Field(default=0.25, ge=0.01, le=0.50)
    cooldown_seconds: int = Field(default=300, ge=10)
    verification_timeout_seconds: int = Field(default=45, ge=5, le=300)


class RemediationPolicyResponse(BaseModel):
    """Serialized remediation policy representation."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str = "tenant_system"
    name: str
    workflow_definition_id: str
    incident_category: str
    action_type: ActionType
    execution_mode: ExecutionMode
    max_blast_radius: float
    cooldown_seconds: int
    verification_timeout_seconds: int
    is_active: bool
    created_at: datetime


class RemediationPlanResponse(BaseModel):
    """Serialized remediation action plan representation."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str = "tenant_system"
    policy_id: str | None
    workflow_definition_id: str

    incident_id: str | None
    trigger_rca_id: str | None
    action_type: ActionType
    execution_mode: ExecutionMode
    status: ActionPlanStatus
    target_service: str
    target_parameters: dict[str, Any]
    blast_radius_pct: float
    idempotency_key: str
    expected_savings: dict[str, float]
    pre_actuation_state_snapshot: StateSnapshot
    post_actuation_state_snapshot: StateSnapshot | None = None
    health_baseline: dict[str, float]
    post_health_metrics: dict[str, float] | None = None
    safety_report: SafetyCheckReport | None = None
    execution_error: str | None = None
    created_at: datetime
    executed_at: datetime | None = None
    completed_at: datetime | None = None


class AuditLedgerEntryResponse(BaseModel):
    """Serialized cryptographic audit ledger entry."""

    model_config = {"from_attributes": True}

    entry_id: str
    plan_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    timestamp: datetime
    previous_hash: str
    entry_hash: str


class AuditLedgerVerificationResponse(BaseModel):
    """Integrity check response for cryptographic audit chain."""

    model_config = {"from_attributes": True}

    is_valid: bool
    message: str
    total_entries: int


class LiveMeshStateResponse(BaseModel):
    """Active runtime mesh routing and circuit breaker state."""

    model_config = {"from_attributes": True}

    routing_weights: dict[str, float]
    circuit_states: dict[str, str]
    concurrency_limits: dict[str, int]
    retry_multipliers: dict[str, float]
    captured_at: datetime
