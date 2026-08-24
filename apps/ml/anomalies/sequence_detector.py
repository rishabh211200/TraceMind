"""Markov DAG causal edge and path transition sequence anomaly detector."""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from packages.domain.events import EventStatus, TraceEvent
from packages.domain.intelligence import Anomaly, AnomalyType


class TransitionPathAnomalyDetector:
    """Detects unusual DAG execution paths, illegal transitions, missing steps, and circular loops."""

    def __init__(self, min_transition_prob: float = 0.02) -> None:
        self.min_transition_prob = min_transition_prob
        self.transition_counts: dict[str, dict[str, int]] = {}
        self.transition_probs: dict[str, dict[str, float]] = {}
        self.expected_services: set[str] = set()
        self.is_fitted = False

    def fit(
        self,
        execution_events_map: Mapping[str, Sequence[TraceEvent | dict[str, Any]]],
    ) -> "TransitionPathAnomalyDetector":
        """Fit empirical transition probabilities between services across nominal executions."""
        self.transition_counts = {}
        all_services: set[str] = set()

        for _exec_id, events in execution_events_map.items():
            if not events:
                continue

            # Extract chronological service sequence
            services: list[str] = []
            for e in events:
                svc = e.get("service") if isinstance(e, dict) else e.service
                if svc and (not services or services[-1] != svc):
                    services.append(svc)
                if svc:
                    all_services.add(svc)

            # Record transitions
            for i in range(len(services) - 1):
                u, v = services[i], services[i + 1]
                self.transition_counts.setdefault(u, {})
                self.transition_counts[u][v] = self.transition_counts[u].get(v, 0) + 1

        self.expected_services = all_services

        # Compute conditional transition probabilities P(v | u)
        self.transition_probs = {}
        for u, targets in self.transition_counts.items():
            total = sum(targets.values())
            self.transition_probs[u] = {v: count / total for v, count in targets.items()}

        self.is_fitted = len(self.transition_probs) > 0
        return self

    def _extract_service_path(
        self, events: Sequence[TraceEvent | dict[str, Any]]
    ) -> tuple[list[str], list[str], bool]:
        """Extract ordered unique service path and failure short-circuit flag."""
        service_path: list[str] = []
        visited_services: list[str] = []
        is_short_circuited = False

        for e in events:
            if isinstance(e, dict):
                svc = e.get("service", "")
                status = e.get("status", "SUCCESS")
            else:
                svc = e.service
                status = e.status

            if svc:
                visited_services.append(svc)
                if not service_path or service_path[-1] != svc:
                    service_path.append(svc)
            if status in (EventStatus.FAILURE, "FAILURE"):
                is_short_circuited = True

        return service_path, visited_services, is_short_circuited

    def _evaluate_transitions(
        self, service_path: list[str]
    ) -> tuple[list[dict[str, Any]], list[float]]:
        """Compute transition probabilities and identify anomalous edge transitions."""
        anomalous_transitions = []
        log_probs = []
        for i in range(len(service_path) - 1):
            u, v = service_path[i], service_path[i + 1]
            probs_from_u = self.transition_probs.get(u, {})
            prob = probs_from_u.get(v, 0.0)
            if prob < self.min_transition_prob:
                anomalous_transitions.append(
                    {"from_service": u, "to_service": v, "empirical_prob": round(prob, 4)}
                )
                log_probs.append(float(np.log(max(prob, 1e-4))))
            else:
                log_probs.append(float(np.log(prob)))
        return anomalous_transitions, log_probs

    def _detect_cycles(self, service_path: list[str]) -> list[str]:
        """Detect non-consecutive cyclic re-entrancy in service path."""
        seen_indices: dict[str, int] = {}
        cycles = []
        for idx, svc in enumerate(service_path):
            if svc in seen_indices and idx - seen_indices[svc] > 1:
                cycles.append(f"{svc} (steps {seen_indices[svc]} -> {idx})")
            seen_indices[svc] = idx
        return cycles

    def detect(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        execution_id: str = "unknown",
        workflow_definition_id: str = "default_workflow",
    ) -> list[Anomaly]:
        """Evaluate execution trace transitions and detect DAG sequence anomalies."""
        if not events:
            return []

        service_path, visited_services, is_short_circuited = self._extract_service_path(events)
        if len(service_path) < 2:
            return []

        anomalous_transitions, log_probs = self._evaluate_transitions(service_path)
        cycles = self._detect_cycles(service_path)

        mean_nll = float(-np.mean(log_probs)) if log_probs else 0.0
        norm_score = float(1.0 - np.exp(-0.4 * mean_nll))

        if not (
            anomalous_transitions or cycles or (is_short_circuited and len(visited_services) < 4)
        ):
            return []

        impacted = list(
            {t["from_service"] for t in anomalous_transitions}
            | {t["to_service"] for t in anomalous_transitions}
        ) or [service_path[-1]]

        severity_score = max(0.50, min(1.0, norm_score + (0.2 if cycles else 0.0)))
        explanation_parts = []
        if anomalous_transitions:
            explanation_parts.append(
                f"Discovered {len(anomalous_transitions)} unusual transition edges: "
                + ", ".join(
                    f"{t['from_service']} -> {t['to_service']}" for t in anomalous_transitions[:3]
                )
            )
        if cycles:
            explanation_parts.append(f"Detected circular dependency loops: {', '.join(cycles)}")
        if is_short_circuited:
            explanation_parts.append(
                f"Workflow short-circuited prematurely after failure on {service_path[-1]}"
            )

        return [
            Anomaly(
                execution_id=execution_id,
                anomaly_type=AnomalyType.UNUSUAL_PATH,
                score=round(severity_score, 3),
                affected_services=impacted,
                explanation=" | ".join(explanation_parts),
                evidence={
                    "service_path": service_path,
                    "anomalous_transitions": anomalous_transitions,
                    "cycles": cycles,
                    "negative_log_likelihood": round(mean_nll, 3),
                    "is_short_circuited": is_short_circuited,
                },
            )
        ]
