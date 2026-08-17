"""Unit tests for asynchronous database repositories."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.database.repositories import (
    IncidentRepository,
    ServiceRepository,
    TraceEventRepository,
    WorkflowRepository,
)


@pytest.mark.asyncio
async def test_service_repository(test_db_session):
    """Test ServiceRepository CRUD and query operations."""
    repo = ServiceRepository(test_db_session)

    # Upsert service
    svc_data = {
        "name": "auth-service",
        "service_type": "business_microservice",
        "capacity": 100,
        "baseline_latency_ms": 25.0,
        "baseline_failure_rate": 0.002,
        "timeout_ms": 2000.0,
        "max_retries": 2,
        "retry_backoff_ms": 100.0,
        "dependencies": [],
        "metadata_": {"tier": "core"},
    }
    created = await repo.upsert_service(svc_data)
    assert created.name == "auth-service"
    assert created.capacity == 100

    # Get service
    fetched = await repo.get_service("auth-service")
    assert fetched is not None
    assert fetched.baseline_latency_ms == 25.0

    # Update service
    svc_data["capacity"] = 150
    updated = await repo.upsert_service(svc_data)
    assert updated.capacity == 150

    # List services
    services = await repo.list_services()
    assert len(services) == 1
    assert services[0].name == "auth-service"


@pytest.mark.asyncio
async def test_workflow_repository(test_db_session):
    """Test WorkflowRepository definition and execution methods."""
    repo = WorkflowRepository(test_db_session)

    # Upsert workflow definition
    wf_def = {
        "id": "order_fulfillment",
        "name": "Order Fulfillment",
        "version": "1.0.0",
        "nodes": [{"id": "auth", "service": "auth-service"}],
        "edges": [],
        "metadata_": {},
    }
    await repo.upsert_definition(wf_def)
    fetched_def = await repo.get_definition("order_fulfillment")
    assert fetched_def is not None
    assert fetched_def.name == "Order Fulfillment"

    # Create execution
    now = datetime.now(UTC)
    exec_data = {
        "id": "exec_42_000001",
        "workflow_definition_id": "order_fulfillment",
        "started_at": now,
        "completed_at": now + timedelta(milliseconds=450),
        "duration_ms": 450.0,
        "status": "COMPLETED",
        "retry_count": 0,
        "error_count": 0,
        "failure_reason": None,
        "incident_id": None,
        "is_incident_affected": False,
        "metadata_": {"correlation_id": "corr_42_000001"},
    }
    await repo.create_execution(exec_data)

    fetched_exec = await repo.get_execution("exec_42_000001")
    assert fetched_exec is not None
    assert fetched_exec.duration_ms == 450.0
    assert fetched_exec.status == "COMPLETED"

    # Count executions
    count = await repo.count_executions(status="COMPLETED")
    assert count == 1

    # List executions
    executions = await repo.list_executions(status="COMPLETED")
    assert len(executions) == 1
    assert executions[0].id == "exec_42_000001"


@pytest.mark.asyncio
async def test_trace_event_repository_tree_and_analytics(test_db_session):
    """Test TraceEventRepository tree DAG reconstruction and latency percentiles."""
    repo = TraceEventRepository(test_db_session)

    now = datetime.now(UTC)
    events = [
        {
            "event_id": "evt_001_root",
            "timestamp": now,
            "execution_id": "exec_001",
            "workflow_id": "order_fulfillment",
            "service": "api-gateway",
            "operation": "start_workflow",
            "event_type": "WORKFLOW_STARTED",
            "status": "SUCCESS",
            "latency_ms": 0.0,
            "parent_event_id": None,
            "correlation_id": "corr_001",
            "metadata_": {},
        },
        {
            "event_id": "evt_001_auth_start",
            "timestamp": now + timedelta(milliseconds=1),
            "execution_id": "exec_001",
            "workflow_id": "order_fulfillment",
            "service": "auth-service",
            "operation": "authenticate_user",
            "event_type": "SERVICE_STARTED",
            "status": "SUCCESS",
            "latency_ms": 0.0,
            "parent_event_id": "evt_001_root",
            "correlation_id": "corr_001",
            "metadata_": {},
        },
        {
            "event_id": "evt_001_auth_comp",
            "timestamp": now + timedelta(milliseconds=25),
            "execution_id": "exec_001",
            "workflow_id": "order_fulfillment",
            "service": "auth-service",
            "operation": "authenticate_user",
            "event_type": "SERVICE_COMPLETED",
            "status": "SUCCESS",
            "latency_ms": 24.0,
            "parent_event_id": "evt_001_auth_start",
            "correlation_id": "corr_001",
            "metadata_": {},
        },
    ]

    inserted = await repo.bulk_insert_events(events)
    assert inserted == 3

    # Ordered events retrieval
    trace_events = await repo.get_trace_events("exec_001")
    assert len(trace_events) == 3
    assert trace_events[0].event_id == "evt_001_root"
    assert trace_events[1].event_id == "evt_001_auth_start"
    assert trace_events[2].event_id == "evt_001_auth_comp"

    # Reconstruct DAG Tree
    tree = await repo.get_trace_tree("exec_001")
    assert tree is not None
    assert tree["event_id"] == "evt_001_root"
    assert len(tree["children"]) == 1
    assert tree["children"][0]["event_id"] == "evt_001_auth_start"
    assert len(tree["children"][0]["children"]) == 1
    assert tree["children"][0]["children"][0]["event_id"] == "evt_001_auth_comp"

    # Latency percentiles
    stats = await repo.get_service_latency_stats("auth-service")
    assert stats["count"] == 1
    assert stats["median_p50_latency_ms"] == 24.0

    # Service health
    health = await repo.get_service_health("auth-service")
    assert health["total_events"] == 2
    assert health["failure_count"] == 0
    assert health["error_rate_percent"] == 0.0


@pytest.mark.asyncio
async def test_incident_repository(test_db_session):
    """Test IncidentRepository operations."""
    wf_repo = WorkflowRepository(test_db_session)
    inc_repo = IncidentRepository(test_db_session)

    # Create workflow definition and execution
    await wf_repo.upsert_definition(
        {"id": "order_fulfillment", "name": "Order Fulfillment", "nodes": [], "edges": []}
    )

    now = datetime.now(UTC)
    await wf_repo.create_execution(
        {
            "id": "exec_42_000028",
            "workflow_definition_id": "order_fulfillment",
            "started_at": now + timedelta(seconds=10),
            "completed_at": now + timedelta(seconds=11),
            "duration_ms": 1000.0,
            "status": "COMPLETED",
            "incident_id": "inc_001_db",
            "is_incident_affected": True,
            "metadata_": {},
        }
    )

    # Upsert incident
    inc_data = {
        "id": "inc_001_db",
        "scenario_type": "DATABASE_LATENCY",
        "severity": "HIGH",
        "started_at": now,
        "ended_at": now + timedelta(minutes=5),
        "duration_seconds": 300.0,
        "affected_services": ["customer-db", "inventory-db"],
        "ground_truth_root_cause": "Storage I/O saturation",
        "description": "Database latency spike incident",
        "parameters": {"multiplier": 5.5},
        "metadata_": {},
    }
    await inc_repo.upsert_incident(inc_data)

    fetched = await inc_repo.get_incident("inc_001_db")
    assert fetched is not None
    assert fetched.scenario_type == "DATABASE_LATENCY"
    assert fetched.affected_services == ["customer-db", "inventory-db"]

    # List incidents
    incidents = await inc_repo.list_incidents(scenario_type="DATABASE_LATENCY")
    assert len(incidents) == 1
    assert incidents[0].id == "inc_001_db"

    # Get incident traces
    traces = await inc_repo.get_incident_traces("inc_001_db")
    assert len(traces) == 1
    assert traces[0].id == "exec_42_000028"
