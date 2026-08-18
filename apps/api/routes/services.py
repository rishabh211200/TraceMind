"""FastAPI routes for service discovery, topology graph, latency distributions, and health telemetry."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.exceptions import EntityNotFoundException
from apps.api.schemas.service import (
    ServiceHealthResponse,
    ServiceLatencyStatsResponse,
    ServiceResponse,
    ServiceTopologyResponse,
    ServiceUpdate,
)
from packages.database.repositories.service_repository import ServiceRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.session import get_db_session

router = APIRouter(prefix="/api/v1/services", tags=["Services & Telemetry"])


def _to_service_response(s) -> ServiceResponse:
    return ServiceResponse(
        name=s.name,
        service_type=s.service_type,
        capacity=s.capacity,
        baseline_latency_ms=s.baseline_latency_ms,
        baseline_failure_rate=s.baseline_failure_rate,
        timeout_ms=s.timeout_ms,
        max_retries=s.max_retries,
        retry_backoff_ms=s.retry_backoff_ms,
        dependencies=s.dependencies if isinstance(s.dependencies, list) else [],
        metadata=s.metadata_ or {},
    )


@router.get(
    "",
    response_model=list[ServiceResponse],
    summary="List Registered Services",
)
async def list_services(
    session: AsyncSession = Depends(get_db_session),
) -> list[ServiceResponse]:
    """Retrieve all registered business microservices and infrastructure components."""
    repo = ServiceRepository(session)
    services = await repo.list_services()
    return [_to_service_response(s) for s in services]


@router.get(
    "/topology",
    response_model=ServiceTopologyResponse,
    summary="Get Service Graph Topology",
)
async def get_service_topology(
    session: AsyncSession = Depends(get_db_session),
) -> ServiceTopologyResponse:
    """Retrieve full system dependency graph with nodes and directed dependency edges."""
    repo = ServiceRepository(session)
    topology = await repo.get_service_topology()
    return ServiceTopologyResponse(**topology)


@router.get(
    "/telemetry/summary",
    response_model=list[ServiceHealthResponse],
    summary="Get System-Wide Service Telemetry Summary",
)
async def get_telemetry_summary(
    start_time: datetime | None = Query(None, description="Start timestamp in UTC"),
    end_time: datetime | None = Query(None, description="End timestamp in UTC"),
    session: AsyncSession = Depends(get_db_session),
) -> list[ServiceHealthResponse]:
    """Calculate and aggregate operational health and latency percentiles across all services."""
    repo = TraceEventRepository(session)
    summaries = await repo.get_service_telemetry_summary(start_time=start_time, end_time=end_time)
    return [ServiceHealthResponse(**s) for s in summaries]


@router.get(
    "/{service_name}",
    response_model=ServiceResponse,
    summary="Get Service Profile",
)
async def get_service(
    service_name: str,
    session: AsyncSession = Depends(get_db_session),
) -> ServiceResponse:
    """Retrieve details, baseline performance profile, and dependencies for a service."""
    repo = ServiceRepository(session)
    service = await repo.get_service(service_name)
    if not service:
        raise EntityNotFoundException("Service", service_name)
    return _to_service_response(service)


@router.put(
    "/{service_name}",
    response_model=ServiceResponse,
    summary="Update Service Baseline Profile",
)
async def update_service(
    service_name: str,
    payload: ServiceUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ServiceResponse:
    """Update baseline parameters (capacity, latency, failure rate, timeout, retries) for a service."""
    repo = ServiceRepository(session)
    existing = await repo.get_service(service_name)
    if not existing:
        raise EntityNotFoundException("Service", service_name)

    updates = payload.model_dump(exclude_unset=True)
    if "metadata" in updates:
        updates["metadata_"] = updates.pop("metadata")

    updated = await repo.update_service(service_name, updates)
    return _to_service_response(updated)


@router.get(
    "/{service_name}/latency",
    response_model=ServiceLatencyStatsResponse,
    summary="Get Service Latency Percentiles (P50/P90/P95/P99)",
)
async def get_service_latency(
    service_name: str,
    start_time: datetime | None = Query(None, description="Start timestamp in UTC"),
    end_time: datetime | None = Query(None, description="End timestamp in UTC"),
    session: AsyncSession = Depends(get_db_session),
) -> ServiceLatencyStatsResponse:
    """Compute database-side P50, P90, P95, P99, Mean, Min, and Max latency for a service."""
    repo = TraceEventRepository(session)
    stats = await repo.get_service_latency_stats(
        service=service_name, start_time=start_time, end_time=end_time
    )
    return ServiceLatencyStatsResponse(**stats)


@router.get(
    "/{service_name}/health",
    response_model=ServiceHealthResponse,
    summary="Get Service Operational Health & Error Rates",
)
async def get_service_health(
    service_name: str,
    start_time: datetime | None = Query(None, description="Start timestamp in UTC"),
    end_time: datetime | None = Query(None, description="End timestamp in UTC"),
    session: AsyncSession = Depends(get_db_session),
) -> ServiceHealthResponse:
    """Retrieve call volume, error rate, retry frequency, and timeout count for a service."""
    repo = TraceEventRepository(session)
    health = await repo.get_service_health(
        service=service_name, start_time=start_time, end_time=end_time
    )
    return ServiceHealthResponse(**health)
