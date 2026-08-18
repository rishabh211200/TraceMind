"""Integration and contract tests for service catalog, updates, and graph topology APIs."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor


@pytest.mark.asyncio
async def test_services_catalog_and_updates(
    async_client: AsyncClient, test_db_session, temp_dir: Path
):
    """Test service listing, profile lookup, updates, and topology graph."""
    out_dir = temp_dir / "services_test_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ingest services and telemetry
    cfg = SimulationConfig(
        seed=123,
        workflow_count=20,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    sim = TraceSimulator(cfg)
    res = sim.run()
    exporter = DatasetExporter(out_dir)
    exporter.export(res, ExportFormat.ALL)

    ingestor = DatasetIngestor(test_db_session)
    await ingestor.ingest_all(out_dir)

    # 1. List Services
    list_res = await async_client.get("/api/v1/services")
    assert list_res.status_code == 200
    services = list_res.json()
    assert len(services) >= 7
    service_names = [s["name"] for s in services]
    assert "order-service" in service_names
    assert "payment-service" in service_names

    # 2. Get Service by Name
    get_res = await async_client.get("/api/v1/services/payment-service")
    assert get_res.status_code == 200
    pay_svc = get_res.json()
    assert pay_svc["name"] == "payment-service"
    assert pay_svc["capacity"] > 0
    assert pay_svc["baseline_latency_ms"] > 0.0

    # 3. Update Service Baseline
    update_res = await async_client.put(
        "/api/v1/services/payment-service",
        json={"capacity": 250, "timeout_ms": 3500.0, "max_retries": 4},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["capacity"] == 250
    assert updated["timeout_ms"] == 3500.0
    assert updated["max_retries"] == 4

    # Verify update persisted
    verify_res = await async_client.get("/api/v1/services/payment-service")
    assert verify_res.json()["capacity"] == 250

    # 4. Get Service Latency Percentiles
    lat_res = await async_client.get("/api/v1/services/payment-service/latency")
    assert lat_res.status_code == 200
    lat_data = lat_res.json()
    assert lat_data["service"] == "payment-service"
    assert lat_data["count"] > 0
    assert lat_data["p95_latency_ms"] >= lat_data["median_p50_latency_ms"]

    # 5. Get Service Health
    health_res = await async_client.get("/api/v1/services/payment-service/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["service"] == "payment-service"
    assert health_data["total_events"] > 0

    # 6. Get Service Topology Graph
    topo_res = await async_client.get("/api/v1/services/topology")
    assert topo_res.status_code == 200
    topology = topo_res.json()
    assert "nodes" in topology
    assert "edges" in topology
    assert topology["total_services"] >= 7
    assert topology["total_dependencies"] > 0

    # Verify edge structure
    edge_pairs = [(e["from_service"], e["to_service"]) for e in topology["edges"]]
    assert any(p[0] == "customer-service" and "customer" in p[1] for p in edge_pairs)

    # 7. 404 for Non-Existent Service
    not_found = await async_client.get("/api/v1/services/non_existent_service_xyz")
    assert not_found.status_code == 404
    assert not_found.json()["error_code"] == "SERVICE_NOT_FOUND"
