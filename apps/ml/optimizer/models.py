"""Domain models and dataclasses for workflow path optimization."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CostModelConfig:
    """Configuration for transparent resource cost estimation."""

    service_base_costs: dict[str, float] = field(
        default_factory=lambda: {
            "api-gateway": 2.0,
            "auth-service": 1.0,
            "customer-service": 1.5,
            "customer-cache": 0.5,
            "customer-db": 3.0,
            "inventory-service": 1.5,
            "inventory-cache": 0.5,
            "inventory-db": 3.0,
            "pricing-service": 1.0,
            "payment-service": 2.0,
            "payment-gateway": 3.5,
            "order-service": 2.0,
            "notification-service": 1.0,
        }
    )
    db_io_unit_cost: float = 2.5
    retry_penalty_multiplier: float = 1.5
    default_step_cost: float = 1.0


@dataclass
class CostBreakdown:
    """Itemized breakdown of modeled resource cost units."""

    compute_units: float
    db_io_units: float
    retry_penalty_units: float
    total_modeled_cost: float
    step_costs: dict[str, float] = field(default_factory=dict)


@dataclass
class PathStep:
    """A single service operation step within an execution path."""

    service: str
    operation: str
    is_database: bool = False
    is_cache: bool = False
    is_fallback: bool = False


@dataclass
class PathMetrics:
    """Empirical observed metrics and modeled cost for an execution path."""

    path_id: str
    steps: list[PathStep]
    step_signatures: list[str]  # e.g. ["auth-service:auth", "customer-service:get_profile"]
    observed_latency_ms: float
    observed_p95_latency_ms: float
    observed_p99_latency_ms: float
    observed_reliability: float  # Empirical success rate [0.0, 1.0]
    observed_retry_rate: float
    observation_count: int
    statistical_confidence: float  # [0.0, 1.0] based on observation count vs threshold
    cost_breakdown: CostBreakdown
    modeled_cost_units: float


@dataclass
class MultiObjectiveWeight:
    """Normalized weights for multi-objective optimization (must sum to 1.0)."""

    latency: float = 0.40
    cost: float = 0.30
    reliability: float = 0.30

    def __post_init__(self) -> None:
        total = self.latency + self.cost + self.reliability
        if total > 0:
            self.latency = round(self.latency / total, 4)
            self.cost = round(self.cost / total, 4)
            self.reliability = round(self.reliability / total, 4)


@dataclass
class ParetoPoint:
    """A non-dominated point on the 3D Pareto frontier."""

    path_id: str
    step_signatures: list[str]
    observed_latency_ms: float
    modeled_cost_units: float
    observed_reliability: float
    utility_score: float
    statistical_confidence: float
    is_pareto_optimal: bool = True


@dataclass
class ExpectedSavings:
    """Projected percentage improvements comparing recommended path vs baseline."""

    latency_reduction_pct: float
    cost_reduction_pct: float
    reliability_gain_pct: float
    overall_utility_improvement_pct: float
    absolute_latency_delta_ms: float
    absolute_cost_delta_units: float


@dataclass
class OptimizationRecommendation:
    """Comprehensive path optimization recommendation report."""

    id: str
    workflow_definition_id: str
    optimization_type: str
    weights: MultiObjectiveWeight
    current_path: PathMetrics | None
    recommended_path: PathMetrics
    pareto_frontier: list[ParetoPoint]
    all_evaluated_paths: list[PathMetrics]
    expected_savings: ExpectedSavings
    rationale: str
    active_incident_culprit: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
