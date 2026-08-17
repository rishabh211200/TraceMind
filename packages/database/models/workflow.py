"""Workflow definitions and workflow execution database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.database.models.base import Base, TimestampMixin, utc_now


class WorkflowDefinitionModel(Base, TimestampMixin):
    """Represents a static multi-step workflow topology definition."""

    __tablename__ = "workflow_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    edges: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    executions: Mapped[list["WorkflowExecutionModel"]] = relationship(
        "WorkflowExecutionModel", back_populates="workflow_definition"
    )


class WorkflowExecutionModel(Base):
    """Represents an execution instance (trace) of a workflow."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        index=True,
        doc="Unique workflow execution ID (e.g. exec_42_000001)",
    )
    workflow_definition_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflow_definitions.id"),
        nullable=False,
        index=True,
        default="order_fulfillment",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, doc="COMPLETED, FAILED, TIMEOUT"
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_incident_affected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    workflow_definition: Mapped["WorkflowDefinitionModel"] = relationship(
        "WorkflowDefinitionModel", back_populates="executions"
    )
