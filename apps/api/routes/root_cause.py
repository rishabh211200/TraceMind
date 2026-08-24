"""FastAPI router for deterministic graph-based root cause analysis."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.exceptions import EntityNotFoundException
from apps.api.schemas.common import PaginatedResponse, PaginationMeta
from apps.api.schemas.root_cause import (
    HypothesisItem,
    RootCauseAnalyzeRequest,
    RootCauseReportResponse,
    RootCauseStatsResponse,
)
from apps.ml.anomalies.registry import AnomalyDetectorRegistry
from apps.ml.root_cause.engine import RootCauseEngine, RootCauseReport
from packages.database.repositories.anomaly_repository import AnomalyRepository
from packages.database.repositories.prediction_repository import PredictionRepository
from packages.database.repositories.root_cause_repository import RootCauseRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.session import get_db_session

router = APIRouter(prefix="/api/v1/root-cause", tags=["Root Cause Engine"])

_engine = RootCauseEngine()


def _map_report_to_response(report: RootCauseReport) -> RootCauseReportResponse:
    """Map internal dataclass or ORM report to API response schema."""
    primary = HypothesisItem(
        id=report.primary_hypothesis.id,
        culprit_service=report.primary_hypothesis.culprit_service,
        incident_category=report.primary_hypothesis.incident_category,
        confidence=round(report.primary_hypothesis.confidence, 3),
        causal_path=report.primary_hypothesis.causal_path,
        supporting_evidence=report.primary_hypothesis.supporting_evidence,
        score_breakdown=report.primary_hypothesis.score_breakdown,
    )
    alternatives = [
        HypothesisItem(
            id=alt.id,
            culprit_service=alt.culprit_service,
            incident_category=alt.incident_category,
            confidence=round(alt.confidence, 3),
            causal_path=alt.causal_path,
            supporting_evidence=alt.supporting_evidence,
            score_breakdown=alt.score_breakdown,
        )
        for alt in report.alternative_hypotheses
    ]

    return RootCauseReportResponse(
        id=report.id,
        execution_id=report.execution_id,
        workflow_definition_id=report.workflow_definition_id,
        culprit_service=report.culprit_service,
        incident_category=report.incident_category,
        confidence=round(report.confidence, 3),
        causal_path=report.causal_path,
        supporting_evidence=report.supporting_evidence,
        primary_hypothesis=primary,
        alternative_hypotheses=alternatives,
        analyzed_at=report.analyzed_at,
    )


@router.post(
    "/analyze",
    response_model=RootCauseReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Root Cause for Execution",
)
async def analyze_root_cause(
    payload: RootCauseAnalyzeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RootCauseReportResponse:
    """Run deterministic causal graph reasoning to identify culprit dependencies."""
    events: list[dict[str, Any]] | None = payload.events
    if events is None:
        event_repo = TraceEventRepository(session)
        db_events = await event_repo.get_trace_events(payload.execution_id)
        events = [e.__dict__ for e in db_events]

    anomalies = payload.anomalies
    if anomalies is None:
        anom_repo = AnomalyRepository(session)
        db_anoms = await anom_repo.get_anomalies_by_execution(payload.execution_id)
        if db_anoms:
            anomalies = [
                {
                    "id": a.id,
                    "anomaly_type": a.anomaly_type,
                    "score": a.score,
                    "affected_services": a.affected_services,
                    "evidence": a.evidence,
                }
                for a in db_anoms
            ]
        elif events:
            detector = AnomalyDetectorRegistry().get_detector()
            live_anoms = detector.detect_anomalies(events, execution_id=payload.execution_id)
            anomalies = [
                {
                    "id": a.id,
                    "anomaly_type": a.anomaly_type.value
                    if hasattr(a.anomaly_type, "value")
                    else str(a.anomaly_type),
                    "score": a.score,
                    "affected_services": a.affected_services,
                    "evidence": a.evidence,
                }
                for a in live_anoms
            ]

    shap_contribs = payload.shap_contributions
    if shap_contribs is None:
        pred_repo = PredictionRepository(session)
        db_preds = await pred_repo.list_predictions_for_execution(payload.execution_id)
        if db_preds and db_preds[0].feature_attributions:
            shap_contribs = db_preds[0].feature_attributions

    # Execute Root Cause Engine
    report = _engine.diagnose_execution(
        events=events or [],
        anomalies=anomalies,
        shap_contributions=shap_contribs,
        execution_id=payload.execution_id,
        workflow_definition_id=payload.workflow_definition_id,
    )

    # Persist if requested
    if payload.persist_to_db:
        repo = RootCauseRepository(session)
        await repo.create_root_cause_report(
            {
                "id": report.id,
                "execution_id": report.execution_id,
                "workflow_definition_id": report.workflow_definition_id,
                "culprit_service": report.culprit_service,
                "incident_category": report.incident_category,
                "confidence": report.confidence,
                "causal_path": report.causal_path,
                "supporting_evidence": report.supporting_evidence,
                "alternative_hypotheses": [
                    {
                        "id": h.id,
                        "culprit_service": h.culprit_service,
                        "incident_category": h.incident_category,
                        "confidence": h.confidence,
                        "causal_path": h.causal_path,
                        "supporting_evidence": h.supporting_evidence,
                    }
                    for h in report.alternative_hypotheses
                ],
            }
        )

    return _map_report_to_response(report)


@router.get(
    "/executions/{execution_id}",
    response_model=list[RootCauseReportResponse],
    summary="Get Root Cause Reports for Execution",
)
async def get_reports_by_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[RootCauseReportResponse]:
    """Retrieve all historical root cause diagnoses for an execution."""
    repo = RootCauseRepository(session)
    records = await repo.get_by_execution_id(execution_id)

    responses: list[RootCauseReportResponse] = []
    for r in records:
        primary = HypothesisItem(
            id=f"hyp_{r.id}",
            culprit_service=r.culprit_service,
            incident_category=r.incident_category,
            confidence=round(r.confidence, 3),
            causal_path=r.causal_path,
            supporting_evidence=r.supporting_evidence,
        )
        alternatives = [
            HypothesisItem(
                id=alt.get("id", ""),
                culprit_service=alt.get("culprit_service", ""),
                incident_category=alt.get("incident_category", ""),
                confidence=round(float(alt.get("confidence", 0.0)), 3),
                causal_path=alt.get("causal_path", []),
                supporting_evidence=alt.get("supporting_evidence", []),
            )
            for alt in r.alternative_hypotheses
        ]
        responses.append(
            RootCauseReportResponse(
                id=r.id,
                execution_id=r.execution_id,
                workflow_definition_id=r.workflow_definition_id,
                culprit_service=r.culprit_service,
                incident_category=r.incident_category,
                confidence=round(r.confidence, 3),
                causal_path=r.causal_path,
                supporting_evidence=r.supporting_evidence,
                primary_hypothesis=primary,
                alternative_hypotheses=alternatives,
                analyzed_at=r.analyzed_at,
            )
        )

    return responses


@router.get(
    "/stats",
    response_model=RootCauseStatsResponse,
    summary="Get Aggregate Root Cause Statistics",
)
async def get_root_cause_stats(
    session: AsyncSession = Depends(get_db_session),
) -> RootCauseStatsResponse:
    """Retrieve aggregate statistics on incident categories, culprits, and confidence."""
    repo = RootCauseRepository(session)
    stats_data = await repo.get_stats()
    return RootCauseStatsResponse(
        total_diagnoses=stats_data["total_diagnoses"],
        by_category=stats_data["by_category"],
        by_culprit_service=stats_data["by_culprit_service"],
        mean_confidence=stats_data["mean_confidence"],
    )


@router.get(
    "",
    response_model=PaginatedResponse[RootCauseReportResponse],
    summary="List Root Cause Reports with Filters",
)
async def list_root_cause_reports(
    workflow_definition_id: str | None = Query(default=None),
    culprit_service: str | None = Query(default=None),
    incident_category: str | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[RootCauseReportResponse]:
    """Search and filter historical root cause diagnoses with pagination."""
    repo = RootCauseRepository(session)
    offset = (page - 1) * page_size
    records, total = await repo.list_reports(
        workflow_definition_id=workflow_definition_id,
        culprit_service=culprit_service,
        incident_category=incident_category,
        min_confidence=min_confidence,
        limit=page_size,
        offset=offset,
    )

    items: list[RootCauseReportResponse] = []
    for r in records:
        primary = HypothesisItem(
            id=f"hyp_{r.id}",
            culprit_service=r.culprit_service,
            incident_category=r.incident_category,
            confidence=round(r.confidence, 3),
            causal_path=r.causal_path,
            supporting_evidence=r.supporting_evidence,
        )
        alternatives = [
            HypothesisItem(
                id=alt.get("id", ""),
                culprit_service=alt.get("culprit_service", ""),
                incident_category=alt.get("incident_category", ""),
                confidence=round(float(alt.get("confidence", 0.0)), 3),
                causal_path=alt.get("causal_path", []),
                supporting_evidence=alt.get("supporting_evidence", []),
            )
            for alt in r.alternative_hypotheses
        ]
        items.append(
            RootCauseReportResponse(
                id=r.id,
                execution_id=r.execution_id,
                workflow_definition_id=r.workflow_definition_id,
                culprit_service=r.culprit_service,
                incident_category=r.incident_category,
                confidence=round(r.confidence, 3),
                causal_path=r.causal_path,
                supporting_evidence=r.supporting_evidence,
                primary_hypothesis=primary,
                alternative_hypotheses=alternatives,
                analyzed_at=r.analyzed_at,
            )
        )

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
    "/{report_id}",
    response_model=RootCauseReportResponse,
    summary="Get Root Cause Report Details",
)
async def get_root_cause_report(
    report_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> RootCauseReportResponse:
    """Retrieve detailed root cause report by ID."""
    repo = RootCauseRepository(session)
    r = await repo.get_by_id(report_id)
    if not r:
        raise EntityNotFoundException(entity_type="RootCauseReport", entity_id=report_id)

    primary = HypothesisItem(
        id=f"hyp_{r.id}",
        culprit_service=r.culprit_service,
        incident_category=r.incident_category,
        confidence=round(r.confidence, 3),
        causal_path=r.causal_path,
        supporting_evidence=r.supporting_evidence,
    )
    alternatives = [
        HypothesisItem(
            id=alt.get("id", ""),
            culprit_service=alt.get("culprit_service", ""),
            incident_category=alt.get("incident_category", ""),
            confidence=round(float(alt.get("confidence", 0.0)), 3),
            causal_path=alt.get("causal_path", []),
            supporting_evidence=alt.get("supporting_evidence", []),
        )
        for alt in r.alternative_hypotheses
    ]

    return RootCauseReportResponse(
        id=r.id,
        execution_id=r.execution_id,
        workflow_definition_id=r.workflow_definition_id,
        culprit_service=r.culprit_service,
        incident_category=r.incident_category,
        confidence=round(r.confidence, 3),
        causal_path=r.causal_path,
        supporting_evidence=r.supporting_evidence,
        primary_hypothesis=primary,
        alternative_hypotheses=alternatives,
        analyzed_at=r.analyzed_at,
    )
