"""Unit tests for ErrorCascadeAnomalyDetector."""

from datetime import UTC, datetime, timedelta

from apps.ml.anomalies.cascade_detector import ErrorCascadeAnomalyDetector
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.domain.intelligence import AnomalyType


def test_error_cascade_and_retry_storm_detection():
    detector = ErrorCascadeAnomalyDetector(min_retry_count=3, min_cascade_services=2)
    now = datetime.now(UTC)

    # 1. Test Retry Storm on payment-service
    retry_events = [
        TraceEvent(
            event_id=f"r_{i}",
            execution_id="exec_retry",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="charge",
            event_type=EventType.RETRY_STARTED,
            status=EventStatus.RETRY,
            latency_ms=200.0,
            timestamp=now + timedelta(milliseconds=i * 200),
        )
        for i in range(4)
    ]

    anoms_retry = detector.detect(retry_events, execution_id="exec_retry")
    assert any(a.anomaly_type == AnomalyType.RETRY_STORM for a in anoms_retry)
    retry_anom = [a for a in anoms_retry if a.anomaly_type == AnomalyType.RETRY_STORM][0]
    assert retry_anom.evidence["retry_count"] == 4
    assert "payment-service" in retry_anom.affected_services

    # 2. Test Multi-Service Error Cascade
    cascade_events = [
        TraceEvent(
            event_id="c1",
            execution_id="exec_cascade",
            workflow_id="order_fulfillment",
            service="inventory-service",
            operation="reserve",
            event_type=EventType.SERVICE_FAILED,
            status=EventStatus.FAILURE,
            latency_ms=100.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="c2",
            execution_id="exec_cascade",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="charge",
            event_type=EventType.SERVICE_FAILED,
            status=EventStatus.FAILURE,
            latency_ms=150.0,
            timestamp=now + timedelta(milliseconds=50),
        ),
        TraceEvent(
            event_id="c3",
            execution_id="exec_cascade",
            workflow_id="order_fulfillment",
            service="order-service",
            operation="fulfill",
            event_type=EventType.SERVICE_FAILED,
            status=EventStatus.FAILURE,
            latency_ms=80.0,
            timestamp=now + timedelta(milliseconds=100),
        ),
    ]

    anoms_cascade = detector.detect(cascade_events, execution_id="exec_cascade")
    assert any(a.anomaly_type == AnomalyType.ERROR_CASCADE for a in anoms_cascade)
    casc_anom = [a for a in anoms_cascade if a.anomaly_type == AnomalyType.ERROR_CASCADE][0]
    assert casc_anom.score >= 0.70
    assert len(casc_anom.affected_services) == 3
