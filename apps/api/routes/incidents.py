"""FastAPI routes for querying ground-truth incidents and affected workflow executions."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
)
from apps.api.exceptions import EntityNotFoundException
from packages.database.repositories.incident_repository import IncidentRepository
from packages.database.session import get_db_session
from packages.domain.security import TenantContext

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents & Ground Truth"])


class IncidentResponse(BaseModel):
    """Ground truth incident response schema."""

    id: str
    scenario_type: str
    severity: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    affected_services: list[Any]
    ground_truth_root_cause: str
    description: str
    parameters: dict[str, Any]
    metadata: dict[str, Any]


class IncidentTraceResponse(BaseModel):
    """Workflow execution affected by an incident."""

    id: str
    workflow_definition_id: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float
    status: str
    retry_count: int
    error_count: int
    failure_reason: str | None
    incident_id: str | None
    is_incident_affected: bool
    metadata: dict[str, Any]


@router.get(
    "",
    response_model=list[IncidentResponse],
    summary="List Ground-Truth Incidents",
)
async def list_incidents(
    scenario_type: str | None = Query(None, description="Filter by scenario type"),
    severity: str | None = Query(
        None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"
    ),
    start_time: datetime | None = Query(None, description="Filter incidents active after UTC"),
    end_time: datetime | None = Query(None, description="Filter incidents active before UTC"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[IncidentResponse]:
    """Retrieve list of recorded ground-truth chaos incidents with optional filtering."""
    repo = IncidentRepository(session)
    incidents = await repo.list_incidents(
        start_time=start_time,
        end_time=end_time,
        scenario_type=scenario_type,
        severity=severity,
        limit=limit,
        offset=offset,
        tenant_id=ctx.tenant_id,
    )
    return [
        IncidentResponse(
            id=inc.id,
            scenario_type=inc.scenario_type,
            severity=inc.severity,
            started_at=inc.started_at,
            ended_at=inc.ended_at,
            duration_seconds=inc.duration_seconds,
            affected_services=inc.affected_services,
            ground_truth_root_cause=inc.ground_truth_root_cause,
            description=inc.description,
            parameters=inc.parameters,
            metadata=inc.metadata_,
        )
        for inc in incidents
    ]


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Get Incident Details",
)
async def get_incident(
    incident_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> IncidentResponse:
    """Retrieve ground-truth incident details by ID."""
    repo = IncidentRepository(session)
    incident = await repo.get_incident(incident_id, tenant_id=ctx.tenant_id)
    if not incident:
        raise EntityNotFoundException("Incident", incident_id)
    return IncidentResponse(
        id=incident.id,
        scenario_type=incident.scenario_type,
        severity=incident.severity,
        started_at=incident.started_at,
        ended_at=incident.ended_at,
        duration_seconds=incident.duration_seconds,
        affected_services=incident.affected_services,
        ground_truth_root_cause=incident.ground_truth_root_cause,
        description=incident.description,
        parameters=incident.parameters,
        metadata=incident.metadata_,
    )


@router.get(
    "/{incident_id}/traces",
    response_model=list[IncidentTraceResponse],
    summary="Get Traces Affected by Incident",
)
async def get_incident_traces(
    incident_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[IncidentTraceResponse]:
    """Retrieve all workflow executions associated with or affected by an incident."""
    repo = IncidentRepository(session)
    traces = await repo.get_incident_traces(
        incident_id, limit=limit, offset=offset, tenant_id=ctx.tenant_id
    )
    return [
        IncidentTraceResponse(
            id=t.id,
            workflow_definition_id=t.workflow_definition_id,
            started_at=t.started_at,
            completed_at=t.completed_at,
            duration_ms=t.duration_ms,
            status=t.status,
            retry_count=t.retry_count,
            error_count=t.error_count,
            failure_reason=t.failure_reason,
            incident_id=t.incident_id,
            is_incident_affected=t.is_incident_affected,
            metadata=t.metadata_,
        )
        for t in traces
    ]

