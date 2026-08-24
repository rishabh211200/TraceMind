"""Integration tests for ML prediction endpoints and TreeSHAP explainability."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_predict_endpoint_with_partial_events(async_client: AsyncClient):
    """Test on-demand in-flight prediction from partial span payload."""
    payload = {
        "execution_id": "test_exec_001",
        "workflow_definition_id": "order_fulfillment",
        "events": [
            {
                "event_id": "e1",
                "execution_id": "test_exec_001",
                "workflow_id": "order_fulfillment",
                "service": "auth-service",
                "operation": "auth",
                "event_type": "SERVICE_COMPLETED",
                "status": "SUCCESS",
                "latency_ms": 22.0,
                "timestamp": "2026-08-24T12:00:00Z",
            },
            {
                "event_id": "e2",
                "execution_id": "test_exec_001",
                "workflow_id": "order_fulfillment",
                "service": "payment-service",
                "operation": "charge",
                "event_type": "SERVICE_FAILED",
                "status": "FAILURE",
                "latency_ms": 1250.0,
                "timestamp": "2026-08-24T12:00:01Z",
            },
        ],
        "persist_to_db": True,
    }

    res = await async_client.post("/api/v1/predictions/predict", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["execution_id"] == "test_exec_001"
    assert "failure_probability" in data
    assert 0.0 <= data["failure_probability"] <= 1.0
    assert data["predicted_risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert data["predicted_latency_ms"] >= 0.0
    assert "top_contributions" in data
    assert isinstance(data["top_contributions"], list)

    # Verify TreeSHAP attributions exist
    if data["top_contributions"]:
        first_attr = data["top_contributions"][0]
        assert "feature_name" in first_attr
        assert "contribution" in first_attr
        assert "description" in first_attr

    # Verify persisted execution predictions query
    get_res = await async_client.get("/api/v1/predictions/executions/test_exec_001")
    assert get_res.status_code == 200
    preds = get_res.json()
    assert len(preds) >= 1
    assert preds[0]["id"] == data["id"]


@pytest.mark.asyncio
async def test_get_models_endpoint(async_client: AsyncClient):
    """Test inspecting active ML model metadata and feature list."""
    res = await async_client.get("/api/v1/predictions/models")
    assert res.status_code == 200
    data = res.json()

    assert data["version"] is not None
    assert "features" in data
    assert "step_count" in data["features"]
    assert "payment_service_latency_ms" in data["features"]


@pytest.mark.asyncio
async def test_train_endpoint(async_client: AsyncClient):
    """Test triggering offline retraining of ML models."""
    payload = {
        "nominal_workflows": 30,
        "incident_workflows_per_scenario": 5,
        "random_state": 777,
        "version": "1.1.0",
    }
    res = await async_client.post("/api/v1/predictions/train", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "trained"
    assert data["version"] == "1.1.0"
    assert data["training_samples"] > 0
    assert "metrics" in data
    assert "classification" in data["metrics"]
    assert "regression" in data["metrics"]
