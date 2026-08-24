"""Pydantic v2 schemas for anomaly detection requests, responses, and calibration."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnomalyResponse(BaseModel):
    """Canonical serialized representation of a detected workflow anomaly."""

    id: str = Field(..., description="Unique anomaly record ID")
    execution_id: str = Field(..., description="Associated workflow execution ID")
    workflow_definition_id: str = Field(
        default="default_workflow", description="Workflow topology ID"
    )
    anomaly_type: str = Field(
        ..., description="Anomaly classification (e.g. LATENCY_SPIKE, RETRY_STORM)"
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized severity score [0.0 - 1.0]")
    severity: str = Field(..., description="Categorical rating: INFO, WARNING, CRITICAL")
    affected_services: list[str] = Field(
        default_factory=list, description="Microservices and components impacted"
    )
    explanation: str = Field(..., description="Human-readable diagnostic description")
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Supporting metrics and distributions"
    )
    detected_at: datetime = Field(..., description="Anomaly discovery timestamp")


class AnomalyDetectRequest(BaseModel):
    """Request payload for on-demand or in-flight anomaly detection."""

    execution_id: str = Field(..., description="Execution identifier to analyze")
    workflow_definition_id: str = Field(
        default="order_fulfillment",
        description="Associated workflow definition identifier",
    )
    events: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional in-memory trace spans (if omitted, queried from database)",
    )
    as_of_step: int | None = Field(
        default=None,
        description="Optional in-flight prefix step boundary (t <= t_k)",
    )
    persist_to_db: bool = Field(
        default=False,
        description="If True, saves discovered anomalies to the database",
    )


class AnomalyDetectResponse(BaseModel):
    """Detection results for a workflow execution."""

    execution_id: str = Field(..., description="Analyzed execution ID")
    workflow_definition_id: str = Field(..., description="Workflow definition ID")
    is_anomalous: bool = Field(..., description="True if at least one anomaly was discovered")
    max_score: float = Field(..., ge=0.0, le=1.0, description="Highest anomaly severity score")
    highest_severity: str = Field(
        ..., description="Highest categorical severity: NOMINAL, WARNING, CRITICAL"
    )
    anomaly_count: int = Field(..., description="Total number of distinct anomalies detected")
    anomalies: list[AnomalyResponse] = Field(
        default_factory=list,
        description="Ranked list of detected anomalies",
    )


class AnomalyStatsResponse(BaseModel):
    """Aggregated anomaly metrics summary."""

    total_anomalies: int = Field(..., description="Total historical anomalies recorded")
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Counts by severity (INFO, WARNING, CRITICAL)"
    )
    by_type: dict[str, int] = Field(default_factory=dict, description="Counts by anomaly type")


class AnomalyFitRequest(BaseModel):
    """Request to calibrate/fit anomaly baseline distributions."""

    nominal_workflows: int = Field(
        default=120, ge=20, le=1000, description="Nominal workflows to simulate"
    )
    seed: int = Field(default=42, description="Random state seed")
    version: str = Field(default="1.1.0", description="Detector version identifier")


class AnomalyFitResponse(BaseModel):
    """Baseline calibration result report."""

    status: str = Field(..., description="Calibration status (e.g. success)")
    version: str = Field(..., description="Saved detector version")
    services_fitted: list[str] = Field(
        default_factory=list, description="Services with fitted latency baselines"
    )
    transitions_fitted: int = Field(..., description="Total unique DAG transitions modeled")
