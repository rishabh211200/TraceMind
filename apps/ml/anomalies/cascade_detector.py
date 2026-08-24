"""Error cascade and retry storm behavioral anomaly detector."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.domain.intelligence import Anomaly, AnomalyType


class ErrorCascadeAnomalyDetector:
    """Detects multi-service error propagation cascades and client retry storms."""

    def __init__(
        self,
        min_retry_count: int = 3,
        min_cascade_services: int = 2,
        cascade_window_ms: float = 1200.0,
    ) -> None:
        self.min_retry_count = min_retry_count
        self.min_cascade_services = min_cascade_services
        self.cascade_window_ms = cascade_window_ms

    def _normalize_events(
        self, events: Sequence[TraceEvent | dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize event objects/dicts into flat sorted dictionary records."""
        normalized = []
        for e in events:
            if isinstance(e, dict):
                t = e.get("timestamp")
                if isinstance(t, str):
                    t = datetime.fromisoformat(t.replace("Z", "+00:00"))
                normalized.append(
                    {
                        "service": e.get("service", ""),
                        "operation": e.get("operation", ""),
                        "status": e.get("status", "SUCCESS"),
                        "event_type": e.get("event_type", ""),
                        "latency_ms": float(e.get("latency_ms", 0.0)),
                        "timestamp": t,
                    }
                )
            else:
                normalized.append(
                    {
                        "service": e.service,
                        "operation": e.operation,
                        "status": e.status,
                        "event_type": e.event_type,
                        "latency_ms": float(e.latency_ms),
                        "timestamp": e.timestamp,
                    }
                )
        return sorted(normalized, key=lambda x: x["timestamp"] or datetime.min)

    def _detect_retry_storms(
        self, sorted_events: list[dict[str, Any]], execution_id: str
    ) -> list[Anomaly]:
        """Detect burst retry attempts exceeding configured threshold."""
        service_retries: dict[str, list[float]] = {}
        for e in sorted_events:
            is_retry = e["event_type"] in (
                EventType.RETRY_STARTED,
                EventType.RETRY_COMPLETED,
                "RETRY_STARTED",
                "RETRY_COMPLETED",
            ) or e["status"] in (EventStatus.RETRY, "RETRY")
            if is_retry:
                service_retries.setdefault(e["service"], []).append(e["latency_ms"])

        anomalies = []
        for svc, ret_lats in service_retries.items():
            if len(ret_lats) >= self.min_retry_count:
                retry_count = len(ret_lats)
                total_retry_dur = sum(ret_lats)
                score = min(1.0, 0.50 + 0.12 * retry_count)
                anomalies.append(
                    Anomaly(
                        execution_id=execution_id,
                        anomaly_type=AnomalyType.RETRY_STORM,
                        score=round(score, 3),
                        affected_services=[svc],
                        explanation=(
                            f"Retry storm burst on '{svc}': {retry_count} retries executed, "
                            f"accumulating {total_retry_dur:.1f}ms of retry overhead"
                        ),
                        evidence={
                            "service": svc,
                            "retry_count": retry_count,
                            "total_retry_latency_ms": round(total_retry_dur, 2),
                        },
                    )
                )
        return anomalies

    def _detect_cascading_failures(
        self, sorted_events: list[dict[str, Any]], execution_id: str
    ) -> list[Anomaly]:
        """Detect multi-service error cascades propagated downstream."""
        failure_events = [
            e
            for e in sorted_events
            if e["status"] in (EventStatus.FAILURE, "FAILURE")
            or e["event_type"] in (EventType.SERVICE_FAILED, "SERVICE_FAILED")
        ]
        if len(failure_events) < self.min_cascade_services:
            return []

        distinct_failing_services: list[str] = []
        for fe in failure_events:
            if fe["service"] not in distinct_failing_services:
                distinct_failing_services.append(fe["service"])

        if len(distinct_failing_services) < self.min_cascade_services:
            return []

        t_first = failure_events[0]["timestamp"]
        t_last = failure_events[-1]["timestamp"]
        duration_ms = (t_last - t_first).total_seconds() * 1000.0 if t_first and t_last else 0.0
        score = min(1.0, 0.60 + 0.15 * len(distinct_failing_services))
        explanation = (
            f"Cascading failure propagated across {len(distinct_failing_services)} services: "
            + " -> ".join(distinct_failing_services)
        )
        return [
            Anomaly(
                execution_id=execution_id,
                anomaly_type=AnomalyType.ERROR_CASCADE,
                score=round(score, 3),
                affected_services=distinct_failing_services,
                explanation=explanation,
                evidence={
                    "cascade_depth": len(distinct_failing_services),
                    "propagation_order": distinct_failing_services,
                    "total_failures": len(failure_events),
                    "cascade_duration_ms": round(duration_ms, 2),
                },
            )
        ]

    def detect(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        execution_id: str = "unknown",
        workflow_definition_id: str = "default_workflow",
    ) -> list[Anomaly]:
        """Analyze trace spans for retry storms and error cascades."""
        if not events:
            return []

        sorted_events = self._normalize_events(events)
        anomalies: list[Anomaly] = []
        anomalies.extend(self._detect_retry_storms(sorted_events, execution_id))
        anomalies.extend(self._detect_cascading_failures(sorted_events, execution_id))
        return anomalies
