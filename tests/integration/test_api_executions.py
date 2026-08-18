"""Integration and contract tests for execution listings, filtering, trace events, and DAG trees."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.incidents import ChaosScenario
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor


@pytest.mark.asyncio
async def test_executions_queries_and_trace_tree(
    async_client: AsyncClient, test_db_session, temp_dir: Path
):
    """Test execution listing with filters, pagination, span event stream, and hierarchical DAG tree."""
    out_dir = temp_dir / "exec_test_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate and ingest 25 workflows with chaos incident
    cfg = SimulationConfig(
        seed=101,
        workflow_count=25,
        incident_scenario=ChaosScenario.DATABASE_LATENCY,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    sim = TraceSimulator(cfg)
    res = sim.run()
    exporter = DatasetExporter(out_dir)
    exporter.export(res, ExportFormat.ALL)

    ingestor = DatasetIngestor(test_db_session)
    await ingestor.ingest_all(out_dir)

    # 1. List Executions with Pagination
    list_res = await async_client.get("/api/v1/executions?limit=10&offset=0")
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["items"]) == 10
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["has_more"] is True

    # 2. Filter by is_incident_affected
    inc_res = await async_client.get("/api/v1/executions?is_incident_affected=true")
    assert inc_res.status_code == 200
    inc_data = inc_res.json()
    assert inc_data["pagination"]["total"] > 0
    assert all(item["is_incident_affected"] is True for item in inc_data["items"])

    # 3. Filter by Duration Range
    dur_res = await async_client.get(
        "/api/v1/executions?min_duration_ms=5.0&max_duration_ms=5000.0"
    )
    assert dur_res.status_code == 200
    dur_data = dur_res.json()
    for item in dur_data["items"]:
        assert 5.0 <= item["duration_ms"] <= 5000.0

    # 4. Get Execution by ID
    target_exec = data["items"][0]
    exec_id = target_exec["id"]
    get_res = await async_client.get(f"/api/v1/executions/{exec_id}")
    assert get_res.status_code == 200
    single = get_res.json()
    assert single["id"] == exec_id
    assert single["workflow_definition_id"] == target_exec["workflow_definition_id"]

    # 5. Get Chronological Trace Events
    events_res = await async_client.get(f"/api/v1/executions/{exec_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 5
    assert events[0]["execution_id"] == exec_id
    assert any(e["service"] == "order-service" for e in events)

    # 6. Get Hierarchical Trace Tree DAG
    tree_res = await async_client.get(f"/api/v1/executions/{exec_id}/tree")
    assert tree_res.status_code == 200
    tree = tree_res.json()
    assert tree["event_id"] is not None
    assert tree["service"] == "api-gateway"
    assert "children" in tree
    assert len(tree["children"]) > 0

    # 7. 404 for Non-Existent Execution
    not_found = await async_client.get("/api/v1/executions/exec_non_existent_999")
    assert not_found.status_code == 404
    assert not_found.json()["error_code"] == "WORKFLOWEXECUTION_NOT_FOUND"
