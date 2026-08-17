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
