"""Root-cause analysis and diagnostic reasoning database model."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base, utc_now


class RootCauseModel(Base):
    """Represents an automated root-cause diagnosis for a workflow execution."""

    __tablename__ = "workflow_root_causes"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"rc_{uuid4().hex[:10]}",
        doc="Unique root-cause diagnosis identifier (e.g. rc_a1b2c3d4)",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="tenant_system", index=True, nullable=False
    )
    execution_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflow_executions.id"),
        nullable=False,
        index=True,
        doc="Associated workflow execution ID",
    )

    workflow_definition_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        default="order_fulfillment",
        doc="Associated workflow topology definition ID",
    )
    culprit_service: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Primary identified root-cause microservice or infrastructure component",
    )
    incident_category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Categorical root-cause pattern (e.g. DATABASE_IOPS_SATURATION, SERVICE_CRASH)",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Diagnosis certainty score [0.0 - 1.0]",
    )
    causal_path: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Ordered list of services in the propagation chain (from root to symptom)",
    )
    supporting_evidence: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Bullet-point quantitative evidence explaining the diagnosis",
    )
    alternative_hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        doc="Ranked secondary candidate hypotheses with confidence scores",
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
        doc="Timestamp of diagnosis generation",
    )
