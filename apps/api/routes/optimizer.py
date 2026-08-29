"""FastAPI router for multi-objective workflow path optimization and advisory routing."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.exceptions import EntityNotFoundException
from apps.api.schemas.optimizer import (
    CostBreakdownResponse,
    ExpectedSavingsResponse,
    MultiObjectiveWeightConfig,
    OptimizationHistoryItem,
    OptimizationHistoryResponse,
    OptimizationRecommendRequest,
    OptimizationReportResponse,
    OptimizerStatsResponse,
    ParetoPointResponse,
    PathMetricsResponse,
    PathStepResponse,
)
from apps.ml.optimizer.engine import WorkflowOptimizer
from apps.ml.optimizer.models import (
    MultiObjectiveWeight,
    PathMetrics,
)
from packages.database.models.trace_event import TraceEventModel
from packages.database.repositories.optimization_repository import OptimizationRepository
from packages.database.session import get_db_session

router = APIRouter(prefix="/api/v1/optimizer", tags=["Optimizer"])

_optimizer = WorkflowOptimizer()


def _map_path_metrics_to_schema(p: PathMetrics) -> PathMetricsResponse:
    """Helper to convert internal PathMetrics dataclass to Pydantic schema."""
    return PathMetricsResponse(
        path_id=p.path_id,
        steps=[
            PathStepResponse(
                service=s.service,
                operation=s.operation,
                is_database=s.is_database,
                is_cache=s.is_cache,
                is_fallback=s.is_fallback,
            )
            for s in p.steps
        ],
        step_signatures=p.step_signatures,
        observed_latency_ms=p.observed_latency_ms,
        observed_p95_latency_ms=p.observed_p95_latency_ms,
        observed_p99_latency_ms=p.observed_p99_latency_ms,
        observed_reliability=p.observed_reliability,
        observed_retry_rate=p.observed_retry_rate,
        observation_count=p.observation_count,
        statistical_confidence=p.statistical_confidence,
        cost_breakdown=CostBreakdownResponse(
            compute_units=p.cost_breakdown.compute_units,
            db_io_units=p.cost_breakdown.db_io_units,
            retry_penalty_units=p.cost_breakdown.retry_penalty_units,
            total_modeled_cost=p.cost_breakdown.total_modeled_cost,
            step_costs=p.cost_breakdown.step_costs,
        ),
        modeled_cost_units=p.modeled_cost_units,
    )


@router.post(
    "/recommend",
    response_model=OptimizationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute Multi-Objective Path Recommendation",
)
async def recommend_optimal_path(
    payload: OptimizationRecommendRequest,
    session: AsyncSession = Depends(get_db_session),
) -> OptimizationReportResponse:
    """Calculate the optimal execution path across Latency, Cost, and Reliability."""
    weights = MultiObjectiveWeight(
        latency=payload.weight_latency,
        cost=payload.weight_cost,
        reliability=payload.weight_reliability,
    )

    # Reconstruct paths from historical telemetry if available, else canonical templates
    stmt = select(TraceEventModel).limit(500)
    res = await session.execute(stmt)
    recent_events = list(res.scalars().all())
    event_dicts = (
        [
            {
                "execution_id": e.execution_id,
                "service": e.service,
                "operation": e.operation,
                "latency_ms": e.latency_ms,
                "status": e.status,
                "event_type": e.event_type,
            }
            for e in recent_events
        ]
        if recent_events
        else None
    )

    recommendation = _optimizer.optimize_workflow(
        events=event_dicts,
        weights=weights,
        workflow_definition_id=payload.workflow_definition_id,
        current_path_id=payload.current_path_id,
        active_incident_culprit=payload.active_incident_culprit,
        max_latency_constraint_ms=payload.max_latency_constraint_ms,
        min_reliability_constraint=payload.min_reliability_constraint,
    )

    from packages.observability.metrics import record_optimization

    record_optimization(
        optimization_type=recommendation.optimization_type.value
        if hasattr(recommendation.optimization_type, "value")
        else str(recommendation.optimization_type),
        workflow_id=payload.workflow_definition_id,
    )

    current_schema = (
        _map_path_metrics_to_schema(recommendation.current_path)
        if recommendation.current_path
        else None
    )
    rec_schema = _map_path_metrics_to_schema(recommendation.recommended_path)

    pareto_schemas = [
        ParetoPointResponse(
            path_id=pt.path_id,
            step_signatures=pt.step_signatures,
            observed_latency_ms=pt.observed_latency_ms,
            modeled_cost_units=pt.modeled_cost_units,
            observed_reliability=pt.observed_reliability,
            utility_score=pt.utility_score,
            statistical_confidence=pt.statistical_confidence,
            is_pareto_optimal=pt.is_pareto_optimal,
        )
        for pt in recommendation.pareto_frontier
    ]

    all_schemas = [_map_path_metrics_to_schema(p) for p in recommendation.all_evaluated_paths]

    savings_schema = ExpectedSavingsResponse(
        latency_reduction_pct=recommendation.expected_savings.latency_reduction_pct,
        cost_reduction_pct=recommendation.expected_savings.cost_reduction_pct,
        reliability_gain_pct=recommendation.expected_savings.reliability_gain_pct,
        overall_utility_improvement_pct=recommendation.expected_savings.overall_utility_improvement_pct,
        absolute_latency_delta_ms=recommendation.expected_savings.absolute_latency_delta_ms,
        absolute_cost_delta_units=recommendation.expected_savings.absolute_cost_delta_units,
    )

    # Optional DB Persistence
    if payload.persist_to_db:
        repo = OptimizationRepository(session)
        await repo.save_optimization(
            workflow_definition_id=payload.workflow_definition_id,
            optimization_type=recommendation.optimization_type,
            weight_latency=weights.latency,
            weight_cost=weights.cost,
            weight_reliability=weights.reliability,
            current_path=current_schema.model_dump() if current_schema else None,
            recommended_path=rec_schema.model_dump(),
            pareto_frontier=[pt.model_dump() for pt in pareto_schemas],
            all_evaluated_paths=[p.model_dump() for p in all_schemas],
            expected_savings=savings_schema.model_dump(),
            cost_model_breakdown=rec_schema.cost_breakdown.model_dump(),
            rationale=recommendation.rationale,
            active_incident_culprit=payload.active_incident_culprit,
            optimization_id=recommendation.id,
            created_at=recommendation.created_at,
        )

    return OptimizationReportResponse(
        id=recommendation.id,
        workflow_definition_id=recommendation.workflow_definition_id,
        optimization_type=recommendation.optimization_type,
        weights=MultiObjectiveWeightConfig(
            latency=weights.latency,
            cost=weights.cost,
            reliability=weights.reliability,
        ),
        current_path=current_schema,
        recommended_path=rec_schema,
        pareto_frontier=pareto_schemas,
        all_evaluated_paths=all_schemas,
        expected_savings=savings_schema,
        rationale=recommendation.rationale,
        active_incident_culprit=recommendation.active_incident_culprit,
        created_at=recommendation.created_at,
    )


@router.get(
    "/paths/{workflow_definition_id}",
    response_model=list[PathMetricsResponse],
    summary="List Candidate Paths & Metrics",
)
async def list_candidate_paths(
    workflow_definition_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[PathMetricsResponse]:
    """Retrieve all candidate execution paths and their empirical observed and modeled metrics."""
    paths = _optimizer.path_extractor.get_canonical_order_paths()
    return [_map_path_metrics_to_schema(p) for p in paths]


@router.get(
    "/pareto/{workflow_definition_id}",
    response_model=list[ParetoPointResponse],
    summary="Get 3D Pareto Optimal Frontier",
)
async def get_pareto_frontier(
    workflow_definition_id: str,
    weight_latency: float = Query(default=0.40, ge=0.0, le=1.0),
    weight_cost: float = Query(default=0.30, ge=0.0, le=1.0),
    weight_reliability: float = Query(default=0.30, ge=0.0, le=1.0),
) -> list[ParetoPointResponse]:
    """Calculate the 3D non-dominated Pareto frontier across Latency, Cost, and Reliability."""
    weights = MultiObjectiveWeight(
        latency=weight_latency, cost=weight_cost, reliability=weight_reliability
    )
    paths = _optimizer.path_extractor.get_canonical_order_paths()
    pts = _optimizer.pareto_calculator.compute_frontier(paths, weights=weights)
    return [
        ParetoPointResponse(
            path_id=pt.path_id,
            step_signatures=pt.step_signatures,
            observed_latency_ms=pt.observed_latency_ms,
            modeled_cost_units=pt.modeled_cost_units,
            observed_reliability=pt.observed_reliability,
            utility_score=pt.utility_score,
            statistical_confidence=pt.statistical_confidence,
            is_pareto_optimal=pt.is_pareto_optimal,
        )
        for pt in pts
    ]


@router.get(
    "/history",
    response_model=OptimizationHistoryResponse,
    summary="List Optimization History",
)
async def list_optimization_history(
    workflow_definition_id: str | None = Query(default=None),
    optimization_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> OptimizationHistoryResponse:
    """Retrieve paginated historical workflow optimization recommendations."""
    repo = OptimizationRepository(session)
    records, total = await repo.list_optimizations(
        workflow_definition_id=workflow_definition_id,
        optimization_type=optimization_type,
        limit=limit,
        offset=offset,
    )

    items = [
        OptimizationHistoryItem(
            id=r.id,
            workflow_definition_id=r.workflow_definition_id,
            optimization_type=r.optimization_type,
            recommended_path_id=r.recommended_path.get("path_id", "unknown"),
            weight_latency=r.weight_latency,
            weight_cost=r.weight_cost,
            weight_reliability=r.weight_reliability,
            expected_latency_reduction_pct=float(
                r.expected_savings.get("latency_reduction_pct", 0.0)
            ),
            expected_reliability_gain_pct=float(
                r.expected_savings.get("reliability_gain_pct", 0.0)
            ),
            active_incident_culprit=r.active_incident_culprit,
            created_at=r.created_at,
        )
        for r in records
    ]

    return OptimizationHistoryResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/stats",
    response_model=OptimizerStatsResponse,
    summary="Get System-Wide Optimizer Statistics",
)
async def get_optimizer_stats(
    session: AsyncSession = Depends(get_db_session),
) -> OptimizerStatsResponse:
    """Retrieve aggregate optimization metrics and historical savings."""
    repo = OptimizationRepository(session)
    stats = await repo.get_stats()
    return OptimizerStatsResponse(
        total_optimizations=stats["total_optimizations"],
        strategy_breakdown=stats["strategy_breakdown"],
        avg_weight_latency=stats["avg_weight_latency"],
        avg_weight_cost=stats["avg_weight_cost"],
        avg_weight_reliability=stats["avg_weight_reliability"],
        most_recent_optimization=stats["most_recent_optimization"],
    )


@router.get(
    "/{id}",
    response_model=OptimizationReportResponse,
    summary="Get Optimization Report by ID",
)
async def get_optimization_by_id(
    id: str,
    session: AsyncSession = Depends(get_db_session),
) -> OptimizationReportResponse:
    """Retrieve a specific historical optimization report by ID."""
    repo = OptimizationRepository(session)
    record = await repo.get_by_id(id)
    if not record:
        raise EntityNotFoundException(entity_type="WorkflowOptimization", entity_id=id)

    return OptimizationReportResponse(
        id=record.id,
        workflow_definition_id=record.workflow_definition_id,
        optimization_type=record.optimization_type,
        weights=MultiObjectiveWeightConfig(
            latency=record.weight_latency,
            cost=record.weight_cost,
            reliability=record.weight_reliability,
        ),
        current_path=PathMetricsResponse.model_validate(record.current_path)
        if record.current_path
        else None,
        recommended_path=PathMetricsResponse.model_validate(record.recommended_path),
        pareto_frontier=[ParetoPointResponse.model_validate(pt) for pt in record.pareto_frontier],
        all_evaluated_paths=[
            PathMetricsResponse.model_validate(p) for p in record.all_evaluated_paths
        ],
        expected_savings=ExpectedSavingsResponse.model_validate(record.expected_savings),
        rationale=record.rationale,
        active_incident_culprit=record.active_incident_culprit,
        created_at=record.created_at,
    )
