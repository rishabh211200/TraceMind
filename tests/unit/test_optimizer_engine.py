"""Unit tests for Workflow Optimizer engine, cost model, and Pareto frontier calculator."""

import pytest

from apps.ml.optimizer.cost_model import ResourceCostModel
from apps.ml.optimizer.engine import WorkflowOptimizer
from apps.ml.optimizer.models import (
    CostModelConfig,
    MultiObjectiveWeight,
    PathMetrics,
    PathStep,
)
from apps.ml.optimizer.pareto import ParetoFrontierCalculator
from apps.ml.optimizer.path_extractor import PathExtractor
from packages.domain.events import EventStatus, EventType, TraceEvent


@pytest.fixture
def cost_model() -> ResourceCostModel:
    return ResourceCostModel(CostModelConfig())


@pytest.fixture
def path_extractor(cost_model: ResourceCostModel) -> PathExtractor:
    return PathExtractor(cost_model=cost_model, min_observation_threshold=10)


@pytest.fixture
def pareto_calc() -> ParetoFrontierCalculator:
    return ParetoFrontierCalculator()


@pytest.fixture
def optimizer(
    cost_model: ResourceCostModel,
    path_extractor: PathExtractor,
    pareto_calc: ParetoFrontierCalculator,
) -> WorkflowOptimizer:
    return WorkflowOptimizer(
        cost_model=cost_model,
        path_extractor=path_extractor,
        pareto_calculator=pareto_calc,
    )


class TestResourceCostModel:
    """Test suite for explicit, transparent resource cost calculations."""

    def test_cost_calculation_with_database_and_cache(self, cost_model: ResourceCostModel) -> None:
        steps = [
            PathStep("api-gateway", "start_workflow"),
            PathStep("customer-service", "get_customer"),
            PathStep("customer-db", "query_customer", is_database=True),
            PathStep("customer-cache", "lookup_cache", is_cache=True),
        ]
        breakdown = cost_model.calculate_cost(steps, retry_rate=0.0)

        # api-gateway(2.0) + customer-service(1.5) + customer-db(3.0 + 2.5 DB IO) + customer-cache(0.5 * 0.5)
        # Compute: 2.0 + 1.5 + 0.25 = 3.75; DB IO: 3.0 + 2.5 = 5.5
        assert breakdown.compute_units > 0
        assert breakdown.db_io_units > 0
        assert breakdown.retry_penalty_units == 0.0
        assert breakdown.total_modeled_cost > 5.0
        assert len(breakdown.step_costs) == 4

    def test_cost_calculation_with_retry_penalty(self, cost_model: ResourceCostModel) -> None:
        steps = [
            PathStep("payment-service", "charge"),
            PathStep("payment-gateway", "process"),
        ]
        breakdown_clean = cost_model.calculate_cost(steps, retry_rate=0.0)
        breakdown_retries = cost_model.calculate_cost(steps, retry_rate=0.10)

        assert breakdown_retries.retry_penalty_units > 0
        assert breakdown_retries.total_modeled_cost > breakdown_clean.total_modeled_cost


class TestParetoFrontierCalculator:
    """Test suite for 3D multi-objective Pareto dominance."""

    def test_pareto_dominance_logic(
        self, pareto_calc: ParetoFrontierCalculator, cost_model: ResourceCostModel
    ) -> None:
        # Superior path: 100ms, cost 5u, 99% reliability
        p_superior = PathMetrics(
            path_id="p_good",
            steps=[],
            step_signatures=["a", "b"],
            observed_latency_ms=100.0,
            observed_p95_latency_ms=120.0,
            observed_p99_latency_ms=150.0,
            observed_reliability=0.99,
            observed_retry_rate=0.0,
            observation_count=50,
            statistical_confidence=1.0,
            cost_breakdown=cost_model.calculate_cost([]),
            modeled_cost_units=5.0,
        )

        # Dominated path: 300ms, cost 10u, 95% reliability (worse in all dimensions)
        p_dominated = PathMetrics(
            path_id="p_bad",
            steps=[],
            step_signatures=["a", "b"],
            observed_latency_ms=300.0,
            observed_p95_latency_ms=350.0,
            observed_p99_latency_ms=400.0,
            observed_reliability=0.95,
            observed_retry_rate=0.05,
            observation_count=50,
            statistical_confidence=1.0,
            cost_breakdown=cost_model.calculate_cost([]),
            modeled_cost_units=10.0,
        )

        assert pareto_calc.is_dominated(p_candidate=p_dominated, p_other=p_superior) is True
        assert pareto_calc.is_dominated(p_candidate=p_superior, p_other=p_dominated) is False

        frontier = pareto_calc.compute_frontier([p_superior, p_dominated])
        assert len(frontier) == 2

        superior_pt = next(pt for pt in frontier if pt.path_id == "p_good")
        dominated_pt = next(pt for pt in frontier if pt.path_id == "p_bad")
        assert superior_pt.is_pareto_optimal is True
        assert dominated_pt.is_pareto_optimal is False


class TestWorkflowOptimizer:
    """Test suite for WorkflowOptimizer recommendations and advisory diversion."""

    def test_canonical_paths_optimization_balanced(self, optimizer: WorkflowOptimizer) -> None:
        rec = optimizer.optimize_workflow(
            weights=MultiObjectiveWeight(latency=0.40, cost=0.30, reliability=0.30)
        )
        assert rec.recommended_path is not None
        assert rec.expected_savings is not None
        assert rec.optimization_type == "MULTI_OBJECTIVE"
        assert len(rec.pareto_frontier) >= 3

    def test_extreme_weights_behavior(self, optimizer: WorkflowOptimizer) -> None:
        # Latency-only priority (1.0, 0.0, 0.0)
        rec_lat = optimizer.optimize_workflow(
            weights=MultiObjectiveWeight(latency=1.0, cost=0.0, reliability=0.0)
        )
        # Cost-only priority (0.0, 1.0, 0.0)
        rec_cost = optimizer.optimize_workflow(
            weights=MultiObjectiveWeight(latency=0.0, cost=1.0, reliability=0.0)
        )

        assert (
            rec_lat.recommended_path.observed_latency_ms
            <= rec_cost.recommended_path.observed_latency_ms
        )
        assert (
            rec_cost.recommended_path.modeled_cost_units
            <= rec_lat.recommended_path.modeled_cost_units
        )

    def test_advisory_incident_diversion_rerouting(self, optimizer: WorkflowOptimizer) -> None:
        # Active bottleneck on inventory-db
        rec = optimizer.optimize_workflow(active_incident_culprit="inventory-db")
        assert rec.optimization_type == "INCIDENT_DIVERSION"
        assert rec.active_incident_culprit == "inventory-db"
        # Recommended path must bypass inventory-db (use cache or alternate)
        assert not any("inventory-db" in step.service for step in rec.recommended_path.steps)
        # Expected savings must demonstrate positive reliability and latency gain
        assert (
            rec.expected_savings.reliability_gain_pct >= 15.0
            or rec.expected_savings.latency_reduction_pct >= 15.0
        )
        assert "Advisory Incident Diversion" in rec.rationale

    def test_sla_constraint_enforcement(self, optimizer: WorkflowOptimizer) -> None:
        # Require max latency <= 200ms
        rec = optimizer.optimize_workflow(max_latency_constraint_ms=200.0)
        assert rec.recommended_path.observed_latency_ms <= 200.0

    def test_path_extraction_from_events(self, optimizer: WorkflowOptimizer) -> None:
        # Generate synthetic trace events
        events = [
            TraceEvent(
                execution_id="exec_1",
                workflow_id="order_fulfillment",
                service="api-gateway",
                operation="start",
                latency_ms=10.0,
                status=EventStatus.SUCCESS,
                event_type=EventType.SERVICE_STARTED,
            ),
            TraceEvent(
                execution_id="exec_1",
                workflow_id="order_fulfillment",
                service="customer-cache",
                operation="lookup",
                latency_ms=15.0,
                status=EventStatus.SUCCESS,
                event_type=EventType.SERVICE_COMPLETED,
            ),
            TraceEvent(
                execution_id="exec_1",
                workflow_id="order_fulfillment",
                service="api-gateway",
                operation="end",
                latency_ms=10.0,
                status=EventStatus.SUCCESS,
                event_type=EventType.SERVICE_COMPLETED,
            ),
        ]
        paths = optimizer.path_extractor.extract_paths_from_events(events)
        assert len(paths) >= 1
        assert paths[0].observation_count == 1
        # Statistical confidence should reflect small sample size
        assert paths[0].statistical_confidence == 0.1
