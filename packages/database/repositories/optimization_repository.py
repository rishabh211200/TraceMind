"""Async repository for querying and persisting workflow path optimizations."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.optimization import OptimizationModel


class OptimizationRepository:
    """Async repository providing CRUD and analytics for workflow optimizations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_optimization(
        self,
        workflow_definition_id: str,
        optimization_type: str,
        weight_latency: float,
        weight_cost: float,
        weight_reliability: float,
        current_path: dict[str, Any] | None,
        recommended_path: dict[str, Any],
        pareto_frontier: list[dict[str, Any]],
        all_evaluated_paths: list[dict[str, Any]],
        expected_savings: dict[str, Any],
        cost_model_breakdown: dict[str, Any],
        rationale: str,
        active_incident_culprit: str | None = None,
        optimization_id: str | None = None,
        created_at: datetime | None = None,
    ) -> OptimizationModel:
        """Create and persist a new workflow optimization recommendation."""
        record_id = optimization_id or f"opt_{uuid4().hex[:10]}"
        now = created_at or datetime.now(UTC)

        model = OptimizationModel(
            id=record_id,
            workflow_definition_id=workflow_definition_id,
            optimization_type=optimization_type,
            weight_latency=float(weight_latency),
            weight_cost=float(weight_cost),
            weight_reliability=float(weight_reliability),
            current_path=current_path,
            recommended_path=recommended_path,
            pareto_frontier=pareto_frontier,
            all_evaluated_paths=all_evaluated_paths,
            expected_savings=expected_savings,
            cost_model_breakdown=cost_model_breakdown,
            rationale=rationale,
            active_incident_culprit=active_incident_culprit,
            created_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_id(self, optimization_id: str) -> OptimizationModel | None:
        """Fetch a specific optimization recommendation by ID."""
        stmt = select(OptimizationModel).where(OptimizationModel.id == optimization_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_optimizations(
        self,
        workflow_definition_id: str | None = None,
        optimization_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OptimizationModel], int]:
        """List optimization recommendations with filtering and pagination."""
        stmt = select(OptimizationModel)
        count_stmt = select(func.count(OptimizationModel.id))

        if workflow_definition_id:
            stmt = stmt.where(OptimizationModel.workflow_definition_id == workflow_definition_id)
            count_stmt = count_stmt.where(
                OptimizationModel.workflow_definition_id == workflow_definition_id
            )

        if optimization_type:
            stmt = stmt.where(OptimizationModel.optimization_type == optimization_type)
            count_stmt = count_stmt.where(OptimizationModel.optimization_type == optimization_type)

        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one() or 0)

        stmt = stmt.order_by(desc(OptimizationModel.created_at)).limit(limit).offset(offset)
        items_result = await self.session.execute(stmt)
        return list(items_result.scalars().all()), total

    async def get_stats(self) -> dict[str, Any]:
        """Compute aggregate summary statistics for all historical optimizations."""
        total_stmt = select(func.count(OptimizationModel.id))
        total_res = await self.session.execute(total_stmt)
        total_count = int(total_res.scalar_one() or 0)

        if total_count == 0:
            return {
                "total_optimizations": 0,
                "strategy_breakdown": {},
                "avg_weight_latency": 0.40,
                "avg_weight_cost": 0.30,
                "avg_weight_reliability": 0.30,
                "most_recent_optimization": None,
            }

        # Strategy breakdown
        strat_stmt = select(
            OptimizationModel.optimization_type,
            func.count(OptimizationModel.id),
        ).group_by(OptimizationModel.optimization_type)
        strat_res = await self.session.execute(strat_stmt)
        strategy_breakdown = {row[0]: row[1] for row in strat_res.all()}

        # Average weights
        avg_weights_stmt = select(
            func.avg(OptimizationModel.weight_latency),
            func.avg(OptimizationModel.weight_cost),
            func.avg(OptimizationModel.weight_reliability),
        )
        avg_weights_res = await self.session.execute(avg_weights_stmt)
        w_lat, w_cost, w_rel = avg_weights_res.one()

        # Most recent
        recent_stmt = (
            select(OptimizationModel).order_by(desc(OptimizationModel.created_at)).limit(1)
        )
        recent_res = await self.session.execute(recent_stmt)
        recent_obj = recent_res.scalars().first()

        return {
            "total_optimizations": total_count,
            "strategy_breakdown": strategy_breakdown,
            "avg_weight_latency": round(float(w_lat or 0.40), 3),
            "avg_weight_cost": round(float(w_cost or 0.30), 3),
            "avg_weight_reliability": round(float(w_rel or 0.30), 3),
            "most_recent_optimization": (
                {
                    "id": recent_obj.id,
                    "workflow_definition_id": recent_obj.workflow_definition_id,
                    "optimization_type": recent_obj.optimization_type,
                    "created_at": recent_obj.created_at.isoformat(),
                }
                if recent_obj
                else None
            ),
        }
