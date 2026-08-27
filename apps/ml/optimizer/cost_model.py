"""Explicit and transparent resource cost modeling engine."""

from apps.ml.optimizer.models import CostBreakdown, CostModelConfig, PathStep


class ResourceCostModel:
    """Calculates transparent modeled resource cost units for execution paths."""

    def __init__(self, config: CostModelConfig | None = None) -> None:
        self.config = config or CostModelConfig()

    def calculate_cost(
        self,
        steps: list[PathStep],
        retry_rate: float = 0.0,
    ) -> CostBreakdown:
        """Compute itemized resource cost units for an execution path sequence.

        Parameters
        ----------
        steps : list[PathStep]
            Ordered sequence of microservice and database operations in the path.
        retry_rate : float
            Empirical historical retry frequency (e.g. 0.05 = 5% retries).

        Returns
        -------
        CostBreakdown
            Itemized compute units, database I/O units, retry penalties, and total cost.
        """
        compute_units = 0.0
        db_io_units = 0.0
        step_costs: dict[str, float] = {}

        for step in steps:
            svc = step.service
            base_cost = self.config.service_base_costs.get(svc, self.config.default_step_cost)

            if step.is_database or "db" in svc:
                db_io = self.config.db_io_unit_cost
                db_io_units += db_io
                total_step = base_cost + db_io
            elif step.is_cache or "cache" in svc:
                total_step = base_cost * 0.5  # Cache efficiency discount
                compute_units += total_step
            else:
                total_step = base_cost
                compute_units += total_step

            step_sig = f"{svc}:{step.operation}"
            step_costs[step_sig] = round(total_step, 2)

        # Retry penalty calculation
        base_sum = compute_units + db_io_units
        retry_penalty_units = round(
            base_sum * (retry_rate * self.config.retry_penalty_multiplier), 2
        )
        total_modeled_cost = round(base_sum + retry_penalty_units, 2)

        return CostBreakdown(
            compute_units=round(compute_units, 2),
            db_io_units=round(db_io_units, 2),
            retry_penalty_units=retry_penalty_units,
            total_modeled_cost=total_modeled_cost,
            step_costs=step_costs,
        )
