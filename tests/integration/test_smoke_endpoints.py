"""Integration tests verifying the 11-subsystem smoke test suite execution."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_subsystem_1_health_probe(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "healthy"


@pytest.mark.asyncio
async def test_subsystem_2_root_metadata(async_client: AsyncClient):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "service" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_3_topology_graph(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/services/topology")
    assert resp.status_code == 200
    assert "nodes" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_4_workflow_registry(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/workflows")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_subsystem_5_simulator_generate(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/simulator/generate",
        json={"workflow_count": 5, "seed": 42, "inject_incidents": False, "persist_to_db": False},
    )
    assert resp.status_code == 200
    assert resp.json().get("executions_generated") == 5


@pytest.mark.asyncio
async def test_subsystem_6_ml_prediction_and_shap(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "execution_id": "exec_smoke_01",
            "workflow_definition_id": "order_fulfillment",
            "events": [
                {
                    "event_id": "ev_01",
                    "execution_id": "exec_smoke_01",
                    "service": "auth-service",
                    "operation": "verify_token",
                    "event_type": "SPAN_START",
                    "status": "SUCCESS",
                    "latency_ms": 12.5,
                    "timestamp": "2026-08-29T12:00:00Z",
                }
            ],
            "persist_to_db": False,
        },
    )
    assert resp.status_code == 200
    assert "failure_probability" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_7_anomaly_detection(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/anomalies/detect",
        json={
            "execution_id": "exec_smoke_02",
            "workflow_definition_id": "order_fulfillment",
            "events": [
                {
                    "event_id": "ev_02",
                    "execution_id": "exec_smoke_02",
                    "service": "payment-gateway",
                    "operation": "process_charge",
                    "event_type": "SPAN_START",
                    "status": "ERROR",
                    "latency_ms": 850.0,
                    "timestamp": "2026-08-29T12:00:00Z",
                }
            ],
            "persist_to_db": False,
        },
    )
    assert resp.status_code == 200
    assert "anomalies" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_8_root_cause_analysis(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/root-cause/analyze",
        json={
            "execution_id": "exec_smoke_03",
            "workflow_definition_id": "order_fulfillment",
            "events": [
                {
                    "event_id": "ev_03",
                    "execution_id": "exec_smoke_03",
                    "service": "inventory-db",
                    "operation": "query_stock",
                    "event_type": "SPAN_START",
                    "status": "ERROR",
                    "latency_ms": 1200.0,
                    "timestamp": "2026-08-29T12:00:00Z",
                }
            ],
            "persist_to_db": False,
        },
    )
    assert resp.status_code == 200
    assert "culprit_service" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_9_pareto_optimizer(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/optimizer/recommend",
        json={
            "workflow_definition_id": "order_fulfillment",
            "latency_weight": 0.4,
            "cost_weight": 0.3,
            "reliability_weight": 0.3,
        },
    )
    assert resp.status_code == 200
    assert "recommended_path" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_10_ai_analyst_chat(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/analyst/chat",
        json={
            "query": "What is the health of the system topology?",
            "provider": "mock",
            "persist": False,
        },
    )
    assert resp.status_code == 200
    assert "content" in resp.json()


@pytest.mark.asyncio
async def test_subsystem_11_prometheus_metrics(async_client: AsyncClient):
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    assert "tracemind_http_requests_total" in resp.text
