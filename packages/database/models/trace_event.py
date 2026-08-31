"""Trace event telemetry database model (TimescaleDB hypertable candidate)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models.base import Base


class TraceEventModel(Base):
    """High-volume trace span event model partitioned by timestamp in TimescaleDB."""

    __tablename__ = "trace_events"

    # TimescaleDB hypertable requirement: Unique/Primary constraints must contain the partitioning column.
    event_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, doc="Unique event ID (e.g. evt_exec_42_000001_auth_start)"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        doc="Event emission timestamp (TimescaleDB hypertable partition key)",
    )

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        default="tenant_system",
        nullable=False,
        doc="Owning multi-tenant organization ID",
    )
    execution_id: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Parent workflow execution / trace ID"
    )
    workflow_id: Mapped[str] = mapped_column(
        String(64), default="order_fulfillment", nullable=False
    )
    service: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Executing service or infrastructure component"
    )
    operation: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Operation or step performed"
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="WORKFLOW_STARTED, SERVICE_COMPLETED, RETRY_STARTED, DATABASE_QUERY, etc.",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, doc="SUCCESS, FAILURE, TIMEOUT, RETRY"
    )
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    parent_event_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="Parent span ID for DAG tree reconstruction"
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="Distributed correlation ID"
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    __table_args__ = (
        Index("ix_trace_events_tenant_ts", "tenant_id", "timestamp"),
        Index("ix_trace_events_exec_ts", "execution_id", "timestamp"),
        Index("ix_trace_events_svc_ts", "service", "timestamp"),
        Index("ix_trace_events_type_ts", "event_type", "timestamp"),
        Index("ix_trace_events_status_ts", "status", "timestamp"),
        Index("ix_trace_events_parent", "parent_event_id"),
    )
