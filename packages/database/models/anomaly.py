"""Workflow anomaly detection database ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base, TimestampMixin, utc_now


class AnomalyModel(Base, TimestampMixin):
    """Stores detected behavioral and statistical anomalies for workflow executions."""

    __tablename__ = "workflow_anomalies"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, doc="Unique anomaly record identifier"
    )
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
    anomaly_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Classification: LATENCY_SPIKE, UNUSUAL_PATH, RETRY_STORM, ERROR_CASCADE, DEPENDENCY_TIMEOUT",
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
        doc="Normalized anomaly severity score [0.0 - 1.0]",
    )
    severity: Mapped[str] = mapped_column(
        String(32),
        default="INFO",
        nullable=False,
        index=True,
        doc="Categorical severity rating: INFO, WARNING, CRITICAL",
    )
    affected_services: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="List of microservice and infrastructure names impacted by the anomaly",
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Human-readable diagnostic description of why this anomaly was flagged",
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Quantitative metrics, statistical distributions, thresholds, and transition matrices",
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
        doc="Timestamp when the anomaly was discovered",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary representation."""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "workflow_definition_id": self.workflow_definition_id,
            "anomaly_type": self.anomaly_type,
            "score": self.score,
            "severity": self.severity,
            "affected_services": self.affected_services,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
