"""Workflow path optimization and multi-objective recommendation database model."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base, utc_now


class OptimizationModel(Base):
    """Represents a multi-objective path optimization recommendation for a workflow DAG."""

    __tablename__ = "workflow_optimizations"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"opt_{uuid4().hex[:10]}",
        doc="Unique optimization recommendation identifier (e.g. opt_a1b2c3d4)",
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="tenant_system", index=True, nullable=False
    )
    workflow_definition_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        default="order_fulfillment",
        doc="Associated workflow DAG topology identifier",
    )
    optimization_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="MULTI_OBJECTIVE",
        doc="Optimization strategy type (e.g. MULTI_OBJECTIVE, INCIDENT_DIVERSION, COST_MINIMIZATION)",
    )
    weight_latency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.40,
        doc="Normalized utility weight assigned to execution latency",
    )
    weight_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.30,
        doc="Normalized utility weight assigned to modeled resource cost",
    )
    weight_reliability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.30,
        doc="Normalized utility weight assigned to historical reliability/success rate",
    )
    current_path: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Baseline or currently observed execution path metrics",
    )
    recommended_path: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Recommended optimal path steps with observed latency, reliability, and modeled cost breakdown",
    )
    pareto_frontier: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="Collection of non-dominated Pareto frontier paths",
    )
    all_evaluated_paths: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="All candidate paths considered during optimization evaluation",
    )
    expected_savings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Projected delta improvements (latency_reduction_pct, cost_reduction_pct, reliability_gain_pct)",
    )
    cost_model_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Transparent breakdown of modeled cost units (compute, db_io, retry penalties)",
    )
    rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        doc="Detailed engineering justification and trade-off explanation for the recommendation",
    )
    active_incident_culprit: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Identified M8 culprit microservice triggering advisory detour recommendation if applicable",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
        doc="Timestamp when optimization was generated",
    )
