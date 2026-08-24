"""Composite anomaly detection evaluator synthesizing multi-model detectors."""

from collections.abc import Sequence
from typing import Any

from apps.ml.anomalies.cascade_detector import ErrorCascadeAnomalyDetector
from apps.ml.anomalies.isolation_forest import WorkflowIsolationForestDetector
from apps.ml.anomalies.latency_detector import ServiceLatencyAnomalyDetector
from apps.ml.anomalies.sequence_detector import TransitionPathAnomalyDetector
from packages.domain.events import TraceEvent
from packages.domain.intelligence import Anomaly, AnomalyType


class CompositeAnomalyDetector:
    """Multi-detector aggregator producing ranked, deduplicated anomaly reports with severity ratings."""

    def __init__(
        self,
        isolation_forest: WorkflowIsolationForestDetector | None = None,
        latency_detector: ServiceLatencyAnomalyDetector | None = None,
        sequence_detector: TransitionPathAnomalyDetector | None = None,
        cascade_detector: ErrorCascadeAnomalyDetector | None = None,
    ) -> None:
        self.isolation_forest = isolation_forest or WorkflowIsolationForestDetector()
        self.latency_detector = latency_detector or ServiceLatencyAnomalyDetector()
        self.sequence_detector = sequence_detector or TransitionPathAnomalyDetector()
        self.cascade_detector = cascade_detector or ErrorCascadeAnomalyDetector()

    def detect_anomalies(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        execution_id: str = "unknown",
        workflow_definition_id: str = "default_workflow",
        as_of_step: int | None = None,
    ) -> list[Anomaly]:
        """Run all detection models against trace telemetry and aggregate anomalies."""
        if not events:
            return []

        # Filter prefix if as_of_step is provided
        eval_events = (
            list(events)[:as_of_step] if as_of_step is not None and as_of_step > 0 else list(events)
        )
        detected_anomalies: list[Anomaly] = []

        # 1. Latency & Timeout Anomalies
        lat_anomalies = self.latency_detector.detect(
            events=eval_events,
            execution_id=execution_id,
            workflow_definition_id=workflow_definition_id,
        )
        detected_anomalies.extend(lat_anomalies)

        # 2. Sequence & Path Anomalies
        seq_anomalies = self.sequence_detector.detect(
            events=eval_events,
            execution_id=execution_id,
            workflow_definition_id=workflow_definition_id,
        )
        detected_anomalies.extend(seq_anomalies)

        # 3. Retry Storm & Cascade Anomalies
        casc_anomalies = self.cascade_detector.detect(
            events=eval_events,
            execution_id=execution_id,
            workflow_definition_id=workflow_definition_id,
        )
        detected_anomalies.extend(casc_anomalies)

        # 4. Multidimensional Isolation Forest Check
        if self.isolation_forest.is_fitted:
            if_score, is_outlier, features = self.isolation_forest.score_events(eval_events)
            if is_outlier and if_score >= 0.70 and not detected_anomalies:
                # Flag general metric outlier if no specific detector triggered
                detected_anomalies.append(
                    Anomaly(
                        execution_id=execution_id,
                        anomaly_type=AnomalyType.LATENCY_SPIKE,
                        score=round(if_score, 3),
                        affected_services=["system"],
                        explanation=f"Multidimensional statistical outlier (Isolation Forest score: {if_score:.2f})",
                        evidence={
                            "isolation_forest_score": round(if_score, 3),
                            "features": {k: round(v, 2) for k, v in features.items() if v > 0.0},
                        },
                    )
                )

        # Sort by severity score descending
        detected_anomalies.sort(key=lambda a: a.score, reverse=True)
        return detected_anomalies

    def get_severity_label(self, score: float) -> str:
        """Map numerical anomaly score to categorical severity rating."""
        if score >= 0.70:
            return "CRITICAL"
        elif score >= 0.40:
            return "WARNING"
        return "INFO"
