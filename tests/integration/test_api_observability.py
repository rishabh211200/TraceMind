"""Integration tests for FastAPI OpenTelemetry distributed tracing and Prometheus metrics endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_metrics_exposition_endpoint(async_client: AsyncClient):
    """Test GET /metrics returns valid Prometheus exposition text."""
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")

    content = resp.text
    assert "# HELP tracemind_http_requests_total" in content
    assert "# TYPE tracemind_http_requests_total counter" in content
    assert "# HELP tracemind_http_request_duration_seconds" in content
    assert "# HELP tracemind_ml_inference_duration_seconds" in content
    assert "# HELP tracemind_anomalies_detected_total" in content
    assert "# HELP tracemind_root_cause_diagnoses_total" in content
    assert "# HELP tracemind_workflow_optimizations_total" in content
    assert "# HELP tracemind_analyst_grounding_score" in content


@pytest.mark.asyncio
async def test_api_tracing_response_headers(async_client: AsyncClient):
    """Test that every API request automatically receives W3C traceparent and correlation headers."""
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "traceparent" in resp.headers
    assert "X-Trace-Id" in resp.headers
    assert "X-Span-Id" in resp.headers

    traceparent = resp.headers["traceparent"]
    assert traceparent.startswith("00-")
    assert resp.headers["X-Trace-Id"] in traceparent


@pytest.mark.asyncio
async def test_api_inbound_traceparent_context_propagation(async_client: AsyncClient):
    """Test that incoming W3C traceparent context is preserved across downstream response headers."""
    inbound_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    inbound_parent_id = "00f067aa0ba902b7"
    inbound_header = f"00-{inbound_trace_id}-{inbound_parent_id}-01"

    resp = await async_client.get(
        "/api/v1/health",
        headers={"traceparent": inbound_header},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Trace-Id") == inbound_trace_id
    assert resp.headers.get("traceparent", "").startswith(f"00-{inbound_trace_id}-")


@pytest.mark.asyncio
async def test_api_metrics_counter_increments(async_client: AsyncClient):
    """Test that API endpoint invocations increment Prometheus counters."""
    # Call health check multiple times
    for _ in range(5):
        await async_client.get("/api/v1/health")

    metrics_resp = await async_client.get("/metrics")
    assert metrics_resp.status_code == 200
    metrics_text = metrics_resp.text
    assert (
        'tracemind_http_requests_total{endpoint="/api/v1/health",method="GET",status_code="200"}'
        in metrics_text
    )
