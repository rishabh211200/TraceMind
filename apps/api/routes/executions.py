"""FastAPI routes for querying workflow executions, trace events, and DAG trees."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
)
from apps.api.exceptions import EntityNotFoundException
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.execution import (
    ExecutionListResponse,
    ExecutionSummaryResponse,
    TraceEventResponse,
    TraceTreeNodeResponse,
)
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.repositories.workflow_repository import WorkflowRepository
from packages.database.session import get_db_session
from packages.domain.security import TenantContext

router = APIRouter(prefix="/api/v1/executions", tags=["Executions & Traces"])


@router.get(
    "",
    response_model=ExecutionListResponse,
    summary="List Workflow Executions",
)
async def list_executions(
    workflow_definition_id: str | None = Query(
        None, description="Filter by workflow definition ID"
    ),
    status: str | None = Query(
        None, description="Filter by execution status (COMPLETED, FAILED, TIMEOUT)"
    ),
    incident_id: str | None = Query(None, description="Filter by incident ID"),
    is_incident_affected: bool | None = Query(
        None, description="Filter by incident affected status"
    ),
    min_duration_ms: float | None = Query(
        None, ge=0.0, description="Minimum duration filter in ms"
    ),
    max_duration_ms: float | None = Query(
        None, ge=0.0, description="Maximum duration filter in ms"
    ),
    start_time: datetime | None = Query(None, description="Filter starting at UTC time"),
    end_time: datetime | None = Query(None, description="Filter ending at UTC time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum records per page"),
    offset: int = Query(0, ge=0, description="Pagination offset index"),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ExecutionListResponse:
    """Retrieve paginated list of workflow executions matching filter criteria."""
    repo = WorkflowRepository(session)
    executions = await repo.list_executions(
        workflow_definition_id=workflow_definition_id,
        status=status,
        incident_id=incident_id,
        is_incident_affected=is_incident_affected,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
        tenant_id=ctx.tenant_id,
    )
    total = await repo.count_executions(
        workflow_definition_id=workflow_definition_id,
        status=status,
        incident_id=incident_id,
        is_incident_affected=is_incident_affected,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        start_time=start_time,
        end_time=end_time,
        tenant_id=ctx.tenant_id,
    )

    items = [
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
            metadata=e.metadata_ or {},
        )
        for e in executions
    ]
    return ExecutionListResponse(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(items)) < total,
        ),
    )


@router.get(
    "/{execution_id}",
    response_model=ExecutionSummaryResponse,
    summary="Get Execution by ID",
)
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ExecutionSummaryResponse:
    """Retrieve single execution metadata by unique execution ID."""
    repo = WorkflowRepository(session)
    execution = await repo.get_execution(execution_id, tenant_id=ctx.tenant_id)
    if not execution:
        raise EntityNotFoundException("WorkflowExecution", execution_id)

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
        metadata=execution.metadata_ or {},
    )


@router.get(
    "/{execution_id}/events",
    response_model=list[TraceEventResponse],
    summary="Get Execution Trace Events",
)
async def get_execution_events(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[TraceEventResponse]:
    """Retrieve all span events for a workflow execution in chronological order."""
    wf_repo = WorkflowRepository(session)
    execution = await wf_repo.get_execution(execution_id, tenant_id=ctx.tenant_id)
    if not execution:
        raise EntityNotFoundException("WorkflowExecution", execution_id)

    event_repo = TraceEventRepository(session)
    events = await event_repo.get_trace_events(execution_id, tenant_id=ctx.tenant_id)
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
            metadata=ev.metadata_ or {},
        )
        for ev in events
    ]


@router.get(
    "/{execution_id}/tree",
    response_model=TraceTreeNodeResponse,
    summary="Get Reconstructed Trace Tree DAG",
)
async def get_execution_trace_tree(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> TraceTreeNodeResponse:
    """Reconstruct and return the full hierarchical DAG span tree for an execution."""
    wf_repo = WorkflowRepository(session)
    execution = await wf_repo.get_execution(execution_id, tenant_id=ctx.tenant_id)
    if not execution:
        raise EntityNotFoundException("WorkflowExecution", execution_id)

    event_repo = TraceEventRepository(session)
    tree = await event_repo.get_trace_tree(execution_id, tenant_id=ctx.tenant_id)
    if not tree:
        raise EntityNotFoundException("TraceTree", execution_id)

    return TraceTreeNodeResponse(**tree)

