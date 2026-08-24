"""Unit tests for CompositeAnomalyDetector and AnomalyDetectorRegistry."""

from datetime import UTC, datetime

from apps.ml.anomalies.composite import CompositeAnomalyDetector
from apps.ml.anomalies.registry import AnomalyDetectorRegistry
from packages.domain.events import EventStatus, EventType, TraceEvent


def test_composite_anomaly_detector_aggregation():
    registry = AnomalyDetectorRegistry()
    detector = registry.get_detector()
    assert isinstance(detector, CompositeAnomalyDetector)

    now = datetime.now(UTC)

    # 1. Test nominal spans
    nom_spans = [
        TraceEvent(
            event_id="e1",
            execution_id="nom_comp",
            workflow_id="order_fulfillment",
            service="auth-service",
            operation="auth",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=22.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="e2",
            execution_id="nom_comp",
            workflow_id="order_fulfillment",
            service="customer-service",
            operation="get_profile",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=45.0,
            timestamp=now,
        ),
    ]

    anoms_nom = detector.detect_anomalies(nom_spans, execution_id="nom_comp")
    assert len(anoms_nom) == 0

    # 2. Test severe degraded spans
    deg_spans = [
        TraceEvent(
            event_id="d1",
            execution_id="deg_comp",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="charge",
            event_type=EventType.SERVICE_FAILED,
            status=EventStatus.FAILURE,
            latency_ms=2800.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="d2",
            execution_id="deg_comp",
            workflow_id="order_fulfillment",
            service="order-service",
            operation="fulfill",
            event_type=EventType.SERVICE_FAILED,
            status=EventStatus.FAILURE,
            latency_ms=1200.0,
            timestamp=now,
        ),
    ]

    anoms_deg = detector.detect_anomalies(deg_spans, execution_id="deg_comp")
    assert len(anoms_deg) >= 1
    assert any(a.score >= 0.70 for a in anoms_deg)
    assert detector.get_severity_label(anoms_deg[0].score) in ("CRITICAL", "WARNING")
