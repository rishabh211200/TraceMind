"""Integration tests for trace analytics, DAG tree reconstruction, and percentile queries."""

from pathlib import Path

import pytest

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor
from packages.database.repositories.incident_repository import IncidentRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.repositories.workflow_repository import WorkflowRepository


@pytest.mark.asyncio
async def test_trace_tree_reconstruction_and_percentiles(test_db_session, temp_dir: Path):
    """Test full trace tree reconstruction and percentile aggregation on realistic trace data."""
    out_dir = temp_dir / "sim_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate 50 workflows with an active incident
    cfg = SimulationConfig(
        seed=42,
        workflow_count=50,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    simulator = TraceSimulator(cfg)
    sim_result = simulator.run()

    exporter = DatasetExporter(out_dir)
    exporter.export(sim_result, ExportFormat.ALL)

    ingestor = DatasetIngestor(test_db_session)
    await ingestor.ingest_all(out_dir)

    ev_repo = TraceEventRepository(test_db_session)
    wf_repo = WorkflowRepository(test_db_session)
    inc_repo = IncidentRepository(test_db_session)

    # 1. Verify workflow count
    exec_count = await wf_repo.count_executions()
    assert exec_count == 50

    # 2. Reconstruct DAG tree for first workflow
    tree = await ev_repo.get_trace_tree("exec_42_000000")
    assert tree is not None
    assert tree["event_type"] == "WORKFLOW_STARTED"
    assert len(tree["children"]) > 0

    # Check child span nesting
    auth_span = next((c for c in tree["children"] if c["service"] == "auth-service"), None)
    assert auth_span is not None

    # 2. Service Latency Percentiles
    auth_stats = await ev_repo.get_service_latency_stats("auth-service")
    assert auth_stats["count"] >= 50
    assert auth_stats["median_p50_latency_ms"] > 0.0
    assert auth_stats["p95_latency_ms"] >= auth_stats["median_p50_latency_ms"]
    assert auth_stats["p99_latency_ms"] >= auth_stats["p95_latency_ms"]

    # 3. Service Operational Health
    health = await ev_repo.get_service_health("auth-service")
    assert health["total_events"] >= 100
    assert "error_rate_percent" in health
    assert "retry_rate_percent" in health

    # 4. System-Wide Telemetry Summary
    summary = await ev_repo.get_service_telemetry_summary()
    assert len(summary) >= 7
    service_names = [s["service"] for s in summary]
    assert "auth-service" in service_names
    assert "payment-service" in service_names

    # 5. Incident Queries
    incidents = await inc_repo.list_incidents()
    if incidents:
        inc_id = incidents[0].id
        traces = await inc_repo.get_incident_traces(inc_id)
        assert isinstance(traces, list)


@pytest.mark.asyncio
async def test_optimized_telemetry_summary_correctness_and_filters(test_db_session, temp_dir: Path):
    """Test correctness, equivalence, service completeness, time filtering, and empty dataset behavior for telemetry summary."""
    out_dir = temp_dir / "sim_summary_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    ev_repo = TraceEventRepository(test_db_session)

    # 1. Empty Dataset Behavior
    empty_summary = await ev_repo.get_service_telemetry_summary()
    assert empty_summary == []

    # Ingest test simulation data
    cfg = SimulationConfig(
        seed=42,
        workflow_count=30,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    simulator = TraceSimulator(cfg)
    sim_result = simulator.run()
    exporter = DatasetExporter(out_dir)
    exporter.export(sim_result, ExportFormat.ALL)

    ingestor = DatasetIngestor(test_db_session)
    await ingestor.ingest_all(out_dir)

    # 2. Complete service list & structure
    full_summary = await ev_repo.get_service_telemetry_summary()
    assert len(full_summary) >= 7
    expected_services = {
        "api-gateway",
        "auth-service",
        "customer-service",
        "inventory-service",
        "pricing-service",
        "payment-service",
        "order-service",
        "notification-service",
    }
    returned_services = {s["service"] for s in full_summary}
    assert expected_services.issubset(returned_services)

    # 3. Equivalence: Verify each item in summary matches get_service_health(svc) exactly
    for item in full_summary:
        svc_name = item["service"]
        individual_health = await ev_repo.get_service_health(svc_name)
        assert item["service"] == individual_health["service"]
        assert item["total_events"] == individual_health["total_events"]
        assert item["failure_count"] == individual_health["failure_count"]
        assert item["error_rate_percent"] == individual_health["error_rate_percent"]
        assert item["retry_count"] == individual_health["retry_count"]
        assert item["retry_rate_percent"] == individual_health["retry_rate_percent"]
        assert item["timeout_count"] == individual_health["timeout_count"]
        assert item["timeout_rate_percent"] == individual_health["timeout_rate_percent"]
        assert item["latency"]["count"] == individual_health["latency"]["count"]
        assert (
            item["latency"]["median_p50_latency_ms"]
            == individual_health["latency"]["median_p50_latency_ms"]
        )
        assert item["latency"]["p95_latency_ms"] == individual_health["latency"]["p95_latency_ms"]

    # 4. Time Window Filtering
    events = await ev_repo.get_trace_events("exec_42_000000")
    t_start = events[0].timestamp
    t_mid = events[len(events) // 2].timestamp
    t_end = events[-1].timestamp

    # Filter bounded window
    windowed_summary = await ev_repo.get_service_telemetry_summary(
        start_time=t_start, end_time=t_mid
    )
    assert isinstance(windowed_summary, list)

    # Filter out-of-range window (future)
    future_start = t_end.replace(year=t_end.year + 10)
    future_summary = await ev_repo.get_service_telemetry_summary(start_time=future_start)
    assert future_summary == []
