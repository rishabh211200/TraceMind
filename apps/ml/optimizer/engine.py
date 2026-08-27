"""Core Workflow Optimizer engine executing multi-objective path routing and advisory diversion recommendations."""

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from apps.ml.optimizer.cost_model import ResourceCostModel
from apps.ml.optimizer.models import (
    ExpectedSavings,
    MultiObjectiveWeight,
    OptimizationRecommendation,
    ParetoPoint,
    PathMetrics,
)
from apps.ml.optimizer.pareto import ParetoFrontierCalculator
from apps.ml.optimizer.path_extractor import PathExtractor
from packages.common.logging import get_logger
from packages.domain.events import TraceEvent

logger = get_logger("tracemind.ml.optimizer")


class WorkflowOptimizer:
    """Engine calculating multi-objective Pareto optimal routing and advisory diversion recommendations."""

    def __init__(
        self,
        cost_model: ResourceCostModel | None = None,
        path_extractor: PathExtractor | None = None,
        pareto_calculator: ParetoFrontierCalculator | None = None,
    ) -> None:
        self.cost_model = cost_model or ResourceCostModel()
        self.path_extractor = path_extractor or PathExtractor(cost_model=self.cost_model)
        self.pareto_calculator = pareto_calculator or ParetoFrontierCalculator()

    def _apply_incident_penalty(
        self,
        paths: list[PathMetrics],
        culprit_service: str,
    ) -> list[PathMetrics]:
        """Adjust observed metrics for paths traversing an active degraded culprit component."""
        adjusted_paths: list[PathMetrics] = []
        for p in paths:
            traverses_culprit = any(
                culprit_service in step.service or culprit_service in step.operation
                for step in p.steps
            )
            if traverses_culprit:
                # Degrade latency and reliability for paths hitting the active culprit
                degraded_lat = p.observed_latency_ms * 3.5
                degraded_p95 = p.observed_p95_latency_ms * 4.0
                degraded_p99 = p.observed_p99_latency_ms * 4.5
                degraded_rel = max(0.20, p.observed_reliability - 0.50)
                degraded_retries = p.observed_retry_rate + 0.35

                cost_breakdown = self.cost_model.calculate_cost(
                    steps=p.steps,
                    retry_rate=degraded_retries,
                )

                adjusted_paths.append(
                    PathMetrics(
                        path_id=p.path_id,
                        steps=p.steps,
                        step_signatures=p.step_signatures,
                        observed_latency_ms=round(degraded_lat, 2),
                        observed_p95_latency_ms=round(degraded_p95, 2),
                        observed_p99_latency_ms=round(degraded_p99, 2),
                        observed_reliability=round(degraded_rel, 3),
                        observed_retry_rate=round(degraded_retries, 3),
                        observation_count=p.observation_count,
                        statistical_confidence=p.statistical_confidence,
                        cost_breakdown=cost_breakdown,
                        modeled_cost_units=cost_breakdown.total_modeled_cost,
                    )
                )
            else:
                adjusted_paths.append(p)
        return adjusted_paths

    def _compute_expected_savings(
        self,
        current: PathMetrics,
        recommended: PathMetrics,
        w: MultiObjectiveWeight,
        frontier_points: list[ParetoPoint],
    ) -> ExpectedSavings:
        """Calculate percentage and absolute delta improvements."""
        # Find utility scores
        curr_pt = next((pt for pt in frontier_points if pt.path_id == current.path_id), None)
        rec_pt = next((pt for pt in frontier_points if pt.path_id == recommended.path_id), None)

        curr_score = curr_pt.utility_score if curr_pt else 0.50
        rec_score = rec_pt.utility_score if rec_pt else 0.80

        lat_delta_ms = current.observed_latency_ms - recommended.observed_latency_ms
        lat_pct = (
            (lat_delta_ms / current.observed_latency_ms) * 100.0
            if current.observed_latency_ms > 0
            else 0.0
        )

        cost_delta = current.modeled_cost_units - recommended.modeled_cost_units
        cost_pct = (
            (cost_delta / current.modeled_cost_units) * 100.0
            if current.modeled_cost_units > 0
            else 0.0
        )

        rel_gain_pct = (recommended.observed_reliability - current.observed_reliability) * 100.0
        overall_gain_pct = (
            ((rec_score - curr_score) / curr_score) * 100.0 if curr_score > 0 else 0.0
        )

        return ExpectedSavings(
            latency_reduction_pct=round(lat_pct, 1),
            cost_reduction_pct=round(cost_pct, 1),
            reliability_gain_pct=round(rel_gain_pct, 1),
            overall_utility_improvement_pct=round(overall_gain_pct, 1),
            absolute_latency_delta_ms=round(lat_delta_ms, 2),
            absolute_cost_delta_units=round(cost_delta, 2),
        )

    def _generate_rationale(
        self,
        current: PathMetrics,
        recommended: PathMetrics,
        savings: ExpectedSavings,
        w: MultiObjectiveWeight,
        active_incident: str | None = None,
    ) -> str:
        """Generate structured engineering justification for the recommended routing path."""
        if active_incident:
            return (
                f"Advisory Incident Diversion: Active bottleneck detected on '{active_incident}'. "
                f"Recommended routing detour through path '{recommended.path_id}' avoids degraded dependency, "
                f"achieving +{savings.reliability_gain_pct:.1f}% higher reliability and "
                f"{savings.latency_reduction_pct:.1f}% lower latency ({abs(savings.absolute_latency_delta_ms):.1f}ms savings)."
            )

        reasons = []
        if savings.latency_reduction_pct > 5.0:
            reasons.append(
                f"{savings.latency_reduction_pct:.1f}% latency reduction ({savings.absolute_latency_delta_ms:.1f}ms faster)"
            )
        if savings.cost_reduction_pct > 5.0:
            reasons.append(
                f"{savings.cost_reduction_pct:.1f}% resource cost reduction ({savings.absolute_cost_delta_units:.1f} units saved)"
            )
        if savings.reliability_gain_pct > 1.0:
            reasons.append(f"+{savings.reliability_gain_pct:.1f}% reliability improvement")

        weights_str = f"(weights: {w.latency * 100:.0f}% lat, {w.cost * 100:.0f}% cost, {w.reliability * 100:.0f}% rel)"
        if reasons:
            return (
                f"Optimal multi-objective path '{recommended.path_id}' delivers "
                + ", ".join(reasons)
                + f" over baseline '{current.path_id}' {weights_str}."
            )
        return (
            f"Path '{recommended.path_id}' achieves the highest multi-objective utility {weights_str} "
            f"on the non-dominated Pareto frontier."
        )

    def _resolve_candidate_paths(
        self,
        events: Sequence[TraceEvent | dict[str, Any]] | None,
        candidate_paths: list[PathMetrics] | None,
    ) -> list[PathMetrics]:
        """Resolve candidate execution paths from parameters or canonical repository templates."""
        if candidate_paths:
            return list(candidate_paths)
        if events:
            return self.path_extractor.extract_paths_from_events(events)
        return self.path_extractor.get_canonical_order_paths()

    def _filter_sla_constraints(
        self,
        paths: list[PathMetrics],
        max_lat: float | None,
        min_rel: float | None,
    ) -> list[PathMetrics]:
        """Filter candidate paths by SLA bounds if specified and valid."""
        valid_paths = paths
        if max_lat is not None:
            filtered = [p for p in valid_paths if p.observed_latency_ms <= max_lat]
            if filtered:
                valid_paths = filtered
        if min_rel is not None:
            filtered = [p for p in valid_paths if p.observed_reliability >= min_rel]
            if filtered:
                valid_paths = filtered
        return valid_paths

    def _resolve_current_path(
        self, paths: list[PathMetrics], current_path_id: str | None
    ) -> PathMetrics:
        """Find baseline execution path by ID or default to primary path."""
        if current_path_id:
            found = next((p for p in paths if p.path_id == current_path_id), None)
            if found:
                return found
        return next((p for p in paths if p.path_id == "path_01"), paths[0])

    def optimize_workflow(
        self,
        events: Sequence[TraceEvent | dict[str, Any]] | None = None,
        candidate_paths: list[PathMetrics] | None = None,
        weights: MultiObjectiveWeight | None = None,
        workflow_definition_id: str = "order_fulfillment",
        current_path_id: str | None = None,
        active_incident_culprit: str | None = None,
        max_latency_constraint_ms: float | None = None,
        min_reliability_constraint: float | None = None,
    ) -> OptimizationRecommendation:
        """Evaluate candidate execution paths and generate advisory optimization recommendation."""
        w = weights or MultiObjectiveWeight(latency=0.40, cost=0.30, reliability=0.30)
        opt_id = f"opt_{uuid4().hex[:10]}"

        # 1. Obtain & adjust candidate paths
        paths = self._resolve_candidate_paths(events, candidate_paths)
        if active_incident_culprit:
            paths = self._apply_incident_penalty(paths, active_incident_culprit)

        # 2. Compute Pareto frontier
        pareto_points = self.pareto_calculator.compute_frontier(paths, weights=w)
        point_map = {pt.path_id: pt for pt in pareto_points}

        # 3. Filter by SLA constraints & rank
        valid_paths = self._filter_sla_constraints(
            paths, max_latency_constraint_ms, min_reliability_constraint
        )

        def _get_path_sort_key(p: PathMetrics) -> tuple[bool, float]:
            pt = point_map.get(p.path_id)
            if pt is not None:
                return (pt.is_pareto_optimal, pt.utility_score)
            return (False, 0.0)

        ranked_paths = sorted(valid_paths, key=_get_path_sort_key, reverse=True)
        recommended = ranked_paths[0]
        current = self._resolve_current_path(paths, current_path_id)

        # 4. Compute savings and rationale
        savings = self._compute_expected_savings(
            current=current,
            recommended=recommended,
            w=w,
            frontier_points=pareto_points,
        )

        strategy_type = "INCIDENT_DIVERSION" if active_incident_culprit else "MULTI_OBJECTIVE"
        rationale = self._generate_rationale(
            current=current,
            recommended=recommended,
            savings=savings,
            w=w,
            active_incident=active_incident_culprit,
        )

        logger.info(
            "workflow_optimized",
            workflow_id=workflow_definition_id,
            recommended_path=recommended.path_id,
            utility_gain=savings.overall_utility_improvement_pct,
            incident_culprit=active_incident_culprit,
        )

        return OptimizationRecommendation(
            id=opt_id,
            workflow_definition_id=workflow_definition_id,
            optimization_type=strategy_type,
            weights=w,
            current_path=current,
            recommended_path=recommended,
            pareto_frontier=pareto_points,
            all_evaluated_paths=paths,
            expected_savings=savings,
            rationale=rationale,
            active_incident_culprit=active_incident_culprit,
        )
