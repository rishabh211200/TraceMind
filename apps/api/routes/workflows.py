"""FastAPI routes for workflow topology management, DAG validation, executions, and statistics."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
    require_permission,
)
from apps.api.exceptions import ConflictException, EntityNotFoundException, ValidationException
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.execution import ExecutionListResponse, ExecutionSummaryResponse
from apps.api.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionResponse,
    WorkflowDefinitionUpdate,
    WorkflowStatsResponse,
)
from packages.database.repositories.workflow_repository import WorkflowRepository
from packages.database.session import get_db_session
from packages.domain.security import Permission, TenantContext

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


def _collect_node_ids(nodes: list[dict[str, Any]]) -> set[str]:
    node_ids = set()
    for node in nodes:
        nid = node.get("id")
        if not nid:
            raise ValidationException("Every workflow node must have a non-empty 'id'.")
        if nid in node_ids:
            raise ValidationException(
                f"Duplicate node ID detected: '{nid}'. Node IDs must be unique."
            )
        node_ids.add(nid)
    return node_ids


def _build_adj_list(edges: list[dict[str, Any]], node_ids: set[str]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for edge in edges:
        from_node = edge.get("from_node")
        to_node = edge.get("to_node")
        if not from_node or not to_node:
            raise ValidationException("Every edge must specify 'from_node' and 'to_node'.")
        if from_node not in node_ids:
            raise ValidationException(f"Edge references non-existent source node '{from_node}'.")
        if to_node not in node_ids:
            raise ValidationException(f"Edge references non-existent target node '{to_node}'.")
        if from_node == to_node:
            raise ValidationException(
                f"Self-loop detected on node '{from_node}'. Workflows must be acyclic."
            )
        adj[from_node].append(to_node)
    return adj


def _detect_dag_cycles(node_ids: set[str], adj: dict[str, list[str]]) -> None:
    color: dict[str, int] = dict.fromkeys(node_ids, 0)

    def dfs(u: str) -> None:
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                raise ValidationException(
                    f"Cycle detected in workflow DAG involving transition '{u}' -> '{v}'."
                )
            if color[v] == 0:
                dfs(v)
        color[u] = 2

    for nid in node_ids:
        if color[nid] == 0:
            dfs(nid)


def validate_workflow_dag(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Validate that nodes and edges form a valid Directed Acyclic Graph (DAG)."""
    node_ids = _collect_node_ids(nodes)
    adj = _build_adj_list(edges, node_ids)
    _detect_dag_cycles(node_ids, adj)


def _to_workflow_response(wf) -> WorkflowDefinitionResponse:
    nodes = wf.nodes if isinstance(wf.nodes, list) else []
    edges = wf.edges if isinstance(wf.edges, list) else []
    return WorkflowDefinitionResponse(
        id=wf.id,
        name=wf.name,
        version=wf.version,
        description=wf.description,
        nodes=nodes,
        edges=edges,
        node_count=len(nodes),
        edge_count=len(edges),
        metadata=wf.metadata_ or {},
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.get(
    "",
    response_model=list[WorkflowDefinitionResponse],
    summary="List Workflow Definitions",
)
async def list_workflows(
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[WorkflowDefinitionResponse]:
    """List all registered workflow DAG topologies."""
    repo = WorkflowRepository(session)
    definitions = await repo.list_definitions(tenant_id=ctx.tenant_id)
    return [_to_workflow_response(wf) for wf in definitions]


@router.post(
    "",
    response_model=WorkflowDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Workflow Definition",
    dependencies=[Depends(require_permission(Permission.WORKFLOWS_WRITE))],
)
async def create_workflow(
    payload: WorkflowDefinitionCreate,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkflowDefinitionResponse:
    """Register a new workflow DAG definition with validation against cycles and invalid references."""
    repo = WorkflowRepository(session)
    existing = await repo.get_definition(payload.id, tenant_id=ctx.tenant_id)
    if existing:
        raise ConflictException(f"Workflow definition with ID '{payload.id}' already exists.")

    nodes_dict = [n.model_dump() for n in payload.nodes]
    edges_dict = [e.model_dump() for e in payload.edges]

    validate_workflow_dag(nodes_dict, edges_dict)

    data = {
        "id": payload.id,
        "tenant_id": ctx.tenant_id,
        "name": payload.name,
        "version": payload.version,
        "description": payload.description,
        "nodes": nodes_dict,
        "edges": edges_dict,
        "metadata_": payload.metadata,
    }
    wf = await repo.upsert_definition(data, tenant_id=ctx.tenant_id)
    return _to_workflow_response(wf)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDefinitionResponse,
    summary="Get Workflow Definition",
)
async def get_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkflowDefinitionResponse:
    """Retrieve details and DAG topology of a specific workflow definition."""
    repo = WorkflowRepository(session)
    wf = await repo.get_definition(workflow_id, tenant_id=ctx.tenant_id)
    if not wf:
        raise EntityNotFoundException("WorkflowDefinition", workflow_id)
    return _to_workflow_response(wf)


@router.put(
    "/{workflow_id}",
    response_model=WorkflowDefinitionResponse,
    summary="Update Workflow Definition",
    dependencies=[Depends(require_permission(Permission.WORKFLOWS_WRITE))],
)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowDefinitionUpdate,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkflowDefinitionResponse:
    """Update workflow definition metadata, nodes, and edges with DAG validation."""
    repo = WorkflowRepository(session)
    wf = await repo.get_definition(workflow_id, tenant_id=ctx.tenant_id)
    if not wf:
        raise EntityNotFoundException("WorkflowDefinition", workflow_id)

    nodes_dict = (
        [n.model_dump() for n in payload.nodes]
        if payload.nodes is not None
        else (wf.nodes if isinstance(wf.nodes, list) else [])
    )
    edges_dict = (
        [e.model_dump() for e in payload.edges]
        if payload.edges is not None
        else (wf.edges if isinstance(wf.edges, list) else [])
    )

    if payload.nodes is not None or payload.edges is not None:
        validate_workflow_dag(nodes_dict, edges_dict)

    update_data: dict[str, Any] = {"id": workflow_id, "tenant_id": ctx.tenant_id}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.version is not None:
        update_data["version"] = payload.version
    if payload.description is not None:
        update_data["description"] = payload.description
    if payload.nodes is not None:
        update_data["nodes"] = nodes_dict
    if payload.edges is not None:
        update_data["edges"] = edges_dict
    if payload.metadata is not None:
        update_data["metadata_"] = payload.metadata

    updated_wf = await repo.upsert_definition(update_data, tenant_id=ctx.tenant_id)
    return _to_workflow_response(updated_wf)


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Workflow Definition",
    dependencies=[Depends(require_permission(Permission.WORKFLOWS_WRITE))],
)
async def delete_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> None:
    """Safely delete workflow definition. Rejects deletion if executions are associated with it."""
    repo = WorkflowRepository(session)
    wf = await repo.get_definition(workflow_id, tenant_id=ctx.tenant_id)
    if not wf:
        raise EntityNotFoundException("WorkflowDefinition", workflow_id)
    await repo.delete_definition(workflow_id, tenant_id=ctx.tenant_id)


@router.get(
    "/{workflow_id}/executions",
    response_model=ExecutionListResponse,
    summary="List Executions for Workflow",
)
async def list_workflow_executions(
    workflow_id: str,
    status: str | None = Query(None, description="Filter by status (COMPLETED, FAILED, TIMEOUT)"),
    incident_id: str | None = Query(None, description="Filter by incident ID"),
    is_incident_affected: bool | None = Query(
        None, description="Filter by incident affected status"
    ),
    min_duration_ms: float | None = Query(None, ge=0.0, description="Minimum duration filter"),
    max_duration_ms: float | None = Query(None, ge=0.0, description="Maximum duration filter"),
    start_time: datetime | None = Query(None, description="Filter starting at UTC time"),
    end_time: datetime | None = Query(None, description="Filter ending at UTC time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum records per page"),
    offset: int = Query(0, ge=0, description="Pagination offset index"),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ExecutionListResponse:
    """Retrieve paginated executions belonging to a specific workflow definition."""
    repo = WorkflowRepository(session)
    wf = await repo.get_definition(workflow_id, tenant_id=ctx.tenant_id)
    if not wf:
        raise EntityNotFoundException("WorkflowDefinition", workflow_id)

    executions = await repo.list_executions(
        workflow_definition_id=workflow_id,
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
        workflow_definition_id=workflow_id,
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
    "/{workflow_id}/stats",
    response_model=WorkflowStatsResponse,
    summary="Get Workflow Execution Statistics",
)
async def get_workflow_stats(
    workflow_id: str,
    start_time: datetime | None = Query(None, description="Start timestamp window"),
    end_time: datetime | None = Query(None, description="End timestamp window"),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> WorkflowStatsResponse:
    """Retrieve execution metrics, success/error rates, and duration percentiles for a workflow."""
    repo = WorkflowRepository(session)
    wf = await repo.get_definition(workflow_id, tenant_id=ctx.tenant_id)
    if not wf:
        raise EntityNotFoundException("WorkflowDefinition", workflow_id)

    stats = await repo.get_workflow_stats(
        definition_id=workflow_id,
        start_time=start_time,
        end_time=end_time,
        tenant_id=ctx.tenant_id,
    )
    return WorkflowStatsResponse(**stats)
