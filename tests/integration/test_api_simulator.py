"""Integration and contract tests for simulation control and chaos injection APIs."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_simulator_scenarios_catalog(async_client: AsyncClient):
    """Test retrieving catalog of supported chaos scenarios."""
    res = await async_client.get("/api/v1/simulator/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) == 7

    scenario_types = {s["scenario_type"] for s in scenarios}
    expected = {
        "database_latency",
        "payment_latency_degradation",
        "traffic_spike",
        "service_failure",
        "network_latency",
        "retry_storm",
        "cascading_failure",
    }
    assert scenario_types == expected

    # Check structure of each scenario
    for s in scenarios:
        assert s["name"]
        assert s["description"]
        assert s["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert len(s["affected_services"]) > 0
        assert s["ground_truth_root_cause"]


@pytest.mark.asyncio
async def test_simulation_generate_in_memory_and_deterministic(async_client: AsyncClient):
    """Test simulation generation in-memory without persistence and verify deterministic output."""
    payload1 = {
        "workflow_count": 20,
        "seed": 42,
        "arrival_rate_rps": 15.0,
        "persist_to_db": False,
    }
    res1 = await async_client.post("/api/v1/simulator/generate", json=payload1)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["seed"] == 42
    assert data1["workflows_requested"] == 20
    assert data1["executions_generated"] == 20
    assert data1["events_generated"] > 0
    assert data1["persisted_to_db"] is False
    assert data1["persisted_executions_count"] == 0

    # Repeat with same seed to verify deterministic output
    res2 = await async_client.post("/api/v1/simulator/generate", json=payload1)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["events_generated"] == data1["events_generated"]
    assert (
        data2["summary_statistics"]["mean_latency_ms"]
        == data1["summary_statistics"]["mean_latency_ms"]
    )


@pytest.mark.asyncio
async def test_simulation_generate_with_db_persistence(async_client: AsyncClient):
    """Test simulation generation with automatic persistence into the database."""
    payload = {
        "workflow_count": 15,
        "seed": 999,
        "incident_scenario": "database_latency",
        "arrival_rate_rps": 20.0,
        "persist_to_db": True,
    }
    res = await async_client.post("/api/v1/simulator/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["persisted_to_db"] is True
    assert data["persisted_executions_count"] == 15
    assert data["persisted_events_count"] > 0
    assert data["persistence_wall_time_ms"] is not None
    assert data["persistence_wall_time_ms"] > 0.0

    # Verify executions are now queryable through /api/v1/executions
    execs_res = await async_client.get("/api/v1/executions?limit=50")
    assert execs_res.status_code == 200
    assert execs_res.json()["pagination"]["total"] >= 15


@pytest.mark.asyncio
async def test_chaos_injection_endpoint(async_client: AsyncClient):
    """Test targeted chaos injection API endpoint."""
    payload = {
        "scenario_type": "payment_latency_degradation",
        "workflow_count": 30,
        "seed": 777,
        "arrival_rate_rps": 10.0,
        "persist_to_db": True,
    }
    res = await async_client.post("/api/v1/simulator/inject-chaos", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_type"] == "payment_latency_degradation"
    assert "payment-service" in data["affected_services"]
    assert data["total_executions"] == 30
    assert data["executions_affected"] > 0
    assert data["persisted_to_db"] is True


@pytest.mark.asyncio
async def test_simulator_validation_errors(async_client: AsyncClient):
    """Test rejection of invalid simulator request parameters."""
    # Invalid scenario type
    res = await async_client.post(
        "/api/v1/simulator/generate",
        json={"workflow_count": 10, "incident_scenario": "non_existent_chaos"},
    )
    assert res.status_code == 400
    assert "Invalid incident_scenario" in res.json()["detail"]

    # Out of bounds workflow count (422 Unprocessable Entity)
    res_bounds = await async_client.post(
        "/api/v1/simulator/generate",
        json={"workflow_count": 20000},  # Max allowed is 10,000
    )
    assert res_bounds.status_code == 422
