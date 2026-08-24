"""Deterministic graph-based root-cause reasoning and multi-hypothesis ranking engine."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import numpy as np

from apps.ml.root_cause.causal_graph import (
    CausalGraph,
    CausalGraphBuilder,
    CausalGraphTraverser,
    CausalNode,
)
from apps.ml.root_cause.pattern_matcher import IncidentCategory, IncidentPatternMatcher
from packages.common.logging import get_logger
from packages.domain.events import EventStatus, TraceEvent

logger = get_logger("tracemind.ml.root_cause")

SERVICE_BASELINES = {
    "api-gateway": 10.0,
    "auth-service": 25.0,
    "customer-service": 30.0,
    "customer-db": 15.0,
    "inventory-service": 40.0,
    "inventory-db": 20.0,
    "pricing-service": 35.0,
    "payment-service": 50.0,
    "payment-gateway": 65.0,
    "order-service": 45.0,
    "notification-service": 20.0,
}


@dataclass
class HypothesisCandidate:
    """A ranked candidate culprit hypothesis with confidence and supporting evidence."""

    id: str
    execution_id: str
    culprit_service: str
    incident_category: str
    confidence: float
    causal_path: list[str]
    supporting_evidence: list[str]
    score_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class RootCauseReport:
    """Comprehensive diagnosis report containing primary root cause and alternative hypotheses."""

    id: str
    execution_id: str
    workflow_definition_id: str
    culprit_service: str
    incident_category: str
    confidence: float
    causal_path: list[str]
    supporting_evidence: list[str]
    primary_hypothesis: HypothesisCandidate
    alternative_hypotheses: list[HypothesisCandidate]
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RootCauseEngine:
    """Engine executing deterministic graph reasoning to identify failure culprits and propagation paths."""

    def __init__(
        self,
        weight_time: float = 0.35,
        weight_depth: float = 0.25,
        weight_severity: float = 0.20,
        weight_shap: float = 0.20,
    ) -> None:
        self.w_time = weight_time
        self.w_depth = weight_depth
        self.w_severity = weight_severity
        self.w_shap = weight_shap
        self.graph_builder = CausalGraphBuilder()
        self.traverser = CausalGraphTraverser()
        self.pattern_matcher = IncidentPatternMatcher()

    def _is_internal_degraded(self, graph: CausalGraph, candidate_services: list[str]) -> bool:
        """Check if any downstream internal microservice had degradation or failure."""
        for svc in candidate_services:
            if svc == "api-gateway":
                continue
            node_ids = graph.service_nodes.get(svc, [])
            svc_nodes = [graph.nodes[nid] for nid in node_ids if nid in graph.nodes]
            if not svc_nodes:
                continue
            max_lat = max([n.latency_ms for n in svc_nodes], default=0.0)
            baseline = SERVICE_BASELINES.get(svc, 35.0)
            has_fail = any(n.is_failure for n in svc_nodes)
            retry_count = sum(
                1
                for n in svc_nodes
                if n.status in ("RETRY", EventStatus.RETRY) or "retry" in n.operation.lower()
            )
            if has_fail or retry_count > 0 or (max_lat / baseline) > 1.4:
                return True
        return False

    def _compute_culprit_score(
        self,
        svc: str,
        has_fail: bool,
        retry_count: int,
        phi_latency: float,
        max_anom_score: float,
        phi_time: float,
        phi_shap: float,
        is_gateway: bool,
        internal_degraded: bool,
    ) -> float:
        """Compute quantitative culprit confidence score."""
        if has_fail:
            score = 0.95 + (0.04 * phi_latency) + (0.01 * phi_time)
        elif retry_count >= 2:
            score = 0.92 + (0.06 * phi_latency) + (0.02 * phi_time)
        elif phi_latency >= 0.40:
            score = 0.75 + (0.20 * phi_latency) + (0.05 * phi_time)
            if "db" in svc or "gateway" in svc:
                score += 0.05
        elif max_anom_score >= 0.50:
            score = 0.70 + (0.20 * max_anom_score) + (0.10 * phi_time)
        else:
            score = 0.50 * phi_latency + 0.30 * max_anom_score + 0.10 * phi_shap + 0.10 * phi_time

        if is_gateway and internal_degraded:
            score = min(0.30, score)

        return float(min(1.0, max(0.35, score)))

    def _build_evidence(
        self,
        svc: str,
        rationale: str,
        max_lat: float,
        has_fail: bool,
        svc_anoms: list[dict[str, Any]],
        max_anom_score: float,
        shap_total: float,
        primary_path: list[str],
        svc_nodes: list[CausalNode],
    ) -> list[str]:
        """Compile diagnostic evidence bullet points."""
        evidence: list[str] = [rationale]
        if max_lat > 0.0:
            evidence.append(
                f"Measured peak latency of {max_lat:.1f}ms on operation '{svc_nodes[0].operation}'"
            )
        if has_fail:
            evidence.append(
                f"Service '{svc}' returned non-retryable failure status during execution"
            )
        if svc_anoms:
            evidence.append(
                f"Associated with {len(svc_anoms)} anomaly detections (peak score: {max_anom_score:.2f})"
            )
        if shap_total > 0.05:
            evidence.append(
                f"TreeSHAP failure risk attribution score of +{shap_total:.3f} aligned with '{svc}'"
            )
        if primary_path and svc in primary_path:
            evidence.append(
                f"Positioned at step {primary_path.index(svc) + 1} of causal propagation chain: {' -> '.join(primary_path)}"
            )
        return evidence

    def _evaluate_candidate(
        self,
        svc: str,
        graph: CausalGraph,
        t_min: datetime,
        total_time_span_ms: float,
        internal_degraded: bool,
        primary_path: list[str],
        events: Sequence[TraceEvent | dict[str, Any]],
        anomalies: Sequence[dict[str, Any]] | None,
        execution_id: str,
    ) -> HypothesisCandidate | None:
        """Score candidate culprit service and compile evidence."""
        node_ids = graph.service_nodes.get(svc, [])
        svc_nodes = [graph.nodes[nid] for nid in node_ids if nid in graph.nodes]
        if not svc_nodes:
            return None

        is_gateway = svc == "api-gateway"
        has_fail = any(
            n.is_failure for n in svc_nodes if not (is_gateway and n.operation == "end_workflow")
        )
        retry_count = sum(
            1
            for n in svc_nodes
            if n.status in ("RETRY", EventStatus.RETRY) or "retry" in n.operation.lower()
        )

        internal_spans = [
            n for n in svc_nodes if not (is_gateway and n.operation == "end_workflow")
        ]
        max_lat = max([n.latency_ms for n in internal_spans], default=0.0)
        baseline = SERVICE_BASELINES.get(svc, 35.0)
        lat_multiplier = max(1.0, max_lat / baseline)
        phi_latency = min(1.0, (lat_multiplier - 1.0) / 2.0) if lat_multiplier > 1.25 else 0.0

        first_svc_time = min(n.timestamp for n in svc_nodes)
        delta_start_ms = (first_svc_time - t_min).total_seconds() * 1000.0
        phi_time = float(np.exp(-0.6 * (delta_start_ms / total_time_span_ms)))

        svc_anoms = []
        for n in svc_nodes:
            svc_anoms.extend(n.anomalies)
        max_anom_score = max([float(a.get("score", 0.0)) for a in svc_anoms], default=0.0)

        shap_total = sum(n.shap_attribution for n in svc_nodes)
        phi_shap = min(1.0, shap_total * 2.0) if shap_total > 0 else 0.10

        confidence = self._compute_culprit_score(
            svc=svc,
            has_fail=has_fail,
            retry_count=retry_count,
            phi_latency=phi_latency,
            max_anom_score=max_anom_score,
            phi_time=phi_time,
            phi_shap=phi_shap,
            is_gateway=is_gateway,
            internal_degraded=internal_degraded,
        )

        category, rationale = self.pattern_matcher.classify(
            culprit_service=svc,
            causal_path=primary_path,
            events=events,
            anomalies=anomalies,
        )

        evidence = self._build_evidence(
            svc=svc,
            rationale=rationale,
            max_lat=max_lat,
            has_fail=has_fail,
            svc_anoms=svc_anoms,
            max_anom_score=max_anom_score,
            shap_total=shap_total,
            primary_path=primary_path,
            svc_nodes=svc_nodes,
        )

        return HypothesisCandidate(
            id=f"hyp_{uuid4().hex[:8]}",
            execution_id=execution_id,
            culprit_service=svc,
            incident_category=category.value,
            confidence=round(confidence, 3),
            causal_path=primary_path,
            supporting_evidence=evidence,
            score_breakdown={
                "temporal_score": round(phi_time, 3),
                "latency_score": round(phi_latency, 3),
                "severity_score": round(max_anom_score, 3),
                "shap_score": round(phi_shap, 3),
            },
        )

    def diagnose_execution(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        anomalies: Sequence[dict[str, Any]] | None = None,
        shap_contributions: Sequence[dict[str, Any]] | None = None,
        execution_id: str = "unknown",
        workflow_definition_id: str = "order_fulfillment",
    ) -> RootCauseReport:
        """Analyze execution trace and anomalies to diagnose primary root cause."""
        report_id = f"rc_{uuid4().hex[:10]}"

        if not events:
            empty_hyp = HypothesisCandidate(
                id=f"hyp_{uuid4().hex[:8]}",
                execution_id=execution_id,
                culprit_service="unknown",
                incident_category=IncidentCategory.SYSTEMIC_LATENCY_DEGRADATION.value,
                confidence=0.50,
                causal_path=[],
                supporting_evidence=["No trace events provided for diagnosis"],
            )
            return RootCauseReport(
                id=report_id,
                execution_id=execution_id,
                workflow_definition_id=workflow_definition_id,
                culprit_service="unknown",
                incident_category=IncidentCategory.SYSTEMIC_LATENCY_DEGRADATION.value,
                confidence=0.50,
                causal_path=[],
                supporting_evidence=["No trace events provided"],
                primary_hypothesis=empty_hyp,
                alternative_hypotheses=[],
            )

        graph = self.graph_builder.build_graph(
            events=events,
            anomalies=anomalies,
            shap_contributions=shap_contributions,
        )

        symptom_nodes = self.traverser.find_symptom_nodes(graph)
        causal_paths = self.traverser.backward_traverse(graph, symptom_nodes)
        primary_path = causal_paths[0] if causal_paths else list(graph.service_nodes.keys())

        candidate_services = list(graph.service_nodes.keys())
        if not candidate_services:
            candidate_services = ["system"]

        all_timestamps = [n.timestamp for n in graph.nodes.values()]
        t_min = min(all_timestamps) if all_timestamps else datetime.now(UTC)
        t_max = max(all_timestamps) if all_timestamps else t_min
        total_time_span_ms = max(1.0, (t_max - t_min).total_seconds() * 1000.0)

        internal_degraded = self._is_internal_degraded(graph, candidate_services)

        candidates: list[HypothesisCandidate] = []
        for svc in candidate_services:
            cand = self._evaluate_candidate(
                svc=svc,
                graph=graph,
                t_min=t_min,
                total_time_span_ms=total_time_span_ms,
                internal_degraded=internal_degraded,
                primary_path=primary_path,
                events=events,
                anomalies=anomalies,
                execution_id=execution_id,
            )
            if cand:
                candidates.append(cand)

        if not candidates:
            candidates.append(
                HypothesisCandidate(
                    id=f"hyp_{uuid4().hex[:8]}",
                    execution_id=execution_id,
                    culprit_service="system",
                    incident_category=IncidentCategory.SYSTEMIC_LATENCY_DEGRADATION.value,
                    confidence=0.50,
                    causal_path=primary_path,
                    supporting_evidence=["Generic systemic degradation"],
                )
            )

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        primary = candidates[0]
        alternatives = candidates[1:4]

        logger.info(
            "root_cause_diagnosed",
            execution_id=execution_id,
            culprit=primary.culprit_service,
            category=primary.incident_category,
            confidence=primary.confidence,
        )

        return RootCauseReport(
            id=report_id,
            execution_id=execution_id,
            workflow_definition_id=workflow_definition_id,
            culprit_service=primary.culprit_service,
            incident_category=primary.incident_category,
            confidence=primary.confidence,
            causal_path=primary.causal_path,
            supporting_evidence=primary.supporting_evidence,
            primary_hypothesis=primary,
            alternative_hypotheses=alternatives,
        )
