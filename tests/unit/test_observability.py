"""Unit tests for OpenTelemetry tracer, W3C traceparent propagation, and Prometheus metrics."""

import logging

import pytest

from packages.common.logging import add_opentelemetry_context
from packages.observability.metrics import (
    record_analyst_query,
    record_anomaly,
    record_http_request,
    record_kafka_ingestion,
    record_ml_inference,
    record_optimization,
    record_root_cause,
    set_active_database_connections,
)
from packages.observability.middleware import normalize_endpoint_path
from packages.observability.tracer import (
    format_w3c_traceparent,
    get_tracer,
    init_tracer,
    parse_w3c_traceparent,
    trace_async_span,
    trace_span,
)


def test_w3c_traceparent_format_and_parse():
    """Verify W3C traceparent formatting and parsing conform to W3C specification."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id = "00f067aa0ba902b7"

    header = format_w3c_traceparent(trace_id, span_id, sampled=True)
    assert header == f"00-{trace_id}-{span_id}-01"

    parsed_trace, parsed_span, sampled = parse_w3c_traceparent(header)
    assert parsed_trace == trace_id
    assert parsed_span == span_id
    assert sampled is True

    # Test unsampled flag
    unsampled_header = format_w3c_traceparent(trace_id, span_id, sampled=False)
    assert unsampled_header == f"00-{trace_id}-{span_id}-00"
    _, _, parsed_sampled = parse_w3c_traceparent(unsampled_header)
    assert parsed_sampled is False

    # Invalid / empty traceparent handling (Fail-open)
    assert parse_w3c_traceparent(None) == (None, None, False)
    assert parse_w3c_traceparent("") == (None, None, False)
    assert parse_w3c_traceparent("invalid-format") == (None, None, False)
    assert parse_w3c_traceparent("00-00000000000000000000000000000000-0000000000000000-01") == (
        None,
        None,
        False,
    )


def test_endpoint_normalization_low_cardinality():
    """Verify dynamic IDs are replaced with generic :id placeholders to prevent cardinality explosion."""
    assert normalize_endpoint_path("/api/v1/traces/exec_4a9b") == "/api/v1/traces/:id"
    assert normalize_endpoint_path("/api/v1/optimizer/opt_12345") == "/api/v1/optimizer/:id"
    assert (
        normalize_endpoint_path("/api/v1/analyst/conversations/conv_abc_999")
        == "/api/v1/analyst/conversations/:id"
    )
    assert (
        normalize_endpoint_path("/api/v1/workflows/order_fulfillment")
        == "/api/v1/workflows/order_fulfillment"
    )
    assert normalize_endpoint_path("/api/v1/health") == "/api/v1/health"
    assert normalize_endpoint_path("/metrics") == "/metrics"


def test_opentelemetry_tracer_and_spans():
    """Verify tracer initialization and span context manager execution."""
    tracer = init_tracer("tracemind-test-suite")
    assert tracer is not None

    with trace_span("test_span_operation", {"service": "test-svc", "count": 42}) as span:
        assert span is not None
        assert span.is_recording()


@pytest.mark.asyncio
async def test_opentelemetry_async_span():
    """Verify asynchronous span context manager."""
    async with trace_async_span("test_async_operation", {"status": "ok"}) as span:
        assert span is not None
        assert span.is_recording()


def test_prometheus_metrics_recording_helpers():
    """Verify metric recording helper functions execute safely without raising exceptions."""
    # HTTP metrics
    record_http_request("GET", "/api/v1/health", 200, 0.005)
    record_http_request("POST", "/api/v1/predictions/predict", 200, 0.025)

    # ML metrics
    record_ml_inference("xgboost_workflow_predictor", "predict_failure", 0.003, "HIGH")

    # Anomaly metrics
    record_anomaly("ISOLATION_FOREST", "CRITICAL")

    # Root cause metrics
    record_root_cause("DATABASE_IOPS_SATURATION", "inventory-db")

    # Optimizer metrics
    record_optimization("MULTI_OBJECTIVE", "order_fulfillment")

    # Analyst metrics
    record_analyst_query("mock", "success", 0.98)

    # Kafka metrics
    record_kafka_ingestion("tracemind-trace-events", 100)

    # DB connection gauge
    set_active_database_connections(5)


def test_structlog_opentelemetry_context_enrichment():
    """Verify logging processor injects active OpenTelemetry span context."""
    tracer = get_tracer()
    with tracer.start_as_current_span("log_test_span"):
        dummy_logger = logging.getLogger("test")
        event_dict: dict = {"event": "test_event"}
        enriched = add_opentelemetry_context(dummy_logger, "info", event_dict)
        assert "trace_id" in enriched
        assert "span_id" in enriched
        assert len(enriched["trace_id"]) == 32
        assert len(enriched["span_id"]) == 16
