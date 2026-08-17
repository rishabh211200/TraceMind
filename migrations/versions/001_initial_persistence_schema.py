"""001 Initial Persistence Schema and TimescaleDB Hypertable initialization.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Services Table
    op.create_table(
        "services",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "service_type",
            sa.String(length=32),
            nullable=False,
            server_default="business_microservice",
        ),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("baseline_latency_ms", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("baseline_failure_rate", sa.Float(), nullable=False, server_default="0.005"),
        sa.Column("timeout_ms", sa.Float(), nullable=False, server_default="2000.0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("retry_backoff_ms", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index("ix_services_name", "services", ["name"])

    # 2. Workflow Definitions Table
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_definitions_id", "workflow_definitions", ["id"])

    # 3. Workflow Executions Table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workflow_definition_id", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("incident_id", sa.String(length=64), nullable=True),
        sa.Column(
            "is_incident_affected", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_executions_id", "workflow_executions", ["id"])
    op.create_index("ix_workflow_executions_started_at", "workflow_executions", ["started_at"])
    op.create_index("ix_workflow_executions_completed_at", "workflow_executions", ["completed_at"])
    op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])
    op.create_index("ix_workflow_executions_incident_id", "workflow_executions", ["incident_id"])
    op.create_index(
        "ix_workflow_executions_is_incident_affected",
        "workflow_executions",
        ["is_incident_affected"],
    )

    # 4. Incidents Table
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("scenario_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="MEDIUM"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("affected_services", sa.JSON(), nullable=False),
        sa.Column("ground_truth_root_cause", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_id", "incidents", ["id"])
    op.create_index("ix_incidents_scenario_type", "incidents", ["scenario_type"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_started_at", "incidents", ["started_at"])

    # 5. Trace Events Table (TimescaleDB Hypertable Candidate)
    # Composite PK (event_id, timestamp) for TimescaleDB hypertable partitioning compliance
    op.create_table(
        "trace_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column(
            "workflow_id", sa.String(length=64), nullable=False, server_default="order_fulfillment"
        ),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("parent_event_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id", "timestamp"),
    )
    op.create_index("ix_trace_events_exec_ts", "trace_events", ["execution_id", "timestamp"])
    op.create_index("ix_trace_events_svc_ts", "trace_events", ["service", "timestamp"])
    op.create_index("ix_trace_events_type_ts", "trace_events", ["event_type", "timestamp"])
    op.create_index("ix_trace_events_status_ts", "trace_events", ["status", "timestamp"])
    op.create_index("ix_trace_events_parent", "trace_events", ["parent_event_id"])

    # 6. TimescaleDB Extension & Hypertable initialization (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Enable TimescaleDB extension and create hypertable on trace_events
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
            op.execute(
                "SELECT create_hypertable('trace_events', 'timestamp', if_not_exists => TRUE);"
            )
        except Exception as e:
            # Fallback if TimescaleDB plugin is not loaded into PostgreSQL
            print(f"TimescaleDB hypertable setup notice: {e}")


def downgrade() -> None:
    op.drop_table("trace_events")
    op.drop_table("incidents")
    op.drop_table("workflow_executions")
    op.drop_table("workflow_definitions")
    op.drop_table("services")
