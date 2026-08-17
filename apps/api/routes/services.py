"""FastAPI routes for service discovery, latency distributions, and health telemetry."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.repositories.service_repository import ServiceRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.session import get_db_session

router = APIRouter(prefix="/api/v1/services", tags=["Services & Telemetry"])


class ServiceResponse(BaseModel):
    """Registered service profile schema."""

    name: str
    service_type: str
    capacity: int
    baseline_latency_ms: float
    baseline_failure_rate: float
    timeout_ms: float
    max_retries: int
    retry_backoff_ms: float
    dependencies: list[Any]
    metadata: dict[str, Any]


class ServiceLatencyStatsResponse(BaseModel):
    """Database-side latency percentile distribution response schema."""

    service: str
    count: int
    mean_latency_ms: float
    median_p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float


class ServiceHealthResponse(BaseModel):
    """Service operational reliability and error rate summary schema."""

    service: str
    total_events: int
    failure_count: int
    error_rate_percent: float
    retry_count: int
    retry_rate_percent: float
    timeout_count: int
    timeout_rate_percent: float
    latency: ServiceLatencyStatsResponse


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
    return [
        ServiceResponse(
            name=s.name,
            service_type=s.service_type,
            capacity=s.capacity,
            baseline_latency_ms=s.baseline_latency_ms,
            baseline_failure_rate=s.baseline_failure_rate,
            timeout_ms=s.timeout_ms,
            max_retries=s.max_retries,
            retry_backoff_ms=s.retry_backoff_ms,
            dependencies=s.dependencies,
            metadata=s.metadata_,
        )
        for s in services
    ]


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
    "/{service}/latency",
    response_model=ServiceLatencyStatsResponse,
    summary="Get Service Latency Percentiles (P50/P90/P95/P99)",
)
async def get_service_latency(
    service: str,
    start_time: datetime | None = Query(None, description="Start timestamp in UTC"),
    end_time: datetime | None = Query(None, description="End timestamp in UTC"),
    session: AsyncSession = Depends(get_db_session),
) -> ServiceLatencyStatsResponse:
    """Compute database-side P50, P90, P95, P99, Mean, Min, and Max latency for a service."""
    repo = TraceEventRepository(session)
    stats = await repo.get_service_latency_stats(
        service=service, start_time=start_time, end_time=end_time
    )
    return ServiceLatencyStatsResponse(**stats)


@router.get(
    "/{service}/health",
    response_model=ServiceHealthResponse,
    summary="Get Service Operational Health & Error Rates",
)
async def get_service_health(
    service: str,
    start_time: datetime | None = Query(None, description="Start timestamp in UTC"),
    end_time: datetime | None = Query(None, description="End timestamp in UTC"),
    session: AsyncSession = Depends(get_db_session),
) -> ServiceHealthResponse:
    """Retrieve call volume, error rate, retry frequency, and timeout count for a service."""
    repo = TraceEventRepository(session)
    health = await repo.get_service_health(
        service=service, start_time=start_time, end_time=end_time
    )
    return ServiceHealthResponse(**health)
