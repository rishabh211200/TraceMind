"""Dynamic statistical service latency outlier detection using robust IQR and Z-scores."""

from collections.abc import Sequence
from typing import Any

import numpy as np

from packages.domain.events import EventStatus, TraceEvent
from packages.domain.intelligence import Anomaly, AnomalyType


class ServiceLatencyAnomalyDetector:
    """Detects service latency spikes and dependency timeouts using robust statistical baselines."""

    def __init__(self, iqr_factor: float = 3.5, z_threshold: float = 3.5) -> None:
        self.iqr_factor = iqr_factor
        self.z_threshold = z_threshold
        self.service_stats: dict[str, dict[str, float]] = {}
        self.is_fitted = False

    def fit_from_events(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
    ) -> "ServiceLatencyAnomalyDetector":
        """Fit empirical latency distributions across microservices from trace telemetry."""
        service_latencies: dict[str, list[float]] = {}

        for e in events:
            if isinstance(e, dict):
                service = e.get("service", "unknown")
                lat = float(e.get("latency_ms", 0.0))
            else:
                service = e.service
                lat = float(e.latency_ms)

            if lat > 0.0:
                service_latencies.setdefault(service, []).append(lat)

        self.service_stats = {}
        for svc, lats in service_latencies.items():
            if len(lats) < 3:
                continue
            arr = np.array(lats, dtype=np.float64)
            q1 = float(np.percentile(arr, 25))
            q3 = float(np.percentile(arr, 75))
            iqr = max(2.0, q3 - q1)
            med = float(np.median(arr))
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            mad = float(np.median(np.abs(arr - med))) or (std * 0.6745) or 2.0

            self.service_stats[svc] = {
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "median": med,
                "mean": mean,
                "std": std,
                "mad": mad,
                "upper_threshold": max(med + 150.0, q3 + self.iqr_factor * iqr),
            }

        self.is_fitted = len(self.service_stats) > 0
        return self

    def detect(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        execution_id: str = "unknown",
        workflow_definition_id: str = "default_workflow",
    ) -> list[Anomaly]:
        """Detect latency spikes and timeouts in an execution trace."""
        anomalies: list[Anomaly] = []

        for e in events:
            if isinstance(e, dict):
                svc = e.get("service", "unknown")
                lat = float(e.get("latency_ms", 0.0))
                op = e.get("operation", "operation")
                status = e.get("status", "SUCCESS")
                event_id = e.get("event_id", "")
            else:
                svc = e.service
                lat = float(e.latency_ms)
                op = e.operation
                status = e.status
                event_id = e.event_id

            if lat <= 0.0:
                continue

            stats = self.service_stats.get(svc)
            if not stats:
                # Default heuristic if service not fitted
                if lat >= 800.0 or status in (EventStatus.TIMEOUT, "TIMEOUT"):
                    is_timeout = status in (EventStatus.TIMEOUT, "TIMEOUT") or lat >= 1500.0
                    anom_type = (
                        AnomalyType.DEPENDENCY_TIMEOUT if is_timeout else AnomalyType.LATENCY_SPIKE
                    )
                    anomalies.append(
                        Anomaly(
                            execution_id=execution_id,
                            anomaly_type=anom_type,
                            score=0.80,
                            affected_services=[svc],
                            explanation=f"Severe latency degradation on {svc}:{op} ({lat:.1f}ms)",
                            evidence={
                                "service": svc,
                                "operation": op,
                                "measured_latency_ms": lat,
                                "event_id": event_id,
                            },
                        )
                    )
                continue

            abs_delta = lat - stats["median"]
            # Guard against microsecond/sub-120ms normal jitter
            if abs_delta < 100.0 and lat < 300.0 and status not in (EventStatus.TIMEOUT, "TIMEOUT"):
                continue

            upper_bound = stats["upper_threshold"]
            iqr_mult = max(0.0, (lat - stats["q3"]) / stats["iqr"])
            z_score = max(0.0, (lat - stats["mean"]) / max(1.0, stats["std"]))

            if (
                (lat > upper_bound and z_score > self.z_threshold)
                or status in (EventStatus.TIMEOUT, "TIMEOUT")
                or lat >= 1200.0
            ):
                is_timeout = status in (EventStatus.TIMEOUT, "TIMEOUT") or lat >= 1500.0
                anom_type = (
                    AnomalyType.DEPENDENCY_TIMEOUT if is_timeout else AnomalyType.LATENCY_SPIKE
                )

                # Calibrate score [0.45 - 1.00]
                raw_score = max(iqr_mult / 5.0, z_score / 4.0)
                norm_score = float(min(1.0, 0.45 + 0.55 * (raw_score / max(1.0, raw_score + 1.0))))

                mult_vs_median = lat / max(1.0, stats["median"])
                explanation = (
                    f"Extreme latency spike on '{svc}' during {op}: measured {lat:.1f}ms "
                    f"({mult_vs_median:.1f}x nominal median of {stats['median']:.1f}ms, z={z_score:.2f})"
                )

                anomalies.append(
                    Anomaly(
                        execution_id=execution_id,
                        anomaly_type=anom_type,
                        score=round(norm_score, 3),
                        affected_services=[svc],
                        explanation=explanation,
                        evidence={
                            "service": svc,
                            "operation": op,
                            "measured_latency_ms": lat,
                            "median_latency_ms": stats["median"],
                            "iqr_ms": stats["iqr"],
                            "z_score": round(z_score, 2),
                            "iqr_multiplier": round(iqr_mult, 2),
                            "threshold_ms": round(upper_bound, 2),
                            "event_id": event_id,
                        },
                    )
                )

        return anomalies
