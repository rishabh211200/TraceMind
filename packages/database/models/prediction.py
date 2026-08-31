"""Workflow prediction and SHAP attribution database ORM model."""

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base, TimestampMixin


class PredictionModel(Base, TimestampMixin):
    """Stores ML failure probabilities, latency forecasts, and TreeSHAP feature attributions."""

    __tablename__ = "workflow_predictions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, doc="Unique prediction record identifier"
    )
    tenant_id: Mapped[str] = mapped_column(String(64), default="tenant_system", index=True, nullable=False)
    execution_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Associated workflow execution ID",
    )

    workflow_definition_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        doc="Workflow definition identifier (e.g. order_fulfillment)",
    )
    step_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Step count / index at the time of inference",
    )
    failure_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Predicted probability of failure [0.0 - 1.0]",
    )
    predicted_risk_level: Mapped[str] = mapped_column(
        String(32),
        default="LOW",
        nullable=False,
        doc="Categorical risk rating: LOW, MEDIUM, HIGH, CRITICAL",
    )
    predicted_latency_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        doc="Expected total duration in ms",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        doc="Model inference confidence score",
    )
    feature_attributions: Mapped[list[Any]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="List of serialized FeatureContribution dicts with SHAP scores and diagnostic text",
    )
    feature_vector: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Raw input feature values used for inference",
    )
    model_name: Mapped[str] = mapped_column(
        String(64),
        default="xgboost_workflow_predictor",
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(32),
        default="1.0.0",
        nullable=False,
    )
