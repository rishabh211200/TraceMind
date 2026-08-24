"""Unit tests for TransitionPathAnomalyDetector."""

from datetime import UTC, datetime

from apps.ml.anomalies.sequence_detector import TransitionPathAnomalyDetector
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.domain.intelligence import AnomalyType


def test_transition_path_detector_fit_and_detect():
    detector = TransitionPathAnomalyDetector()
    now = datetime.now(UTC)

    # 1. Fit nominal sequential flows: auth -> customer -> inventory -> payment
    nominal_map = {}
    for i in range(20):
        nominal_map[f"nom_exec_{i}"] = [
            TraceEvent(
                event_id="e1",
                execution_id=f"nom_exec_{i}",
                workflow_id="order_fulfillment",
                service="auth-service",
                operation="auth",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=20.0,
                timestamp=now,
            ),
            TraceEvent(
                event_id="e2",
                execution_id=f"nom_exec_{i}",
                workflow_id="order_fulfillment",
                service="customer-service",
                operation="get_profile",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=30.0,
                timestamp=now,
            ),
            TraceEvent(
                event_id="e3",
                execution_id=f"nom_exec_{i}",
                workflow_id="order_fulfillment",
                service="inventory-service",
                operation="reserve",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=40.0,
                timestamp=now,
            ),
            TraceEvent(
                event_id="e4",
                execution_id=f"nom_exec_{i}",
                workflow_id="order_fulfillment",
                service="payment-service",
                operation="charge",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=50.0,
                timestamp=now,
            ),
        ]

    detector.fit(nominal_map)
    assert detector.is_fitted
    assert "auth-service" in detector.transition_probs
    assert "customer-service" in detector.transition_probs["auth-service"]

    # 2. Test nominal execution path (should produce 0 anomalies)
    nom_events = nominal_map["nom_exec_0"]
    anoms_nom = detector.detect(nom_events, execution_id="nom_test")
    assert len(anoms_nom) == 0

    # 3. Test anomalous execution with illegal transition: payment -> auth (circular loop)
    anom_events = [
        TraceEvent(
            event_id="a1",
            execution_id="anom_test",
            workflow_id="order_fulfillment",
            service="auth-service",
            operation="auth",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=20.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="a2",
            execution_id="anom_test",
            workflow_id="order_fulfillment",
            service="payment-service",
            operation="charge",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=50.0,
            timestamp=now,
        ),
        TraceEvent(
            event_id="a3",
            execution_id="anom_test",
            workflow_id="order_fulfillment",
            service="auth-service",
            operation="auth",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.SUCCESS,
            latency_ms=20.0,
            timestamp=now,
        ),
    ]

    anoms_path = detector.detect(anom_events, execution_id="anom_test")
    assert len(anoms_path) >= 1
    assert anoms_path[0].anomaly_type == AnomalyType.UNUSUAL_PATH
    assert anoms_path[0].score >= 0.50
