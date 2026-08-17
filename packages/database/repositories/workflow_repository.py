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
        # Using merge or add_all
        for obj in objects:
            await self.session.merge(obj)
        await self.session.commit()
        return len(records)

    async def list_executions(
        self,
        status: str | None = None,
        incident_id: str | None = None,
        is_incident_affected: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowExecutionModel]:
        """List workflow executions matching filters with pagination."""
        stmt = select(WorkflowExecutionModel).order_by(WorkflowExecutionModel.started_at.desc())

        if status:
            stmt = stmt.where(WorkflowExecutionModel.status == status)
        if incident_id:
            stmt = stmt.where(WorkflowExecutionModel.incident_id == incident_id)
        if is_incident_affected is not None:
            stmt = stmt.where(WorkflowExecutionModel.is_incident_affected == is_incident_affected)
        if start_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at >= start_time)
        if end_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at <= end_time)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_executions(
        self,
        status: str | None = None,
        incident_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Count workflow executions matching filters."""
        stmt = select(func.count(WorkflowExecutionModel.id))
        if status:
            stmt = stmt.where(WorkflowExecutionModel.status == status)
        if incident_id:
            stmt = stmt.where(WorkflowExecutionModel.incident_id == incident_id)
        if start_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at >= start_time)
        if end_time:
            stmt = stmt.where(WorkflowExecutionModel.started_at <= end_time)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)
