"""Prometheus metric collectors, custom registries, and low-cardinality recording helpers."""

from collections.abc import Sequence
from typing import Any

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
)

from packages.common.logging import get_logger

logger = get_logger("tracemind.observability.metrics")


def _get_or_create_metric(
    metric_type: type,
    name: str,
    documentation: str,
    labelnames: Sequence[str] = (),
    **kwargs: Any,
) -> Any:
    """Safely register or retrieve existing metric from registry to prevent duplicate registration errors."""
    try:
        return metric_type(name, documentation, labelnames=labelnames, registry=REGISTRY, **kwargs)
    except ValueError:
        # Metric already registered in default registry
        return REGISTRY._names_to_collectors.get(name)


# HTTP Request Metrics (Normalized route templates only)
HTTP_REQUESTS_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_http_requests_total",
    "Total number of HTTP requests processed by TraceMind API",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS: Histogram = _get_or_create_metric(
    Histogram,
    "tracemind_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ML & Intelligence Metrics
ML_INFERENCE_DURATION_SECONDS: Histogram = _get_or_create_metric(
    Histogram,
    "tracemind_ml_inference_duration_seconds",
    "ML model inference duration in seconds",
    ["model_name", "task"],
    buckets=[0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

ML_PREDICTIONS_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_ml_predictions_total",
    "Total in-flight failure and latency predictions generated",
    ["model_name", "risk_level"],
)

# Unsupervised Anomaly Detection Metrics
ANOMALIES_DETECTED_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_anomalies_detected_total",
    "Total anomalies detected by detector type and severity",
    ["detector_type", "severity"],
)

# Deterministic Root Cause Analysis Metrics
ROOT_CAUSE_DIAGNOSES_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_root_cause_diagnoses_total",
    "Total root cause diagnoses executed by incident category",
    ["category", "culprit_service"],
)

# Multi-Objective Workflow Optimizer Metrics
WORKFLOW_OPTIMIZATIONS_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_workflow_optimizations_total",
    "Total multi-objective workflow optimizations calculated",
    ["optimization_type", "workflow_id"],
)

# Conversational AI Analyst Metrics
ANALYST_QUERIES_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_analyst_queries_total",
    "Total conversational AI Analyst turns processed",
    ["provider", "status"],
)

ANALYST_GROUNDING_SCORE: Gauge = _get_or_create_metric(
    Gauge,
    "tracemind_analyst_grounding_score",
    "Latest AI Analyst grounding compliance score (0.0 to 1.0)",
    ["provider"],
)

# Event Streaming & Ingestion Metrics
KAFKA_MESSAGES_INGESTED_TOTAL: Counter = _get_or_create_metric(
    Counter,
    "tracemind_kafka_messages_ingested_total",
    "Total trace events ingested from Kafka stream",
    ["topic"],
)

DATABASE_CONNECTIONS_ACTIVE: Gauge = _get_or_create_metric(
    Gauge,
    "tracemind_database_connections_active",
    "Active asyncpg database connections in connection pool",
)


# Fail-open recording helper functions
def record_http_request(
    method: str, endpoint: str, status_code: int, duration_seconds: float
) -> None:
    """Record HTTP request metrics with strict low-cardinality guarantees and fail-open protection."""
    try:
        norm_method = method.upper()
        norm_status = str(status_code)
        HTTP_REQUESTS_TOTAL.labels(
            method=norm_method, endpoint=endpoint, status_code=norm_status
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=norm_method, endpoint=endpoint).observe(
            duration_seconds
        )
    except Exception as exc:
        logger.warning("prometheus_http_record_failed", error=str(exc))


def record_ml_inference(
    model_name: str, task: str, duration_seconds: float, risk_level: str = "NORMAL"
) -> None:
    """Record ML inference duration and prediction counts."""
    try:
        ML_INFERENCE_DURATION_SECONDS.labels(model_name=model_name, task=task).observe(
            duration_seconds
        )
        ML_PREDICTIONS_TOTAL.labels(model_name=model_name, risk_level=risk_level).inc()
    except Exception as exc:
        logger.warning("prometheus_ml_record_failed", error=str(exc))


def record_anomaly(detector_type: str, severity: str = "MEDIUM") -> None:
    """Record detected anomaly."""
    try:
        ANOMALIES_DETECTED_TOTAL.labels(detector_type=detector_type, severity=severity).inc()
    except Exception as exc:
        logger.warning("prometheus_anomaly_record_failed", error=str(exc))


def record_root_cause(category: str, culprit_service: str) -> None:
    """Record root cause diagnosis execution."""
    try:
        ROOT_CAUSE_DIAGNOSES_TOTAL.labels(category=category, culprit_service=culprit_service).inc()
    except Exception as exc:
        logger.warning("prometheus_rca_record_failed", error=str(exc))


def record_optimization(optimization_type: str, workflow_id: str = "order_fulfillment") -> None:
    """Record workflow path optimization calculation."""
    try:
        WORKFLOW_OPTIMIZATIONS_TOTAL.labels(
            optimization_type=optimization_type, workflow_id=workflow_id
        ).inc()
    except Exception as exc:
        logger.warning("prometheus_optimizer_record_failed", error=str(exc))


def record_analyst_query(provider: str, status: str, grounding_score: float = 1.0) -> None:
    """Record conversational AI Analyst execution and grounding score."""
    try:
        ANALYST_QUERIES_TOTAL.labels(provider=provider, status=status).inc()
        ANALYST_GROUNDING_SCORE.labels(provider=provider).set(grounding_score)
    except Exception as exc:
        logger.warning("prometheus_analyst_record_failed", error=str(exc))


def record_kafka_ingestion(topic: str = "tracemind-trace-events", count: int = 1) -> None:
    """Record Kafka streaming messages ingested."""
    try:
        KAFKA_MESSAGES_INGESTED_TOTAL.labels(topic=topic).inc(count)
    except Exception as exc:
        logger.warning("prometheus_kafka_record_failed", error=str(exc))


def set_active_database_connections(count: int) -> None:
    """Update active database connection gauge."""
    try:
        DATABASE_CONNECTIONS_ACTIVE.set(count)
    except Exception as exc:
        logger.warning("prometheus_db_gauge_failed", error=str(exc))
