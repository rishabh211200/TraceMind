"""Incident repository for ground-truth incidents and affected execution queries."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.incident import IncidentModel
from packages.database.models.workflow import WorkflowExecutionModel


class IncidentRepository:
    """Async repository for IncidentModel entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_incident(
        self, incident_id: str, tenant_id: str | None = None
    ) -> IncidentModel | None:
        """Fetch ground-truth incident by ID."""
        stmt = select(IncidentModel).where(IncidentModel.id == incident_id)
        if tenant_id:
            stmt = stmt.where(IncidentModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_incident(
        self, data: dict[str, Any] | IncidentModel, tenant_id: str = "tenant_system"
    ) -> IncidentModel:
        """Insert or update incident record."""
        if isinstance(data, IncidentModel):
            if not getattr(data, "tenant_id", None):
                data.tenant_id = tenant_id
            incident = await self.session.merge(data)
            await self.session.commit()
            return incident

        if "tenant_id" not in data:
            data["tenant_id"] = tenant_id
        inc_id = data["id"]
        existing = await self.get_incident(inc_id, tenant_id=data["tenant_id"])
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            new_incident = IncidentModel(**data)
            self.session.add(new_incident)
            await self.session.commit()
            await self.session.refresh(new_incident)
            return new_incident

    async def bulk_create_incidents(
        self, records: list[dict[str, Any]], tenant_id: str = "tenant_system"
    ) -> int:
        """Bulk insert incidents with idempotency."""
        if not records:
            return 0
        for r in records:
            if "tenant_id" not in r:
                r["tenant_id"] = tenant_id
        objects = [IncidentModel(**r) for r in records]
        for obj in objects:
            await self.session.merge(obj)
        await self.session.commit()
        return len(records)

    async def list_incidents(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        scenario_type: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[IncidentModel]:
        """List ground-truth incidents with filtering and pagination."""
        stmt = select(IncidentModel).order_by(IncidentModel.started_at.desc())

        if tenant_id:
            stmt = stmt.where(IncidentModel.tenant_id == tenant_id)
        if scenario_type:
            stmt = stmt.where(IncidentModel.scenario_type == scenario_type)
        if severity:
            stmt = stmt.where(IncidentModel.severity == severity)
        if start_time:
            stmt = stmt.where(IncidentModel.started_at >= start_time)
        if end_time:
            stmt = stmt.where(IncidentModel.ended_at <= end_time)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_incident_traces(
        self, incident_id: str, limit: int = 100, offset: int = 0, tenant_id: str | None = None
    ) -> list[WorkflowExecutionModel]:
        """Retrieve all workflow executions associated with an incident."""
        incident = await self.get_incident(incident_id, tenant_id=tenant_id)
        stmt = select(WorkflowExecutionModel).order_by(WorkflowExecutionModel.started_at.asc())

        if tenant_id:
            stmt = stmt.where(WorkflowExecutionModel.tenant_id == tenant_id)

        if incident:
            # Match directly by tagged incident_id or by time window overlap
            stmt = stmt.where(
                (WorkflowExecutionModel.incident_id == incident_id)
                | (
                    (WorkflowExecutionModel.started_at >= incident.started_at)
                    & (WorkflowExecutionModel.started_at <= incident.ended_at)
                )
            )
        else:
            stmt = stmt.where(WorkflowExecutionModel.incident_id == incident_id)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
