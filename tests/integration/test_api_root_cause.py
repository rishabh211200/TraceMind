"""Integration tests for FastAPI Root Cause REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_root_cause_analyze_and_query_flow(async_client: AsyncClient):
    # 1. Analyze on in-memory spans with persistence
    payload = {
        "execution_id": "test_exec_rc_flow_01",
        "workflow_definition_id": "order_fulfillment",
        "events": [
            {
                "event_id": "e1",
                "execution_id": "test_exec_rc_flow_01",
                "workflow_id": "order_fulfillment",
                "service": "api-gateway",
                "operation": "route",
                "event_type": "SERVICE_COMPLETED",
                "status": "SUCCESS",
                "latency_ms": 15.0,
                "timestamp": "2026-08-24T12:00:00Z",
            },
            {
                "event_id": "e2",
                "execution_id": "test_exec_rc_flow_01",
                "workflow_id": "order_fulfillment",
                "service": "order-service",
                "operation": "process",
                "event_type": "SERVICE_COMPLETED",
                "status": "SUCCESS",
                "latency_ms": 25.0,
                "timestamp": "2026-08-24T12:00:01Z",
            },
            {
                "event_id": "e3",
                "execution_id": "test_exec_rc_flow_01",
                "workflow_id": "order_fulfillment",
                "service": "inventory-db",
                "operation": "query",
                "event_type": "SERVICE_COMPLETED",
                "status": "FAILURE",
                "latency_ms": 1850.0,
                "timestamp": "2026-08-24T12:00:02Z",
            },
        ],
        "anomalies": [
            {
                "id": "anom_01",
                "anomaly_type": "LATENCY_SPIKE",
                "score": 0.88,
                "affected_services": ["inventory-db"],
            }
        ],
        "persist_to_db": True,
    }

    resp = await async_client.post("/api/v1/root-cause/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == "test_exec_rc_flow_01"
    assert data["culprit_service"] == "inventory-db"
    assert data["incident_category"] == "DATABASE_IOPS_SATURATION"
    assert data["confidence"] >= 0.70
    report_id = data["id"]

    # 2. Get reports by execution ID
    resp_exec = await async_client.get("/api/v1/root-cause/executions/test_exec_rc_flow_01")
    assert resp_exec.status_code == 200
    exec_reports = resp_exec.json()
    assert len(exec_reports) >= 1
    assert exec_reports[0]["culprit_service"] == "inventory-db"

    # 3. Get single report details
    resp_single = await async_client.get(f"/api/v1/root-cause/{report_id}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["id"] == report_id
    assert single_data["culprit_service"] == "inventory-db"
    assert len(single_data["supporting_evidence"]) >= 1

    # 4. Search and filter reports list
    resp_list = await async_client.get("/api/v1/root-cause?culprit_service=inventory-db")
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data["pagination"]["total"] >= 1
    assert any(item["id"] == report_id for item in list_data["items"])

    # 5. Get aggregate statistics
    resp_stats = await async_client.get("/api/v1/root-cause/stats")
    assert resp_stats.status_code == 200
    stats_data = resp_stats.json()
    assert stats_data["total_diagnoses"] >= 1
    assert "inventory-db" in stats_data["by_culprit_service"]
