"""Integration tests for FastAPI Workflow Optimizer REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_optimizer_recommend_and_persistence(async_client: AsyncClient):
    """Test POST /api/v1/optimizer/recommend and persistence to database."""
    payload = {
        "workflow_definition_id": "order_fulfillment",
        "weight_latency": 0.50,
        "weight_cost": 0.25,
        "weight_reliability": 0.25,
        "persist_to_db": True,
    }

    resp = await async_client.post("/api/v1/optimizer/recommend", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["workflow_definition_id"] == "order_fulfillment"
    assert data["optimization_type"] == "MULTI_OBJECTIVE"
    assert data["recommended_path"] is not None
    assert "observed_latency_ms" in data["recommended_path"]
    assert "modeled_cost_units" in data["recommended_path"]
    assert "cost_breakdown" in data["recommended_path"]
    assert len(data["pareto_frontier"]) >= 1

    opt_id = data["id"]

    # 2. Fetch specific optimization by ID
    get_resp = await async_client.get(f"/api/v1/optimizer/{opt_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == opt_id


@pytest.mark.asyncio
async def test_api_optimizer_incident_diversion(async_client: AsyncClient):
    """Test POST /api/v1/optimizer/recommend with advisory incident culprit detour."""
    payload = {
        "workflow_definition_id": "order_fulfillment",
        "weight_latency": 0.40,
        "weight_cost": 0.30,
        "weight_reliability": 0.30,
        "active_incident_culprit": "inventory-db",
        "persist_to_db": True,
    }

    resp = await async_client.post("/api/v1/optimizer/recommend", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["optimization_type"] == "INCIDENT_DIVERSION"
    assert data["active_incident_culprit"] == "inventory-db"
    assert "Advisory Incident Diversion" in data["rationale"]


@pytest.mark.asyncio
async def test_api_optimizer_candidate_paths_and_pareto(async_client: AsyncClient):
    """Test GET /api/v1/optimizer/paths and GET /api/v1/optimizer/pareto."""
    # List candidate paths
    paths_resp = await async_client.get("/api/v1/optimizer/paths/order_fulfillment")
    assert paths_resp.status_code == 200
    paths = paths_resp.json()
    assert len(paths) >= 3
    assert all("path_id" in p for p in paths)
    assert all("modeled_cost_units" in p for p in paths)

    # Get Pareto frontier
    pareto_resp = await async_client.get(
        "/api/v1/optimizer/pareto/order_fulfillment",
        params={"weight_latency": 0.6, "weight_cost": 0.2, "weight_reliability": 0.2},
    )
    assert pareto_resp.status_code == 200
    points = pareto_resp.json()
    assert len(points) >= 1
    assert any(pt["is_pareto_optimal"] for pt in points)


@pytest.mark.asyncio
async def test_api_optimizer_history_and_stats(async_client: AsyncClient):
    """Test GET /api/v1/optimizer/history and GET /api/v1/optimizer/stats."""
    hist_resp = await async_client.get("/api/v1/optimizer/history?limit=10")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert "items" in hist
    assert "total" in hist

    stats_resp = await async_client.get("/api/v1/optimizer/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_optimizations" in stats
    assert "avg_weight_latency" in stats
