"""Unit tests for in-flight temporal feature extraction pipeline."""

from datetime import UTC, datetime, timedelta

from apps.ml.features import FEATURE_NAMES, TraceFeatureExtractor
from packages.domain.events import EventStatus, EventType, TraceEvent


def _create_sample_span(
    execution_id: str,
    service: str,
    operation: str,
    latency_ms: float,
    status: EventStatus = EventStatus.SUCCESS,
    event_type: EventType = EventType.SERVICE_COMPLETED,
    offset_seconds: float = 0.0,
    base_time: datetime | None = None,
) -> TraceEvent:
    base = base_time or datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    return TraceEvent(
        event_id=f"evt_{service}_{int(offset_seconds * 1000)}",
        execution_id=execution_id,
        workflow_id="order_fulfillment",
        service=service,
        operation=operation,
        event_type=event_type,
        status=status,
        latency_ms=latency_ms,
        timestamp=base + timedelta(seconds=offset_seconds),
    )


def test_feature_extractor_returns_all_canonical_features():
    extractor = TraceFeatureExtractor()
    feats = extractor.extract_features_from_events([])
    assert set(feats.keys()) == set(FEATURE_NAMES)
    for v in feats.values():
        assert v == 0.0


def test_feature_extractor_calculates_correct_metrics():
    extractor = TraceFeatureExtractor()
    base_time = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)

    events = [
        _create_sample_span(
            "exec_1", "auth-service", "auth_user", 25.0, offset_seconds=0.0, base_time=base_time
        ),
        _create_sample_span(
            "exec_1", "customer-service", "get_cust", 40.0, offset_seconds=0.03, base_time=base_time
        ),
        _create_sample_span(
            "exec_1",
            "customer-cache",
            "lookup",
            5.0,
            event_type=EventType.CACHE_MISS,
            offset_seconds=0.04,
            base_time=base_time,
        ),
        _create_sample_span(
            "exec_1",
            "customer-db",
            "query_db",
            35.0,
            event_type=EventType.DATABASE_QUERY,
            offset_seconds=0.08,
            base_time=base_time,
        ),
        _create_sample_span(
            "exec_1",
            "payment-service",
            "charge",
            800.0,
            status=EventStatus.FAILURE,
            event_type=EventType.SERVICE_FAILED,
            offset_seconds=0.15,
            base_time=base_time,
        ),
        _create_sample_span(
            "exec_1",
            "payment-service",
            "retry_charge",
            300.0,
            status=EventStatus.RETRY,
            event_type=EventType.RETRY_STARTED,
            offset_seconds=0.95,
            base_time=base_time,
        ),
    ]

    feats = extractor.extract_features_from_events(events)

    assert feats["step_count"] == 6.0
    assert feats["cumulative_retries"] == 1.0
    assert feats["cumulative_errors"] == 1.0
    assert feats["has_cache_miss"] == 1.0
    assert feats["has_database_query"] == 1.0
    assert feats["auth_service_latency_ms"] == 25.0
    assert feats["payment_service_latency_ms"] == 1100.0
    assert feats["last_step_latency_ms"] == 300.0
    assert feats["last_step_is_error"] == 0.0  # Last was RETRY, not FAILURE
    assert feats["mean_step_latency_ms"] > 0.0
    assert feats["max_step_latency_ms"] == 800.0
    assert feats["latency_ratio_vs_nominal"] > 1.0


def test_feature_extractor_guarantees_temporal_safety():
    """Verify that events occurring after as_of_timestamp are strictly rejected (zero leakage)."""
    extractor = TraceFeatureExtractor()
    base_time = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)

    events = [
        _create_sample_span(
            "exec_1", "auth-service", "auth", 20.0, offset_seconds=0.0, base_time=base_time
        ),
        _create_sample_span(
            "exec_1", "customer-service", "profile", 40.0, offset_seconds=0.05, base_time=base_time
        ),
        # Future event (t = +10.0s) contains a catastrophic failure
        _create_sample_span(
            "exec_1",
            "payment-service",
            "fail",
            2000.0,
            status=EventStatus.FAILURE,
            offset_seconds=10.0,
            base_time=base_time,
        ),
    ]

    # Query as of t = +0.1s
    as_of = base_time + timedelta(seconds=0.1)
    feats = extractor.extract_features_from_events(events, as_of_timestamp=as_of)

    assert feats["step_count"] == 2.0
    assert feats["cumulative_errors"] == 0.0
    assert feats["payment_service_latency_ms"] == 0.0
    assert feats["max_step_latency_ms"] == 40.0


def test_feature_extractor_as_of_step_slice():
    """Verify that as_of_step properly slices the prefix."""
    extractor = TraceFeatureExtractor()
    events = [
        _create_sample_span("exec_1", "auth-service", "auth", 20.0, offset_seconds=0.0),
        _create_sample_span("exec_1", "customer-service", "profile", 40.0, offset_seconds=0.05),
        _create_sample_span("exec_1", "inventory-service", "reserve", 50.0, offset_seconds=0.10),
    ]

    feats = extractor.extract_features_from_events(events, as_of_step=2)
    assert feats["step_count"] == 2.0
    assert feats["inventory_service_latency_ms"] == 0.0
    assert feats["customer_service_latency_ms"] == 40.0
