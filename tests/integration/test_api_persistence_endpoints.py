"""Integration tests for FastAPI persistence and query REST API endpoints."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor


@pytest.mark.asyncio
async def test_api_persistence_endpoints(
    async_client: AsyncClient, test_db_session, temp_dir: Path
):
    """Test full suite of /api/v1/ traces, services, and incidents endpoints."""
    out_dir = temp_dir / "sim_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate sample trace data
    cfg = SimulationConfig(
        seed=42,
        workflow_count=20,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    simulator = TraceSimulator(cfg)
    sim_result = simulator.run()

    exporter = DatasetExporter(out_dir)
    exporter.export(sim_result, ExportFormat.ALL)

    # Ingest into test DB
    ingestor = DatasetIngestor(test_db_session)
    await ingestor.ingest_all(out_dir)

    # 1. Test GET /api/v1/services
    res = await async_client.get("/api/v1/services")
    assert res.status_code == 200
    services = res.json()
    assert len(services) >= 7
    service_names = [s["name"] for s in services]
    assert "auth-service" in service_names

    # 2. Test GET /api/v1/services/{service}/latency
    res_lat = await async_client.get("/api/v1/services/auth-service/latency")
    assert res_lat.status_code == 200
    lat_data = res_lat.json()
    assert lat_data["service"] == "auth-service"
    assert "median_p50_latency_ms" in lat_data

    # 3. Test GET /api/v1/services/{service}/health
    res_health = await async_client.get("/api/v1/services/auth-service/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["service"] == "auth-service"
    assert health_data["total_events"] > 0

    # 4. Test GET /api/v1/services/telemetry/summary
    res_sum = await async_client.get("/api/v1/services/telemetry/summary")
    assert res_sum.status_code == 200
    assert len(res_sum.json()) >= 7

    # 5. Test GET /api/v1/traces
    res_traces = await async_client.get("/api/v1/traces?limit=10")
    assert res_traces.status_code == 200
    traces = res_traces.json()
    assert len(traces) > 0
    sample_id = traces[0]["id"]

    # 6. Test GET /api/v1/traces/{trace_id}
    res_single = await async_client.get(f"/api/v1/traces/{sample_id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == sample_id

    # 7. Test GET /api/v1/traces/{trace_id}/events
    res_events = await async_client.get(f"/api/v1/traces/{sample_id}/events")
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) > 0
    assert events[0]["execution_id"] == sample_id

    # 8. Test GET /api/v1/traces/{trace_id}/tree
    res_tree = await async_client.get(f"/api/v1/traces/{sample_id}/tree")
    assert res_tree.status_code == 200
    tree = res_tree.json()
    assert "event_id" in tree
    assert "children" in tree

    # 9. Test GET /api/v1/incidents
    res_inc = await async_client.get("/api/v1/incidents")
    assert res_inc.status_code == 200
    incidents = res_inc.json()
    assert isinstance(incidents, list)
