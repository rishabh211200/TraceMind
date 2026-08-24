"""Incident pattern matcher for classifying causal failure signatures into canonical incident types."""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from packages.domain.events import EventStatus, EventType, TraceEvent


class IncidentCategory(StrEnum):
    """Categorical classification of root-cause failure mechanisms."""

    DATABASE_IOPS_SATURATION = "DATABASE_IOPS_SATURATION"
    SERVICE_CRASH = "SERVICE_CRASH"
    CASCADING_RETRY_STORM = "CASCADING_RETRY_STORM"
    NETWORK_TRANSIT_DELAY = "NETWORK_TRANSIT_DELAY"
    FLASH_TRAFFIC_OVERLOAD = "FLASH_TRAFFIC_OVERLOAD"
    DEPENDENCY_TIMEOUT = "DEPENDENCY_TIMEOUT"
    SYSTEMIC_LATENCY_DEGRADATION = "SYSTEMIC_LATENCY_DEGRADATION"


class IncidentPatternMatcher:
    """Matches empirical telemetry and anomaly patterns to standard fault categories."""

    def _extract_culprit_metrics(
        self,
        culprit_service: str,
        events: Sequence[TraceEvent | dict[str, Any]],
        anomalies: Sequence[dict[str, Any]] | None = None,
    ) -> tuple[float, int, bool, bool, set[str], list[Any]]:
        """Extract summary metrics for culprit service."""
        culprit_events = [
            e
            for e in events
            if (e.get("service") if isinstance(e, dict) else e.service) == culprit_service
            or culprit_service in str(e.get("service") if isinstance(e, dict) else e.service)
        ]

        max_latency = 0.0
        retry_count = 0
        has_failure = False
        has_db_query = False

        for e in culprit_events:
            lat = float(e.get("latency_ms", 0.0) if isinstance(e, dict) else e.latency_ms)
            status = e.get("status", "SUCCESS") if isinstance(e, dict) else e.status
            event_type = e.get("event_type", "") if isinstance(e, dict) else e.event_type

            if lat > max_latency:
                max_latency = lat
            if status in (EventStatus.RETRY, "RETRY") or event_type in (
                EventType.RETRY_STARTED,
                "RETRY_STARTED",
            ):
                retry_count += 1
            if status in (EventStatus.FAILURE, "FAILURE", EventStatus.TIMEOUT, "TIMEOUT"):
                has_failure = True
            if "db" in culprit_service or event_type in (
                EventType.DATABASE_QUERY,
                "DATABASE_QUERY",
            ):
                has_db_query = True

        culprit_anom_types = set()
        if anomalies:
            for anom in anomalies:
                if culprit_service in anom.get("affected_services", []):
                    culprit_anom_types.add(anom.get("anomaly_type"))

        return (
            max_latency,
            retry_count,
            has_failure,
            has_db_query,
            culprit_anom_types,
            culprit_events,
        )

    def classify(
        self,
        culprit_service: str,
        causal_path: list[str],
        events: Sequence[TraceEvent | dict[str, Any]],
        anomalies: Sequence[dict[str, Any]] | None = None,
    ) -> tuple[IncidentCategory, str]:
        """Classify root cause category and generate technical rationale summary."""
        (
            max_latency,
            retry_count,
            has_failure,
            has_db_query,
            culprit_anom_types,
            culprit_events,
        ) = self._extract_culprit_metrics(culprit_service, events, anomalies)

        # Pattern Rule 1: Database IOPS Saturation
        if "db" in culprit_service or has_db_query or "database" in culprit_service:
            return (
                IncidentCategory.DATABASE_IOPS_SATURATION,
                f"Database query saturation on '{culprit_service}': measured {max_latency:.1f}ms latency causing upstream caller stalls",
            )

        # Pattern Rule 2: Cascading Retry Storm
        if retry_count >= 3 or "RETRY_STORM" in culprit_anom_types:
            return (
                IncidentCategory.CASCADING_RETRY_STORM,
                f"Client retry burst on '{culprit_service}' ({retry_count} retries) exhausting thread pool capacity and propagating downstream",
            )

        # Pattern Rule 3: Hard Service Crash
        if has_failure or "SERVICE_FAILED" in str(culprit_events):
            return (
                IncidentCategory.SERVICE_CRASH,
                f"Fatal service execution failure on '{culprit_service}' with HTTP 500 error, short-circuiting downstream workflow dependencies",
            )

        # Pattern Rule 4: Dependency Timeout
        if max_latency >= 1500.0 or "DEPENDENCY_TIMEOUT" in culprit_anom_types:
            return (
                IncidentCategory.DEPENDENCY_TIMEOUT,
                f"Downstream dependency timeout on '{culprit_service}': latency of {max_latency:.1f}ms breached timeout budget",
            )

        # Pattern Rule 5: Network Transit Delay
        if (
            "network" in culprit_service
            or "transit" in culprit_service
            or (max_latency >= 200.0 and len(culprit_events) == 1)
        ):
            return (
                IncidentCategory.NETWORK_TRANSIT_DELAY,
                f"High network transit packet delay (+{max_latency:.1f}ms) between {causal_path[0] if causal_path else culprit_service} and peer dependencies",
            )

        # Pattern Rule 6: Flash Traffic Overload
        if "gateway" in culprit_service or len(causal_path) >= 4:
            return (
                IncidentCategory.FLASH_TRAFFIC_OVERLOAD,
                f"Flash arrival traffic surge arriving at '{culprit_service}', propagating concurrent queueing delays across workflow",
            )

        # Default fallback
        return (
            IncidentCategory.SYSTEMIC_LATENCY_DEGRADATION,
            f"Severe latency degradation on '{culprit_service}' measured at {max_latency:.1f}ms",
        )
