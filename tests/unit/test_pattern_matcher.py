"""Unit tests for Incident Pattern Matcher."""

from datetime import UTC, datetime

from apps.ml.root_cause.pattern_matcher import IncidentCategory, IncidentPatternMatcher
from packages.domain.events import EventStatus, EventType, TraceEvent


def test_pattern_matcher_categories():
    matcher = IncidentPatternMatcher()
    now = datetime.now(UTC)

    # 1. Database IOPS Saturation
    db_events = [
        TraceEvent(
            event_id="e1",
            execution_id="ex",
            workflow_id="wf",
            service="inventory-db",
            operation="query",
            event_type=EventType.DATABASE_QUERY,
            status=EventStatus.SUCCESS,
            latency_ms=650.0,
            timestamp=now,
        )
    ]
    cat1, _ = matcher.classify("inventory-db", ["inventory-db"], db_events)
    assert cat1 == IncidentCategory.DATABASE_IOPS_SATURATION

    # 2. Cascading Retry Storm
    retry_events = [
        TraceEvent(
            event_id=f"r{i}",
            execution_id="ex",
            workflow_id="wf",
            service="payment-service",
            operation="charge",
            event_type=EventType.RETRY_STARTED,
            status=EventStatus.RETRY,
            latency_ms=50.0,
            timestamp=now,
        )
        for i in range(3)
    ]
    cat2, _ = matcher.classify("payment-service", ["payment-service"], retry_events)
    assert cat2 == IncidentCategory.CASCADING_RETRY_STORM

    # 3. Hard Service Crash
    crash_events = [
        TraceEvent(
            event_id="c1",
            execution_id="ex",
            workflow_id="wf",
            service="auth-service",
            operation="authenticate",
            event_type=EventType.SERVICE_COMPLETED,
            status=EventStatus.FAILURE,
            latency_ms=20.0,
            timestamp=now,
        )
    ]
    cat3, _ = matcher.classify("auth-service", ["auth-service"], crash_events)
    assert cat3 == IncidentCategory.SERVICE_CRASH
