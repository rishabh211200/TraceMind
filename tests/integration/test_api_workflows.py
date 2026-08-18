"""Integration and contract tests for workflow definition CRUD, DAG validation, and statistics."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor


@pytest.mark.asyncio
async def test_workflow_crud_and_dag_validation(async_client: AsyncClient):
    """Test full workflow definition lifecycle and DAG validation rules."""
    # 1. Valid Workflow Registration
    valid_payload = {
        "id": "checkout_flow",
        "name": "E-Commerce Checkout Flow",
        "version": "1.0.0",
        "description": "Standard checkout orchestration workflow",
        "nodes": [
            {
                "id": "step_auth",
                "name": "Authenticate",
                "service": "auth-service",
                "operation": "auth",
            },
            {
                "id": "step_pay",
                "name": "Process Payment",
                "service": "payment-service",
                "operation": "charge",
            },
            {
                "id": "step_notify",
                "name": "Send Confirmation",
                "service": "notification-service",
                "operation": "notify",
            },
        ],
        "edges": [
            {"from_node": "step_auth", "to_node": "step_pay"},
            {"from_node": "step_pay", "to_node": "step_notify"},
        ],
        "metadata": {"tier": "critical"},
    }

    res = await async_client.post("/api/v1/workflows", json=valid_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "checkout_flow"
    assert data["node_count"] == 3
    assert data["edge_count"] == 2

    # 2. Duplicate Workflow ID Rejection (409 Conflict)
    dup_res = await async_client.post("/api/v1/workflows", json=valid_payload)
    assert dup_res.status_code == 409

    # 3. DAG Validation: Cycle Detection Rejection (400 Bad Request)
    cycle_payload = {
        "id": "cyclic_workflow",
        "name": "Invalid Cyclic Workflow",
        "version": "1.0.0",
        "nodes": [
            {"id": "node_a", "name": "A", "service": "auth-service", "operation": "op"},
            {"id": "node_b", "name": "B", "service": "payment-service", "operation": "op"},
            {"id": "node_c", "name": "C", "service": "order-service", "operation": "op"},
        ],
        "edges": [
            {"from_node": "node_a", "to_node": "node_b"},
            {"from_node": "node_b", "to_node": "node_c"},
            {"from_node": "node_c", "to_node": "node_a"},  # Cycle!
        ],
    }
    cycle_res = await async_client.post("/api/v1/workflows", json=cycle_payload)
    assert cycle_res.status_code == 400
    assert "Cycle detected" in cycle_res.json()["detail"]

    # 4. DAG Validation: Invalid Node Reference Rejection (400 Bad Request)
    invalid_node_payload = {
        "id": "invalid_ref_workflow",
        "name": "Invalid Ref Workflow",
        "version": "1.0.0",
        "nodes": [
            {"id": "node_1", "name": "1", "service": "auth-service", "operation": "op"},
        ],
        "edges": [
            {"from_node": "node_1", "to_node": "node_non_existent"},
        ],
    }
    inv_res = await async_client.post("/api/v1/workflows", json=invalid_node_payload)
    assert inv_res.status_code == 400
    assert "non-existent target node" in inv_res.json()["detail"]

    # 5. DAG Validation: Self-Loop Rejection (400 Bad Request)
    loop_payload = {
        "id": "loop_workflow",
        "name": "Loop Workflow",
        "version": "1.0.0",
        "nodes": [
            {"id": "node_x", "name": "X", "service": "auth-service", "operation": "op"},
        ],
        "edges": [
            {"from_node": "node_x", "to_node": "node_x"},
        ],
    }
    loop_res = await async_client.post("/api/v1/workflows", json=loop_payload)
    assert loop_res.status_code == 400
    assert "Self-loop detected" in loop_res.json()["detail"]

    # 6. List Workflows
    list_res = await async_client.get("/api/v1/workflows")
    assert list_res.status_code == 200
    wf_list = list_res.json()
    assert any(w["id"] == "checkout_flow" for w in wf_list)

    # 7. Get Workflow by ID
    get_res = await async_client.get("/api/v1/workflows/checkout_flow")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "E-Commerce Checkout Flow"

    # 8. Update Workflow
    update_res = await async_client.put(
        "/api/v1/workflows/checkout_flow",
        json={"description": "Updated checkout orchestration flow description", "version": "1.1.0"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["version"] == "1.1.0"
    assert update_res.json()["description"] == "Updated checkout orchestration flow description"

    # 9. Delete Workflow with no executions (204 No Content)
    del_res = await async_client.delete("/api/v1/workflows/checkout_flow")
    assert del_res.status_code == 204

    # 10. Verify Deletion
    get_del = await async_client.get("/api/v1/workflows/checkout_flow")
    assert get_del.status_code == 404


@pytest.mark.asyncio
async def test_workflow_executions_and_stats(
    async_client: AsyncClient, test_db_session, temp_dir: Path
):
    """Test workflow executions listing, pagination, and aggregate statistics calculation."""
    out_dir = temp_dir / "sim_stats_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate and persist 30 workflows
    cfg = SimulationConfig(
        seed=42,
        workflow_count=30,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    sim = TraceSimulator(cfg)
    res = sim.run()
    exporter = DatasetExporter(out_dir)
    exporter.export(res, ExportFormat.ALL)

    ingestor = DatasetIngestor(test_db_session)
    await ingestor.ingest_all(out_dir)

    # 1. Get Executions for Workflow
    wf_id = "order_fulfillment"
    execs_res = await async_client.get(f"/api/v1/workflows/{wf_id}/executions?limit=10&offset=0")
    assert execs_res.status_code == 200
    data = execs_res.json()
    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 10
    assert data["pagination"]["total"] == 30
    assert data["pagination"]["has_more"] is True

    # 2. Get Aggregate Workflow Stats
    stats_res = await async_client.get(f"/api/v1/workflows/{wf_id}/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["workflow_definition_id"] == wf_id
    assert stats["total_executions"] == 30
    assert stats["success_rate_percent"] >= 0.0
    assert stats["mean_duration_ms"] > 0.0
    assert stats["p95_duration_ms"] >= stats["median_p50_duration_ms"]

    # 3. Verify Deletion Safety (Cannot delete workflow with active executions -> 409 Conflict)
    del_conflict = await async_client.delete(f"/api/v1/workflows/{wf_id}")
    assert del_conflict.status_code == 409
    assert "execution records are associated" in del_conflict.json()["detail"]
