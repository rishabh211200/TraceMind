"""FastAPI router for unsupervised and statistical anomaly detection."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
    require_permission,
)
from apps.api.exceptions import EntityNotFoundException
from apps.api.schemas.anomaly import (
    AnomalyDetectRequest,
    AnomalyDetectResponse,
    AnomalyFitRequest,
    AnomalyFitResponse,
    AnomalyResponse,
    AnomalyStatsResponse,
)
from apps.api.schemas.common import PaginatedResponse, PaginationMeta
from apps.ml.anomalies.registry import AnomalyDetectorRegistry
from packages.database.repositories.anomaly_repository import AnomalyRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.session import get_db_session
from packages.domain.security import Permission, TenantContext

router = APIRouter(prefix="/api/v1/anomalies", tags=["Anomalies & Outlier Detection"])


@router.post(
    "/detect",
    response_model=AnomalyDetectResponse,
    summary="Run Anomaly Detection on Trace Execution",
)
async def detect_anomalies(
    req: AnomalyDetectRequest,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> AnomalyDetectResponse:
    """Run composite unsupervised anomaly detectors against trace execution telemetry."""
    raw_events = req.events

    # If no spans passed directly, load from database trace event hypertable
    if not raw_events:
        event_repo = TraceEventRepository(session)
        db_events = await event_repo.get_trace_events(req.execution_id, tenant_id=ctx.tenant_id)
        raw_events = [e.__dict__ for e in db_events]

    # 1. Run detection from singleton registry
    registry = AnomalyDetectorRegistry()
    detector = registry.get_detector()

    anomalies = detector.detect_anomalies(
        events=raw_events,
        execution_id=req.execution_id,
        workflow_definition_id=req.workflow_definition_id,
        as_of_step=req.as_of_step,
    )

    # 2. Map to Response Models
    from packages.observability.metrics import record_anomaly

    anomaly_responses: list[AnomalyResponse] = []
    for anom in anomalies:
        sev = detector.get_severity_label(anom.score)
        record_anomaly(
            detector_type=str(
                anom.anomaly_type.value
                if hasattr(anom.anomaly_type, "value")
                else anom.anomaly_type
            ),
            severity=sev,
        )
        resp = AnomalyResponse(
            id=anom.id,
            execution_id=anom.execution_id,
            workflow_definition_id=req.workflow_definition_id,
            anomaly_type=anom.anomaly_type.value
            if hasattr(anom.anomaly_type, "value")
            else str(anom.anomaly_type),
            score=round(anom.score, 3),
            severity=sev,
            affected_services=anom.affected_services,
            explanation=anom.explanation,
            evidence=anom.evidence,
            detected_at=anom.detected_at,
        )
        anomaly_responses.append(resp)

    max_score = max((a.score for a in anomaly_responses), default=0.0)
    highest_sev = detector.get_severity_label(max_score) if anomaly_responses else "NOMINAL"

    # 3. Optional persistence
    if req.persist_to_db and anomaly_responses:
        repo = AnomalyRepository(session)
        anomalies_to_save = [
            {
                "id": a.id,
                "tenant_id": ctx.tenant_id,
                "execution_id": a.execution_id,
                "workflow_definition_id": a.workflow_definition_id,
                "anomaly_type": a.anomaly_type,
                "score": a.score,
                "severity": a.severity,
                "affected_services": a.affected_services,
                "explanation": a.explanation,
                "evidence": a.evidence,
                "detected_at": a.detected_at,
            }
            for a in anomaly_responses
        ]
        await repo.save_anomalies_batch(anomalies_to_save, tenant_id=ctx.tenant_id)

    return AnomalyDetectResponse(
        execution_id=req.execution_id,
        workflow_definition_id=req.workflow_definition_id,
        is_anomalous=len(anomaly_responses) > 0 and max_score >= 0.40,
        max_score=round(max_score, 3),
        highest_severity=highest_sev,
        anomaly_count=len(anomaly_responses),
        anomalies=anomaly_responses,
    )


@router.get(
    "/stats",
    response_model=AnomalyStatsResponse,
    summary="Aggregated Anomaly Statistics",
)
async def get_anomaly_stats(
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> AnomalyStatsResponse:
    """Return aggregated counts by anomaly severity and anomaly type."""
    repo = AnomalyRepository(session)
    stats = await repo.get_anomaly_stats(tenant_id=ctx.tenant_id)
    return AnomalyStatsResponse(
        total_anomalies=stats["total_anomalies"],
        by_severity=stats["by_severity"],
        by_type=stats["by_type"],
    )


@router.get(
    "/executions/{execution_id}",
    response_model=list[AnomalyResponse],
    summary="Get Anomalies for an Execution",
)
async def get_execution_anomalies(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[AnomalyResponse]:
    """Retrieve all detected anomalies associated with a given execution ID."""
    repo = AnomalyRepository(session)
    records = await repo.get_anomalies_by_execution(execution_id, tenant_id=ctx.tenant_id)

    # If not yet recorded in DB, run on-demand detection
    if not records:
        event_repo = TraceEventRepository(session)
        db_events = await event_repo.get_trace_events(execution_id, tenant_id=ctx.tenant_id)
        if db_events:
            registry = AnomalyDetectorRegistry()
            detector = registry.get_detector()
            raw_anoms = detector.detect_anomalies(
                events=[e.__dict__ for e in db_events],
                execution_id=execution_id,
            )
            return [
                AnomalyResponse(
                    id=a.id,
                    execution_id=a.execution_id,
                    workflow_definition_id="default_workflow",
                    anomaly_type=a.anomaly_type.value
                    if hasattr(a.anomaly_type, "value")
                    else str(a.anomaly_type),
                    score=round(a.score, 3),
                    severity=detector.get_severity_label(a.score),
                    affected_services=a.affected_services,
                    explanation=a.explanation,
                    evidence=a.evidence,
                    detected_at=a.detected_at,
                )
                for a in raw_anoms
            ]

    return [
        AnomalyResponse(
            id=r.id,
            execution_id=r.execution_id,
            workflow_definition_id=r.workflow_definition_id,
            anomaly_type=r.anomaly_type,
            score=round(r.score, 3),
            severity=r.severity,
            affected_services=r.affected_services,
            explanation=r.explanation,
            evidence=r.evidence,
            detected_at=r.detected_at,
        )
        for r in records
    ]


@router.get(
    "",
    response_model=PaginatedResponse[AnomalyResponse],
    summary="List Recorded Anomalies with Filters",
)
async def list_anomalies(
    workflow_definition_id: str | None = Query(default=None),
    anomaly_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> PaginatedResponse[AnomalyResponse]:
    """Search and filter historical anomalies with pagination."""
    repo = AnomalyRepository(session)
    offset = (page - 1) * page_size
    records, total = await repo.list_anomalies(
        workflow_definition_id=workflow_definition_id,
        anomaly_type=anomaly_type,
        severity=severity,
        min_score=min_score,
        limit=page_size,
        offset=offset,
        tenant_id=ctx.tenant_id,
    )

    items = [
        AnomalyResponse(
            id=r.id,
            execution_id=r.execution_id,
            workflow_definition_id=r.workflow_definition_id,
            anomaly_type=r.anomaly_type,
            score=round(r.score, 3),
            severity=r.severity,
            affected_services=r.affected_services,
            explanation=r.explanation,
            evidence=r.evidence,
            detected_at=r.detected_at,
        )
        for r in records
    ]

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=page_size,
            offset=offset,
            has_more=(offset + len(items)) < total,
        ),
    )


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyResponse,
    summary="Get Anomaly Record Details",
)
async def get_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> AnomalyResponse:
    """Retrieve details for a single anomaly record."""
    repo = AnomalyRepository(session)
    rec = await repo.get_anomaly(anomaly_id, tenant_id=ctx.tenant_id)
    if not rec:
        raise EntityNotFoundException("Anomaly", anomaly_id)

    return AnomalyResponse(
        id=rec.id,
        execution_id=rec.execution_id,
        workflow_definition_id=rec.workflow_definition_id,
        anomaly_type=rec.anomaly_type,
        score=round(rec.score, 3),
        severity=rec.severity,
        affected_services=rec.affected_services,
        explanation=rec.explanation,
        evidence=rec.evidence,
        detected_at=rec.detected_at,
    )


@router.post(
    "/fit",
    response_model=AnomalyFitResponse,
    summary="Fit / Calibrate Anomaly Detectors",
    dependencies=[Depends(require_permission(Permission.ANOMALIES_FEEDBACK))],
)
async def fit_anomaly_detectors(
    req: AnomalyFitRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> AnomalyFitResponse:
    """Calibrate baseline statistical distributions and DAG transitions using synthetic trace simulation."""
    registry = AnomalyDetectorRegistry()
    registry._bootstrap_default_baselines()
    detector = registry.get_detector()

    services_fitted = list(detector.latency_detector.service_stats.keys())
    transitions_count = sum(len(v) for v in detector.sequence_detector.transition_probs.values())

    return AnomalyFitResponse(
        status="success",
        version=req.version,
        services_fitted=services_fitted,
        transitions_fitted=transitions_count,
    )
