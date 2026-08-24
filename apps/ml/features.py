"""In-flight temporal feature extraction pipeline for workflow executions.

Extracts tabular feature vectors from partial trace span prefixes while guaranteeing
strict temporal safety (zero leakage of future events t > t_k).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from packages.domain.events import EventStatus, EventType, TraceEvent

# Canonical ordered feature names for model input
FEATURE_NAMES: list[str] = [
    "step_count",
    "elapsed_time_ms",
    "cumulative_retries",
    "cumulative_errors",
    "mean_step_latency_ms",
    "max_step_latency_ms",
    "last_step_latency_ms",
    "last_step_is_error",
    "has_cache_miss",
    "has_database_query",
    "auth_service_latency_ms",
    "customer_service_latency_ms",
    "inventory_service_latency_ms",
    "pricing_service_latency_ms",
    "payment_service_latency_ms",
    "latency_ratio_vs_nominal",
]

# Baseline nominal expected latencies (ms) per service for ratio calculations
NOMINAL_SERVICE_LATENCIES: dict[str, float] = {
    "api-gateway": 1.0,
    "auth-service": 22.0,
    "customer-service": 45.0,
    "customer-cache": 3.0,
    "customer-db": 35.0,
    "inventory-service": 60.0,
    "inventory-db": 50.0,
    "pricing-service": 15.0,
    "payment-service": 250.0,
    "order-service": 40.0,
    "notification-service": 30.0,
}


class TraceFeatureExtractor:
    """Extracts in-flight temporal feature vectors from workflow trace spans."""

    def __init__(
        self,
        nominal_latencies: dict[str, float] | None = None,
        feature_names: list[str] | None = None,
    ) -> None:
        self.nominal_latencies = nominal_latencies or NOMINAL_SERVICE_LATENCIES
        self.feature_names = feature_names or FEATURE_NAMES

    def extract_features_from_events(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        as_of_timestamp: datetime | None = None,
        as_of_step: int | None = None,
    ) -> dict[str, float]:
        """Extract a tabular feature dictionary from a list of trace events.

        Parameters
        ----------
        events : Sequence[TraceEvent | dict]
            Chronological list of trace events or spans.
        as_of_timestamp : datetime | None
            If provided, only events with timestamp <= as_of_timestamp are included.
        as_of_step : int | None
            If provided, only the first `as_of_step` events are included.

        Returns
        -------
        dict[str, float]
            Ordered dictionary of extracted feature values.
        """
        # Convert dicts to TraceEvent if necessary
        normalized_events: list[TraceEvent] = []
        for e in events:
            if isinstance(e, dict):
                normalized_events.append(TraceEvent.model_validate(e))
            else:
                normalized_events.append(e)

        # Sort chronologically by timestamp
        sorted_events = sorted(normalized_events, key=lambda x: x.timestamp)

        # Apply strict temporal filter: reject any future events where t > as_of_timestamp
        if as_of_timestamp is not None:
            sorted_events = [e for e in sorted_events if e.timestamp <= as_of_timestamp]

        # Apply prefix slice if as_of_step is specified
        if as_of_step is not None and as_of_step > 0:
            sorted_events = sorted_events[:as_of_step]

        if not sorted_events:
            return dict.fromkeys(self.feature_names, 0.0)

        # Compute core temporal metrics
        step_count = float(len(sorted_events))
        latencies = [e.latency_ms for e in sorted_events if e.latency_ms >= 0.0]
        mean_step_latency = float(np.mean(latencies)) if latencies else 0.0
        max_step_latency = float(np.max(latencies)) if latencies else 0.0
        last_event = sorted_events[-1]
        last_step_latency = float(last_event.latency_ms)

        # Retries and errors
        retries = sum(
            1
            for e in sorted_events
            if e.event_type in (EventType.RETRY_STARTED, EventType.RETRY_COMPLETED)
            or e.status == EventStatus.RETRY
        )
        errors = sum(
            1
            for e in sorted_events
            if e.status == EventStatus.FAILURE or e.event_type == EventType.SERVICE_FAILED
        )
        last_is_error = 1.0 if last_event.status == EventStatus.FAILURE else 0.0

        # Operation flags
        has_cache_miss = (
            1.0 if any(e.event_type == EventType.CACHE_MISS for e in sorted_events) else 0.0
        )
        has_db_query = (
            1.0 if any(e.event_type == EventType.DATABASE_QUERY for e in sorted_events) else 0.0
        )

        # Elapsed time from start of first event to completion of last event
        first_time = sorted_events[0].timestamp
        last_time = sorted_events[-1].timestamp
        time_delta_ms = (last_time - first_time).total_seconds() * 1000.0
        # If timestamps are identical or close, sum latencies as lower bound
        elapsed_time_ms = max(time_delta_ms + last_step_latency, float(np.sum(latencies)))

        # Per-service cumulative latencies
        service_latencies: dict[str, float] = {}
        for e in sorted_events:
            service_latencies[e.service] = service_latencies.get(e.service, 0.0) + e.latency_ms

        auth_latency = service_latencies.get("auth-service", 0.0)
        customer_latency = service_latencies.get("customer-service", 0.0)
        inventory_latency = service_latencies.get("inventory-service", 0.0)
        pricing_latency = service_latencies.get("pricing-service", 0.0)
        payment_latency = service_latencies.get("payment-service", 0.0)

        # Latency ratio vs nominal expected baseline for the executed services
        expected_nominal_total = sum(
            self.nominal_latencies.get(e.service, 20.0) for e in sorted_events
        )
        actual_total_latency = sum(latencies)
        latency_ratio = (
            actual_total_latency / expected_nominal_total if expected_nominal_total > 0.0 else 1.0
        )

        raw_features: dict[str, float] = {
            "step_count": step_count,
            "elapsed_time_ms": elapsed_time_ms,
            "cumulative_retries": float(retries),
            "cumulative_errors": float(errors),
            "mean_step_latency_ms": mean_step_latency,
            "max_step_latency_ms": max_step_latency,
            "last_step_latency_ms": last_step_latency,
            "last_step_is_error": last_is_error,
            "has_cache_miss": has_cache_miss,
            "has_database_query": has_db_query,
            "auth_service_latency_ms": auth_latency,
            "customer_service_latency_ms": customer_latency,
            "inventory_service_latency_ms": inventory_latency,
            "pricing_service_latency_ms": pricing_latency,
            "payment_service_latency_ms": payment_latency,
            "latency_ratio_vs_nominal": latency_ratio,
        }

        # Return ordered dict matching FEATURE_NAMES
        return {k: raw_features.get(k, 0.0) for k in self.feature_names}

    def extract_feature_vector(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        as_of_timestamp: datetime | None = None,
        as_of_step: int | None = None,
    ) -> np.ndarray:
        """Extract a 1D NumPy array feature vector matching FEATURE_NAMES ordering."""
        feat_dict = self.extract_features_from_events(
            events=events,
            as_of_timestamp=as_of_timestamp,
            as_of_step=as_of_step,
        )
        return np.array([feat_dict[k] for k in self.feature_names], dtype=np.float32)

    def extract_prefix_dataset(
        self,
        execution_events_map: dict[str, list[TraceEvent]],
        execution_outcomes: dict[str, tuple[bool, float]],
        min_prefix_steps: int = 1,
        sample_checkpoints: bool = True,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """Generate a prefix dataset across multiple executions for offline training.

        Parameters
        ----------
        execution_events_map : dict[str, list[TraceEvent]]
            Map of execution_id -> full chronological list of trace events.
        execution_outcomes : dict[str, tuple[bool, float]]
            Map of execution_id -> (is_failed: bool, total_duration_ms: float).
        min_prefix_steps : int
            Minimum number of steps required to form a valid training sample.
        sample_checkpoints : bool
            If True, extracts representative progress points (33%, 66%, 100%) per execution.

        Returns
        -------
        tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]
            (X_df, y_failure_series, y_latency_series, execution_ids_series)
        """
        rows: list[dict[str, float]] = []
        y_failures: list[int] = []
        y_latencies: list[float] = []
        exec_ids: list[str] = []

        for exec_id, events in execution_events_map.items():
            if exec_id not in execution_outcomes:
                continue

            is_failed, total_duration = execution_outcomes[exec_id]
            total_steps = len(events)

            if total_steps < min_prefix_steps:
                continue

            if sample_checkpoints:
                checkpoints = {max(1, int(total_steps * p)) for p in (0.33, 0.66, 1.0)}
                steps_to_extract = sorted(checkpoints)
            else:
                steps_to_extract = list(range(min_prefix_steps, total_steps + 1))

            for step_idx in steps_to_extract:
                prefix_feats = self.extract_features_from_events(events=events, as_of_step=step_idx)
                rows.append(prefix_feats)
                y_failures.append(1 if is_failed else 0)
                y_latencies.append(float(total_duration))
                exec_ids.append(exec_id)

        df_X = pd.DataFrame(rows, columns=self.feature_names)
        s_y_fail = pd.Series(y_failures, name="is_failed")
        s_y_lat = pd.Series(y_latencies, name="total_duration_ms")
        s_groups = pd.Series(exec_ids, name="execution_id")

        return df_X, s_y_fail, s_y_lat, s_groups
