"""Unit tests for ServiceLatencyAnomalyDetector."""

from datetime import UTC, datetime

from apps.ml.anomalies.latency_detector import ServiceLatencyAnomalyDetector
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.domain.intelligence import AnomalyType


def test_service_latency_detector_fit_and_detect():
    detector = ServiceLatencyAnomalyDetector(iqr_factor=2.5, z_threshold=3.0)

    # 1. Fit nominal baseline spans for auth-service and payment-service
    now = datetime.now(UTC)
    nominal_spans = []
    for _ in range(50):
        nominal_spans.append(
            TraceEvent(
                event_id="e_nom_auth",
                execution_id="exec_1",
                workflow_id="order_fulfillment",
                service="auth-service",
                operation="auth",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=22.0,
                timestamp=now,
            )
        )
        nominal_spans.append(
            TraceEvent(
                event_id="e_nom_pay",
                execution_id="exec_1",
                workflow_id="order_fulfillment",
                service="payment-service",
                operation="charge",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=250.0,
                timestamp=now,
            )
        )

    detector.fit_from_events(nominal_spans)
    assert detector.is_fitted
    assert "auth-service" in detector.service_stats
    assert "payment-service" in detector.service_stats

    # 2. Test nominal execution (no anomalies)
    nom_test = [
        TraceEvent(
            event_id="t1",
            execution_id="exec_test_nom",
            workflow_id="order_fulfillment",
            service="auth-service",
            operation="auth",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=23.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="t2",
            execution_id="exec_test_nom",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="charge",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=255.0,
            timestamp=now,
        ),
    ]
    anoms_nom = detector.detect(nom_test, execution_id="exec_test_nom")
    assert len(anoms_nom) == 0

    # 3. Test latency spike on payment-service (1800ms vs 250ms median)
    degraded_test = [
        TraceEvent(
            event_id="t3",
            execution_id="exec_test_deg",
            workflow_id="order_fulfillment",
            service="auth-service",
            operation="auth",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=22.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="t4",
            execution_id="exec_test_deg",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="charge",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=1800.0,
            timestamp=now,
        ),
    ]
    anoms_deg = detector.detect(degraded_test, execution_id="exec_test_deg")
    assert len(anoms_deg) >= 1
    anom = anoms_deg[0]
    assert anom.anomaly_type in (AnomalyType.LATENCY_SPIKE, AnomalyType.DEPENDENCY_TIMEOUT)
    assert anom.score >= 0.70
    assert "payment-service" in anom.affected_services
    assert anom.evidence["measured_latency_ms"] == 1800.0
