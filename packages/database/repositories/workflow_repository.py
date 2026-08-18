"""Workflow repository for managing workflow definitions and executions."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.workflow import (
    WorkflowDefinitionModel,
    WorkflowExecutionModel,
)


class WorkflowRepository:
    """Async repository for WorkflowDefinitionModel and WorkflowExecutionModel."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Workflow Definitions ---

    async def get_definition(self, definition_id: str) -> WorkflowDefinitionModel | None:
        """Fetch workflow definition by ID."""
        stmt = select(WorkflowDefinitionModel).where(WorkflowDefinitionModel.id == definition_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_definition(
        self, data: dict[str, Any] | WorkflowDefinitionModel
    ) -> WorkflowDefinitionModel:
        """Insert or update workflow definition."""
        if isinstance(data, WorkflowDefinitionModel):
            definition = await self.session.merge(data)
            await self.session.commit()
            return definition

        def_id = data["id"]
        existing = await self.get_definition(def_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            new_def = WorkflowDefinitionModel(**data)
            self.session.add(new_def)
            await self.session.commit()
            await self.session.refresh(new_def)
            return new_def

    async def list_definitions(self) -> list[WorkflowDefinitionModel]:
        """List all registered workflow definitions."""
        stmt = select(WorkflowDefinitionModel).order_by(WorkflowDefinitionModel.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_definition(self, definition_id: str) -> bool:
        """Safely delete workflow definition if no executions exist."""
        # Check if executions reference this definition
        count_stmt = select(func.count(WorkflowExecutionModel.id)).where(
            WorkflowExecutionModel.workflow_definition_id == definition_id
        )
        count = int((await self.session.execute(count_stmt)).scalar_one() or 0)
        if count > 0:
            from apps.api.exceptions import ConflictException

            raise ConflictException(
                f"Cannot delete workflow definition '{definition_id}' because {count} execution records are associated with it."
            )

        existing = await self.get_definition(definition_id)
        if not existing:
            return False

        await self.session.delete(existing)
        await self.session.commit()
        return True

    async def get_workflow_stats(
        self,
        definition_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute aggregate execution statistics for a workflow definition."""
        from sqlalchemy import case

        stmt = select(
            func.count(WorkflowExecutionModel.id).label("total_executions"),
            func.sum(case((WorkflowExecutionModel.status == "COMPLETED", 1), else_=0)).label(
                "completed_count"
            ),
            func.sum(case((WorkflowExecutionModel.status == "FAILED", 1), else_=0)).label(
                "failed_count"
            ),
            func.sum(case((WorkflowExecutionModel.status == "TIMEOUT", 1), else_=0)).label(
                "timeout_count"
            ),
            func.sum(case((WorkflowExecutionModel.is_incident_affected, 1), else_=0)).label(
                "incident_affected_count"
            ),
            func.avg(WorkflowExecutionModel.duration_ms).label("mean_duration"),
            func.min(WorkflowExecutionModel.duration_ms).label("min_duration"),
            func.max(WorkflowExecutionModel.duration_ms).label("max_duration"),
        ).where(WorkflowExecutionModel.workflow_definition_id == definition_id)

        if start_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at >= start_time)
        if end_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at <= end_time)

        row = (await self.session.execute(stmt)).one()
        total = int(row.total_executions or 0)
        completed = int(row.completed_count or 0)
        failed = int(row.failed_count or 0)
        timeout = int(row.timeout_count or 0)
        incident_aff = int(row.incident_affected_count or 0)

        success_rate = (completed / total * 100.0) if total > 0 else 0.0
        error_rate = ((failed + timeout) / total * 100.0) if total > 0 else 0.0

        # Compute P50 and P95 durations
        dur_stmt = select(WorkflowExecutionModel.duration_ms).where(
            WorkflowExecutionModel.workflow_definition_id == definition_id
        )
        if start_time:
            dur_stmt = dur_stmt.where(WorkflowExecutionModel.started_at >= start_time)
        if end_time:
            dur_stmt = dur_stmt.where(WorkflowExecutionModel.started_at <= end_time)

        dur_rows = (await self.session.execute(dur_stmt)).scalars().all()
        import numpy as np

        if dur_rows:
            p50_dur = float(np.percentile(dur_rows, 50))
            p95_dur = float(np.percentile(dur_rows, 95))
            min_dur = float(row.min_duration or 0.0)
            max_dur = float(row.max_duration or 0.0)
            mean_dur = float(row.mean_duration or 0.0)
        else:
            p50_dur = p95_dur = min_dur = max_dur = mean_dur = 0.0

        return {
            "workflow_definition_id": definition_id,
            "total_executions": total,
            "completed_count": completed,
            "failed_count": failed,
            "timeout_count": timeout,
            "success_rate_percent": round(success_rate, 2),
            "error_rate_percent": round(error_rate, 2),
            "mean_duration_ms": round(mean_dur, 2),
            "median_p50_duration_ms": round(p50_dur, 2),
            "p95_duration_ms": round(p95_dur, 2),
            "min_duration_ms": round(min_dur, 2),
            "max_duration_ms": round(max_dur, 2),
            "incident_affected_count": incident_aff,
        }

    # --- Workflow Executions ---

    async def get_execution(self, execution_id: str) -> WorkflowExecutionModel | None:
        """Fetch workflow execution trace by ID."""
        stmt = select(WorkflowExecutionModel).where(WorkflowExecutionModel.id == execution_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_execution(
        self, data: dict[str, Any] | WorkflowExecutionModel
    ) -> WorkflowExecutionModel:
        """Persist a single workflow execution record."""
        if isinstance(data, WorkflowExecutionModel):
            self.session.add(data)
            await self.session.commit()
            await self.session.refresh(data)
            return data
        else:
            execution = WorkflowExecutionModel(**data)
            self.session.add(execution)
            await self.session.commit()
            await self.session.refresh(execution)
            return execution

    async def bulk_create_executions(self, records: list[dict[str, Any]]) -> int:
        """Bulk insert executions ignoring existing IDs for idempotency."""
        if not records:
            return 0
        objects = [WorkflowExecutionModel(**r) for r in records]
        for obj in objects:
            await self.session.merge(obj)
        await self.session.commit()
        return len(records)

    async def list_executions(
        self,
        workflow_definition_id: str | None = None,
        status: str | None = None,
        incident_id: str | None = None,
        is_incident_affected: bool | None = None,
        min_duration_ms: float | None = None,
        max_duration_ms: float | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowExecutionModel]:
        """List workflow executions matching filters with pagination."""
        stmt = select(WorkflowExecutionModel).order_by(WorkflowExecutionModel.started_at.desc())

        if workflow_definition_id:
            stmt = stmt.where(
                WorkflowExecutionModel.workflow_definition_id == workflow_definition_id
            )
        if status:
            stmt = stmt.where(WorkflowExecutionModel.status == status)
        if incident_id:
            stmt = stmt.where(WorkflowExecutionModel.incident_id == incident_id)
        if is_incident_affected is not None:
            stmt = stmt.where(WorkflowExecutionModel.is_incident_affected == is_incident_affected)
        if min_duration_ms is not None:
            stmt = stmt.where(WorkflowExecutionModel.duration_ms >= min_duration_ms)
        if max_duration_ms is not None:
            stmt = stmt.where(WorkflowExecutionModel.duration_ms <= max_duration_ms)
        if start_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at >= start_time)
        if end_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at <= end_time)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_executions(
        self,
        workflow_definition_id: str | None = None,
        status: str | None = None,
        incident_id: str | None = None,
        is_incident_affected: bool | None = None,
        min_duration_ms: float | None = None,
        max_duration_ms: float | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Count workflow executions matching filters."""
        stmt = select(func.count(WorkflowExecutionModel.id))
        if workflow_definition_id:
            stmt = stmt.where(
                WorkflowExecutionModel.workflow_definition_id == workflow_definition_id
            )
        if status:
            stmt = stmt.where(WorkflowExecutionModel.status == status)
        if incident_id:
            stmt = stmt.where(WorkflowExecutionModel.incident_id == incident_id)
        if is_incident_affected is not None:
            stmt = stmt.where(WorkflowExecutionModel.is_incident_affected == is_incident_affected)
        if min_duration_ms is not None:
            stmt = stmt.where(WorkflowExecutionModel.duration_ms >= min_duration_ms)
        if max_duration_ms is not None:
            stmt = stmt.where(WorkflowExecutionModel.duration_ms <= max_duration_ms)
        if start_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at >= start_time)
        if end_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at <= end_time)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)
