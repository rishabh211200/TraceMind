"""Unit tests for Root Cause Engine reasoning and multi-hypothesis ranking."""

from datetime import UTC, datetime, timedelta

from apps.ml.root_cause.engine import RootCauseEngine
from packages.domain.events import EventStatus, EventType, TraceEvent


def test_root_cause_engine_diagnosis():
    engine = RootCauseEngine()
    now = datetime.now(UTC)

    events = [
        TraceEvent(
            event_id="e1",
            execution_id="exec_rc_1",
            workflow_id="order_fulfillment",
            service="api-gateway",
            operation="route",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=15.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="e2",
            execution_id="exec_rc_1",
            workflow_id="order_fulfillment",
            service="order-service",
            operation="checkout",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=30.0,
            timestamp=now + timedelta(milliseconds=15),
        ),
        TraceEvent(
            event_id="e3",
            execution_id="exec_rc_1",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="process_payment",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.FAILURE,
            latency_ms=2500.0,
            timestamp=now + timedelta(milliseconds=45),
        ),
    ]

    anomalies = [
        {
            "id": "anom_1",
            "anomaly_type": "LATENCY_SPIKE",
            "score": 0.92,
            "affected_services": ["payment-service"],
            "evidence": {"measured_latency_ms": 2500.0},
        }
    ]

    shap_contribs = [{"feature_name": "payment_service_duration_ms", "contribution": 0.65}]

    report = engine.diagnose_execution(
        events=events,
        anomalies=anomalies,
        shap_contributions=shap_contribs,
        execution_id="exec_rc_1",
    )

    assert report.execution_id == "exec_rc_1"
    assert report.culprit_service == "payment-service"
    assert report.confidence >= 0.70
    assert len(report.supporting_evidence) >= 2
    assert report.primary_hypothesis.culprit_service == "payment-service"


def test_root_cause_engine_empty_fallback():
    engine = RootCauseEngine()
    report = engine.diagnose_execution(events=[], execution_id="empty_exec")
    assert report.execution_id == "empty_exec"
    assert report.culprit_service == "unknown"
    assert report.confidence == 0.50
