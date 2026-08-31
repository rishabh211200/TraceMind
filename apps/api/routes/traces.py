"""FastAPI routes for querying workflow execution traces and hierarchical span DAGs."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
)
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.repositories.workflow_repository import WorkflowRepository
from packages.database.session import get_db_session
from packages.domain.security import TenantContext

router = APIRouter(prefix="/api/v1/traces", tags=["Traces & Executions"])


class ExecutionSummaryResponse(BaseModel):
    """Workflow execution summary response schema."""

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


class TraceEventResponse(BaseModel):
    """Individual span event response schema."""

    event_id: str
    timestamp: datetime
    execution_id: str
    workflow_id: str
    service: str
    operation: str
    event_type: str
    status: str
    latency_ms: float
    parent_event_id: str | None
    correlation_id: str | None
    metadata: dict[str, Any]


@router.get(
    "",
    response_model=list[ExecutionSummaryResponse],
    summary="List Workflow Execution Traces",
)
async def list_traces(
    status: str | None = Query(None, description="Filter by status (COMPLETED, FAILED)"),
    incident_id: str | None = Query(None, description="Filter by incident ID"),
    is_incident_affected: bool | None = Query(
        None, description="Filter by incident affected status"
    ),
    start_time: datetime | None = Query(None, description="Filter starting at UTC time"),
    end_time: datetime | None = Query(None, description="Filter ending at UTC time"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[ExecutionSummaryResponse]:
    """Retrieve paginated list of workflow executions matching filter criteria."""
    repo = WorkflowRepository(session)
    executions = await repo.list_executions(
        status=status,
        incident_id=incident_id,
        is_incident_affected=is_incident_affected,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
        tenant_id=ctx.tenant_id,
    )
    return [
        ExecutionSummaryResponse(
            id=e.id,
            workflow_definition_id=e.workflow_definition_id,
            started_at=e.started_at,
            completed_at=e.completed_at,
            duration_ms=e.duration_ms,
            status=e.status,
            retry_count=e.retry_count,
            error_count=e.error_count,
            failure_reason=e.failure_reason,
            incident_id=e.incident_id,
            is_incident_affected=e.is_incident_affected,
            metadata=e.metadata_,
        )
        for e in executions
    ]


@router.get(
    "/{trace_id}",
    response_model=ExecutionSummaryResponse,
    summary="Get Workflow Execution Trace Summary",
)
async def get_trace(
    trace_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ExecutionSummaryResponse:
    """Retrieve execution trace summary by ID."""
    repo = WorkflowRepository(session)
    execution = await repo.get_execution(trace_id, tenant_id=ctx.tenant_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution trace '{trace_id}' not found",
        )
    return ExecutionSummaryResponse(
        id=execution.id,
        workflow_definition_id=execution.workflow_definition_id,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=execution.duration_ms,
        status=execution.status,
        retry_count=execution.retry_count,
        error_count=execution.error_count,
        failure_reason=execution.failure_reason,
        incident_id=execution.incident_id,
        is_incident_affected=execution.is_incident_affected,
        metadata=execution.metadata_,
    )


@router.get(
    "/{trace_id}/events",
    response_model=list[TraceEventResponse],
    summary="Get Chronological Trace Events",
)
async def get_trace_events(
    trace_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[TraceEventResponse]:
    """Retrieve all span events for a trace ordered chronologically by timestamp."""
    repo = TraceEventRepository(session)
    events = await repo.get_trace_events(trace_id, tenant_id=ctx.tenant_id)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for trace '{trace_id}'",
        )
    return [
        TraceEventResponse(
            event_id=ev.event_id,
            timestamp=ev.timestamp,
            execution_id=ev.execution_id,
            workflow_id=ev.workflow_id,
            service=ev.service,
            operation=ev.operation,
            event_type=ev.event_type,
            status=ev.status,
            latency_ms=ev.latency_ms,
            parent_event_id=ev.parent_event_id,
            correlation_id=ev.correlation_id,
            metadata=ev.metadata_,
        )
        for ev in events
    ]


@router.get(
    "/{trace_id}/tree",
    response_model=dict[str, Any],
    summary="Get Reconstructed Parent-Child Trace Tree DAG",
)
async def get_trace_tree(
    trace_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Reconstruct and retrieve the hierarchical span DAG tree for an execution trace."""
    repo = TraceEventRepository(session)
    tree = await repo.get_trace_tree(trace_id, tenant_id=ctx.tenant_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not reconstruct tree for trace '{trace_id}'",
        )
    return tree

