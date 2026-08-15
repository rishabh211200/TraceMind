"""Domain models for ML predictions, anomaly detection, root-cause analysis, and optimization."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AnomalyType(StrEnum):
    """Categorization of detected workflow anomalies."""

    LATENCY_SPIKE = "LATENCY_SPIKE"
    UNUSUAL_PATH = "UNUSUAL_PATH"
    RETRY_STORM = "RETRY_STORM"
    ERROR_CASCADE = "ERROR_CASCADE"
    DEPENDENCY_TIMEOUT = "DEPENDENCY_TIMEOUT"


class FeatureContribution(BaseModel):
    """SHAP or feature importance contribution to a prediction."""

    feature_name: str = Field(..., description="Name of the input feature")
    value: float = Field(..., description="Feature input value")
    contribution: float = Field(..., description="SHAP attribution (+/- value)")
    description: str | None = Field(default=None, description="Human-readable explanation")


class Prediction(BaseModel):
    """Failure and latency inference output for a workflow execution."""

    id: str = Field(default_factory=lambda: f"pred_{uuid4().hex[:10]}")
    execution_id: str = Field(..., description="Associated workflow execution ID")
    model_name: str = Field(..., description="Model identifier (e.g. xgboost_failure_classifier)")
    model_version: str = Field(default="1.0.0", description="Model version")
    failure_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Predicted probability of failure [0.0 - 1.0]"
    )
    latency_prediction_ms: float | None = Field(
        default=None, ge=0.0, description="Predicted remaining or total latency"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Model certainty")
    top_contributions: list[FeatureContribution] = Field(
        default_factory=list, description="SHAP feature attribution breakdown"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Inference timestamp"
    )


class Anomaly(BaseModel):
    """Detected behavioral anomaly in a workflow run or service."""

    id: str = Field(default_factory=lambda: f"anom_{uuid4().hex[:10]}")
    execution_id: str = Field(..., description="Associated workflow execution ID")
    anomaly_type: AnomalyType = Field(..., description="Classification of anomaly")
    score: float = Field(..., ge=0.0, description="Anomaly severity score / outlier degree")
    affected_services: list[str] = Field(default_factory=list, description="Services impacted")
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Detection timestamp"
    )
    explanation: str = Field(..., description="Detailed description of why this was flagged")
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Supporting metrics and distributions"
    )


class RootCauseHypothesis(BaseModel):
    """Inferred root cause produced by deterministic/graph reasoning engine."""

    id: str = Field(default_factory=lambda: f"rc_{uuid4().hex[:10]}")
    execution_id: str = Field(..., description="Associated workflow execution ID")
    probable_root_cause: str = Field(..., description="Primary identified failure cause")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Hypothesis confidence level [0.0 - 1.0]"
    )
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Bullet-point supporting technical evidence"
    )
    affected_services: list[str] = Field(default_factory=list, description="Degraded services")
    dependency_graph_path: list[str] = Field(
        default_factory=list, description="Causal propagation path across graph"
    )


class Recommendation(BaseModel):
    """Execution path or strategy optimization recommendation."""

    id: str = Field(default_factory=lambda: f"rec_{uuid4().hex[:10]}")
    execution_id: str | None = Field(default=None, description="Associated execution if contextual")
    workflow_id: str = Field(..., description="Target workflow ID")
    current_strategy: str = Field(..., description="Existing routing/execution approach")
    recommended_strategy: str = Field(..., description="Optimized proposed strategy")
    expected_latency_change_ms: float = Field(
        default=0.0, description="Expected delta in latency (negative is faster)"
    )
    expected_failure_rate_change: float = Field(
        default=0.0, description="Expected delta in failure rate (negative is safer)"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Optimizer confidence score")
    rationale: str = Field(default="", description="Optimization algorithm rationale")
