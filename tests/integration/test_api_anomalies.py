"""Integration tests for FastAPI Anomaly Detection REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_anomalies_detect_and_query_flow(async_client: AsyncClient):
    # 1. Detect on in-memory anomalous spans with database persistence
    payload = {
        "execution_id": "test_exec_anomaly_flow_01",
        "workflow_definition_id": "order_fulfillment",
        "events": [
            {
                "event_id": "e1",
                "execution_id": "test_exec_anomaly_flow_01",
                "workflow_id": "order_fulfillment",
                "service": "auth-service",
                "operation": "auth",
                "event_type": "SERVICE_COMPLETED",
                "status": "SUCCESS",
                "latency_ms": 20.0,
                "timestamp": "2026-08-24T12:00:00Z",
            },
            {
                "event_id": "e2",
                "execution_id": "test_exec_anomaly_flow_01",
                "workflow_id": "order_fulfillment",
                "service": "payment-service",
                "operation": "charge",
                "event_type": "SERVICE_FAILED",
                "status": "FAILURE",
                "latency_ms": 2400.0,
                "timestamp": "2026-08-24T12:00:01Z",
            },
        ],
        "persist_to_db": True,
    }

    resp = await async_client.post("/api/v1/anomalies/detect", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == "test_exec_anomaly_flow_01"
    assert data["is_anomalous"] is True
    assert data["anomaly_count"] >= 1
    anom_id = data["anomalies"][0]["id"]

    # 2. Get anomalies by execution ID
    resp_exec = await async_client.get("/api/v1/anomalies/executions/test_exec_anomaly_flow_01")
    assert resp_exec.status_code == 200
    exec_anoms = resp_exec.json()
    assert len(exec_anoms) >= 1
    assert exec_anoms[0]["id"] == anom_id

    # 3. Get single anomaly details
    resp_single = await async_client.get(f"/api/v1/anomalies/{anom_id}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["id"] == anom_id
    assert "payment-service" in single_data["affected_services"]

    # 4. List anomalies with filter
    resp_list = await async_client.get("/api/v1/anomalies?page=1&page_size=10")
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data["pagination"]["total"] >= 1

    # 5. Get anomaly stats
    resp_stats = await async_client.get("/api/v1/anomalies/stats")
    assert resp_stats.status_code == 200
    stats_data = resp_stats.json()
    assert stats_data["total_anomalies"] >= 1
    assert "by_severity" in stats_data

    # 6. Fit / Calibrate baseline distributions
    resp_fit = await async_client.post(
        "/api/v1/anomalies/fit", json={"nominal_workflows": 30, "seed": 42}
    )
    assert resp_fit.status_code == 200
    fit_data = resp_fit.json()
    assert fit_data["status"] == "success"
    assert len(fit_data["services_fitted"]) > 0
