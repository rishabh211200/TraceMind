"""Pydantic v2 schemas for Root Cause Analysis and diagnostic reports."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RootCauseAnalyzeRequest(BaseModel):
    """Payload for on-demand root cause diagnosis."""

    execution_id: str = Field(..., description="Target workflow execution ID")
    workflow_definition_id: str = Field(
        default="order_fulfillment", description="Workflow DAG identifier"
    )
    events: list[dict[str, Any]] | None = Field(
        default=None, description="Optional raw or in-flight trace span list"
    )
    anomalies: list[dict[str, Any]] | None = Field(
        default=None, description="Optional pre-computed anomaly records"
    )
    shap_contributions: list[dict[str, Any]] | None = Field(
        default=None, description="Optional TreeSHAP feature attributions"
    )
    persist_to_db: bool = Field(
        default=True, description="Whether to persist the generated report to database"
    )


class HypothesisItem(BaseModel):
    """Candidate culprit hypothesis item in response envelope."""

    id: str
    culprit_service: str
    incident_category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    causal_path: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class RootCauseReportResponse(BaseModel):
    """Complete root-cause diagnosis report response."""

    id: str
    execution_id: str
    workflow_definition_id: str
    culprit_service: str
    incident_category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    causal_path: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    primary_hypothesis: HypothesisItem
    alternative_hypotheses: list[HypothesisItem] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RootCauseStatsResponse(BaseModel):
    """Aggregated summary statistics for root cause diagnoses."""

    total_diagnoses: int
    by_category: dict[str, int]
    by_culprit_service: dict[str, int]
    mean_confidence: float
