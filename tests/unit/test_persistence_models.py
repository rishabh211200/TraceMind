"""Unit tests for persistence SQLAlchemy ORM models."""

from datetime import UTC, datetime

from packages.database.models import (
    IncidentModel,
    ServiceModel,
    TraceEventModel,
    WorkflowDefinitionModel,
    WorkflowExecutionModel,
)


def test_service_model_attributes():
    """Verify ServiceModel table and column definitions."""
    svc = ServiceModel(
        name="payment-service",
        service_type="business_microservice",
        capacity=150,
        baseline_latency_ms=65.0,
        baseline_failure_rate=0.01,
        timeout_ms=3500.0,
        max_retries=3,
        retry_backoff_ms=200.0,
        dependencies=["payment-gateway"],
        metadata_={"tier": "critical"},
    )
    assert svc.name == "payment-service"
    assert svc.capacity == 150
    assert svc.timeout_ms == 3500.0
    assert svc.dependencies == ["payment-gateway"]
    assert ServiceModel.__tablename__ == "services"


def test_workflow_definition_model_attributes():
    """Verify WorkflowDefinitionModel schema."""
    wf = WorkflowDefinitionModel(
        id="order_fulfillment",
        name="Order Fulfillment Pipeline",
        version="1.0.0",
        nodes=[{"id": "auth", "service": "auth-service"}],
        edges=[],
    )
    assert wf.id == "order_fulfillment"
    assert wf.version == "1.0.0"
    assert WorkflowDefinitionModel.__tablename__ == "workflow_definitions"


def test_workflow_execution_model_attributes():
    """Verify WorkflowExecutionModel schema."""
    now = datetime.now(UTC)
    exec_model = WorkflowExecutionModel(
        id="exec_42_000001",
        workflow_definition_id="order_fulfillment",
        started_at=now,
        completed_at=now,
        duration_ms=450.5,
        status="COMPLETED",
        retry_count=1,
        error_count=0,
        incident_id="inc_000100_database",
        is_incident_affected=True,
    )
    assert exec_model.id == "exec_42_000001"
    assert exec_model.duration_ms == 450.5
    assert exec_model.is_incident_affected is True
    assert WorkflowExecutionModel.__tablename__ == "workflow_executions"


def test_trace_event_model_hypertable_composite_pk():
    """Verify TraceEventModel schema and composite primary key for TimescaleDB."""
    now = datetime.now(UTC)
    event = TraceEventModel(
        event_id="evt_exec_42_000001_auth_comp",
        timestamp=now,
        execution_id="exec_42_000001",
        service="auth-service",
        operation="authenticate_user",
        event_type="SERVICE_COMPLETED",
        status="SUCCESS",
        latency_ms=24.5,
        parent_event_id="evt_42_000001_root",
        correlation_id="corr_42_000001",
    )
    assert event.event_id == "evt_exec_42_000001_auth_comp"
    assert event.timestamp == now
    assert event.service == "auth-service"
    assert TraceEventModel.__tablename__ == "trace_events"

    # Verify that both event_id and timestamp are primary keys
    pk_cols = [col.name for col in TraceEventModel.__table__.primary_key]
    assert "event_id" in pk_cols
    assert "timestamp" in pk_cols


def test_incident_model_attributes():
    """Verify IncidentModel schema."""
    now = datetime.now(UTC)
    inc = IncidentModel(
        id="inc_000100_database",
        scenario_type="DATABASE_LATENCY",
        severity="HIGH",
        started_at=now,
        ended_at=now,
        duration_seconds=120.0,
        affected_services=["customer-db", "inventory-db"],
        ground_truth_root_cause="Database pool saturation",
        description="Controlled chaos storage slowdown",
    )
    assert inc.id == "inc_000100_database"
    assert inc.scenario_type == "DATABASE_LATENCY"
    assert inc.affected_services == ["customer-db", "inventory-db"]
    assert IncidentModel.__tablename__ == "incidents"
