"""Multi-objective 3D Pareto optimal frontier calculation engine."""

from apps.ml.optimizer.models import MultiObjectiveWeight, ParetoPoint, PathMetrics


class ParetoFrontierCalculator:
    """Calculates non-dominated 3D Pareto optimal paths across Latency, Cost, and Reliability."""

    def is_dominated(self, p_candidate: PathMetrics, p_other: PathMetrics) -> bool:
        """Check if p_candidate is dominated by p_other.

        p_other dominates p_candidate if:
        1. Latency is <= candidate (lower is better)
        2. Modeled cost is <= candidate (lower is better)
        3. Reliability is >= candidate (higher is better)
        AND at least one objective is strictly better.
        """
        l_cand, l_other = p_candidate.observed_latency_ms, p_other.observed_latency_ms
        c_cand, c_other = p_candidate.modeled_cost_units, p_other.modeled_cost_units
        r_cand, r_other = p_candidate.observed_reliability, p_other.observed_reliability

        is_no_worse = (l_other <= l_cand) and (c_other <= c_cand) and (r_other >= r_cand)
        is_strictly_better = (l_other < l_cand) or (c_other < c_cand) or (r_other > r_cand)

        return bool(is_no_worse and is_strictly_better)

    def compute_frontier(
        self,
        paths: list[PathMetrics],
        weights: MultiObjectiveWeight | None = None,
    ) -> list[ParetoPoint]:
        """Compute the non-dominated Pareto frontier from candidate execution paths."""
        if not paths:
            return []

        w = weights or MultiObjectiveWeight()

        # Compute min/max bounds for utility normalization
        min_lat = min(p.observed_latency_ms for p in paths)
        max_lat = max(p.observed_latency_ms for p in paths)
        lat_range = max(1.0, max_lat - min_lat)

        min_cost = min(p.modeled_cost_units for p in paths)
        max_cost = max(p.modeled_cost_units for p in paths)
        cost_range = max(0.1, max_cost - min_cost)

        pareto_points: list[ParetoPoint] = []

        for p in paths:
            dominated = False
            for other in paths:
                if p.path_id != other.path_id and self.is_dominated(p, other):
                    dominated = True
                    break

            # Utility score
            u_lat = max(0.0, 1.0 - (p.observed_latency_ms - min_lat) / lat_range)
            u_cost = max(0.0, 1.0 - (p.modeled_cost_units - min_cost) / cost_range)
            u_rel = p.observed_reliability

            utility_score = (w.latency * u_lat) + (w.cost * u_cost) + (w.reliability * u_rel)
            # Apply confidence discount if observation count is low
            adjusted_score = utility_score * (0.5 + 0.5 * p.statistical_confidence)

            pareto_points.append(
                ParetoPoint(
                    path_id=p.path_id,
                    step_signatures=p.step_signatures,
                    observed_latency_ms=p.observed_latency_ms,
                    modeled_cost_units=p.modeled_cost_units,
                    observed_reliability=p.observed_reliability,
                    utility_score=round(adjusted_score, 4),
                    statistical_confidence=p.statistical_confidence,
                    is_pareto_optimal=not dominated,
                )
            )

        return pareto_points
