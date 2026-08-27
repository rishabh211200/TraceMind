"""Pydantic schemas for multi-objective workflow path optimization endpoints."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class CostBreakdownResponse(BaseModel):
    """Transparent itemized breakdown of modeled resource cost units."""

    compute_units: float = Field(..., description="Base CPU/microservice compute units")
    db_io_units: float = Field(..., description="Database I/O read/write units")
    retry_penalty_units: float = Field(
        ..., description="Penalty units incurred from retry amplification"
    )
    total_modeled_cost: float = Field(..., description="Sum of all modeled resource cost units")
    step_costs: dict[str, float] = Field(
        default_factory=dict, description="Cost per individual step"
    )


class PathStepResponse(BaseModel):
    """A single service operation step within an execution path."""

    service: str
    operation: str
    is_database: bool = False
    is_cache: bool = False
    is_fallback: bool = False


class PathMetricsResponse(BaseModel):
    """Empirical observed metrics and modeled cost for a candidate execution path."""

    path_id: str
    steps: list[PathStepResponse]
    step_signatures: list[str]
    observed_latency_ms: float
    observed_p95_latency_ms: float
    observed_p99_latency_ms: float
    observed_reliability: float
    observed_retry_rate: float
    observation_count: int
    statistical_confidence: float
    cost_breakdown: CostBreakdownResponse
    modeled_cost_units: float


class MultiObjectiveWeightConfig(BaseModel):
    """Normalized weights for multi-objective optimization."""

    latency: float = Field(default=0.40, ge=0.0, le=1.0)
    cost: float = Field(default=0.30, ge=0.0, le=1.0)
    reliability: float = Field(default=0.30, ge=0.0, le=1.0)


class ParetoPointResponse(BaseModel):
    """A point on the 3D Pareto frontier."""

    path_id: str
    step_signatures: list[str]
    observed_latency_ms: float
    modeled_cost_units: float
    observed_reliability: float
    utility_score: float
    statistical_confidence: float
    is_pareto_optimal: bool = True


class ExpectedSavingsResponse(BaseModel):
    """Projected percentage improvements comparing recommended path vs baseline."""

    latency_reduction_pct: float
    cost_reduction_pct: float
    reliability_gain_pct: float
    overall_utility_improvement_pct: float
    absolute_latency_delta_ms: float
    absolute_cost_delta_units: float


class OptimizationRecommendRequest(BaseModel):
    """Request payload to calculate optimal path recommendations."""

    workflow_definition_id: str = Field(default="order_fulfillment")
    weight_latency: float = Field(default=0.40, ge=0.0, le=1.0)
    weight_cost: float = Field(default=0.30, ge=0.0, le=1.0)
    weight_reliability: float = Field(default=0.30, ge=0.0, le=1.0)
    current_path_id: str | None = Field(
        default=None, description="Optional baseline path ID for comparison"
    )
    active_incident_culprit: str | None = Field(
        default=None, description="Optional active bottleneck service for advisory detour"
    )
    max_latency_constraint_ms: float | None = Field(
        default=None, description="Optional SLA upper bound on latency"
    )
    min_reliability_constraint: float | None = Field(
        default=None, description="Optional SLA lower bound on reliability"
    )
    persist_to_db: bool = Field(
        default=False, description="Persist optimization report to database"
    )


class OptimizationReportResponse(BaseModel):
    """Complete path optimization recommendation report."""

    id: str
    workflow_definition_id: str
    optimization_type: str
    weights: MultiObjectiveWeightConfig
    current_path: PathMetricsResponse | None
    recommended_path: PathMetricsResponse
    pareto_frontier: list[ParetoPointResponse]
    all_evaluated_paths: list[PathMetricsResponse]
    expected_savings: ExpectedSavingsResponse
    rationale: str
    active_incident_culprit: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OptimizationHistoryItem(BaseModel):
    """Brief metadata summary for an optimization run."""

    id: str
    workflow_definition_id: str
    optimization_type: str
    recommended_path_id: str
    weight_latency: float
    weight_cost: float
    weight_reliability: float
    expected_latency_reduction_pct: float
    expected_reliability_gain_pct: float
    active_incident_culprit: str | None = None
    created_at: datetime


class OptimizationHistoryResponse(BaseModel):
    """Paginated list of historical optimization recommendations."""

    items: list[OptimizationHistoryItem]
    total: int
    limit: int
    offset: int


class OptimizerStatsResponse(BaseModel):
    """System-wide summary metrics for workflow optimization."""

    total_optimizations: int
    strategy_breakdown: dict[str, int]
    avg_weight_latency: float
    avg_weight_cost: float
    avg_weight_reliability: float
    most_recent_optimization: dict[str, Any] | None = None
