"""Pydantic v2 schemas for ML failure/latency predictions and TreeSHAP explainability."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeatureContributionResponse(BaseModel):
    """TreeSHAP or feature attribution item schema."""

    feature_name: str = Field(..., description="Name of the input feature")
    value: float = Field(..., description="Numeric input feature value")
    contribution: float = Field(..., description="SHAP attribution (+/- value to margin/log-odds)")
    description: str | None = Field(default=None, description="Human-readable diagnostic message")


class PredictionRequest(BaseModel):
    """Payload for on-demand in-flight workflow failure & latency prediction."""

    execution_id: str = Field(..., description="Target workflow execution ID")
    workflow_definition_id: str = Field(
        default="order_fulfillment", description="Workflow definition identifier"
    )
    events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological partial trace span events (or omit to load from DB)",
    )
    as_of_step: int | None = Field(default=None, ge=1, description="In-flight step prefix limit")
    persist_to_db: bool = Field(
        default=False, description="Whether to persist the prediction record to database"
    )


class PredictionResponse(BaseModel):
    """Inference result schema including failure probability, forecasted latency, and SHAP attributions."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    execution_id: str
    workflow_definition_id: str
    step_index: int
    failure_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Predicted probability of failure [0.0 - 1.0]"
    )
    predicted_risk_level: str = Field(
        ..., description="Categorical risk: LOW, MEDIUM, HIGH, CRITICAL"
    )
    predicted_latency_ms: float = Field(
        ..., ge=0.0, description="Predicted total workflow duration in milliseconds"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Inference certainty score")
    top_contributions: list[FeatureContributionResponse] = Field(
        default_factory=list, description="Top ranked TreeSHAP feature attributions"
    )
    feature_vector: dict[str, float] = Field(
        default_factory=dict, description="Extracted feature vector values"
    )
    model_name: str
    model_version: str
    created_at: datetime


class TrainRequest(BaseModel):
    """Request parameters for offline model training."""

    nominal_workflows: int = Field(
        default=150, ge=20, le=2000, description="Number of baseline workflows to simulate"
    )
    incident_workflows_per_scenario: int = Field(
        default=30, ge=5, le=500, description="Workflows to simulate per chaos scenario"
    )
    random_state: int = Field(default=42, description="Deterministic random seed")
    version: str = Field(default="1.0.0", description="Model version tag")


class TrainResponse(BaseModel):
    """Training metrics and artifact metadata response."""

    status: str = Field(default="trained")
    version: str
    training_samples: int
    test_samples: int
    metrics: dict[str, Any]


class ModelMetadataResponse(BaseModel):
    """Information regarding the active ML model registry state."""

    version: str
    model_name: str
    status: str
    features: list[str]
    metrics: dict[str, Any]
