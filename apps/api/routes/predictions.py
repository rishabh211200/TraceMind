"""FastAPI router for ML workflow failure & latency predictions and TreeSHAP explainability."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.security import (
    get_tenant_context,
    require_permission,
)
from apps.api.schemas.prediction import (
    FeatureContributionResponse,
    ModelMetadataResponse,
    PredictionRequest,
    PredictionResponse,
    TrainRequest,
    TrainResponse,
)
from apps.ml.features import FEATURE_NAMES, TraceFeatureExtractor
from apps.ml.registry import ModelRegistry
from apps.ml.trainer import ModelTrainer
from packages.database.repositories.prediction_repository import PredictionRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.session import get_db_session
from packages.domain.security import Permission, TenantContext

router = APIRouter(prefix="/api/v1/predictions", tags=["Intelligence & ML Engine"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="In-Flight Failure & Latency Prediction with TreeSHAP",
    dependencies=[Depends(require_permission(Permission.PREDICTIONS_EXECUTE))],
)
async def predict_execution(
    req: PredictionRequest,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> PredictionResponse:
    """Extract in-flight features from partial trace spans, infer failure probability & duration, and compute TreeSHAP attributions."""
    raw_events = req.events

    # If no spans passed directly, load from database trace event hypertable
    if not raw_events:
        event_repo = TraceEventRepository(session)
        db_events = await event_repo.get_trace_events(req.execution_id, tenant_id=ctx.tenant_id)
        raw_events = [e.__dict__ for e in db_events]

    import time

    from packages.observability.metrics import record_ml_inference

    t_start = time.perf_counter()

    # 1. In-flight feature extraction
    extractor = TraceFeatureExtractor()
    features = extractor.extract_features_from_events(raw_events, as_of_step=req.as_of_step)

    # 2. Model inference from singleton cache
    classifier, regressor, explainer = ModelRegistry().get_models()
    meta = ModelRegistry().get_metadata()

    fail_prob, risk_level = classifier.predict_single(features)
    pred_latency = regressor.predict_single(features)

    # 3. TreeSHAP feature attributions
    contributions = explainer.explain_instance(features, top_k=5)
    inference_duration = time.perf_counter() - t_start
    record_ml_inference(
        "xgboost_workflow_predictor", "predict_failure", inference_duration, risk_level
    )
    contrib_responses = [
        FeatureContributionResponse(
            feature_name=c.feature_name,
            value=c.value,
            contribution=c.contribution,
            description=c.description,
        )
        for c in contributions
    ]

    pred_id = f"pred_{uuid4().hex[:10]}"
    step_idx = req.as_of_step or int(features.get("step_count", 0))

    # 4. Optional Database persistence
    if req.persist_to_db:
        pred_repo = PredictionRepository(session)
        await pred_repo.save_prediction(
            prediction_id=pred_id,
            tenant_id=ctx.tenant_id,
            execution_id=req.execution_id,
            workflow_definition_id=req.workflow_definition_id,
            step_index=step_idx,
            failure_probability=fail_prob,
            predicted_risk_level=risk_level,
            predicted_latency_ms=pred_latency,
            confidence=1.0,
            feature_attributions=[c.model_dump() for c in contrib_responses],
            feature_vector=features,
            model_name=meta.get("model_name", "xgboost_workflow_predictor"),
            model_version=meta.get("version", "1.0.0"),
        )

    return PredictionResponse(
        id=pred_id,
        execution_id=req.execution_id,
        workflow_definition_id=req.workflow_definition_id,
        step_index=step_idx,
        failure_probability=fail_prob,
        predicted_risk_level=risk_level,
        predicted_latency_ms=pred_latency,
        confidence=1.0,
        top_contributions=contrib_responses,
        feature_vector=features,
        model_name=meta.get("model_name", "xgboost_workflow_predictor"),
        model_version=meta.get("version", "1.0.0"),
        created_at=datetime.now(UTC),
    )


@router.get(
    "/executions/{execution_id}",
    response_model=list[PredictionResponse],
    summary="Get Execution Predictions",
)
async def get_execution_predictions(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[PredictionResponse]:
    """Retrieve persisted prediction records for an execution, or generate on-demand if none exist."""
    pred_repo = PredictionRepository(session)
    stored = await pred_repo.list_predictions_for_execution(execution_id, tenant_id=ctx.tenant_id)

    if stored:
        return [
            PredictionResponse(
                id=p.id,
                execution_id=p.execution_id,
                workflow_definition_id=p.workflow_definition_id,
                step_index=p.step_index,
                failure_probability=p.failure_probability,
                predicted_risk_level=p.predicted_risk_level,
                predicted_latency_ms=p.predicted_latency_ms,
                confidence=p.confidence,
                top_contributions=[
                    FeatureContributionResponse(**c) for c in p.feature_attributions
                ],
                feature_vector=p.feature_vector,
                model_name=p.model_name,
                model_version=p.model_version,
                created_at=p.created_at,
            )
            for p in stored
        ]

    # Generate on-demand prediction from execution trace spans in database
    event_repo = TraceEventRepository(session)
    events = await event_repo.get_trace_events(execution_id, tenant_id=ctx.tenant_id)

    pred = await predict_execution(
        PredictionRequest(
            execution_id=execution_id,
            events=[e.__dict__ for e in events],
            persist_to_db=True,
        ),
        session=session,
        ctx=ctx,
    )
    return [pred]


@router.post(
    "/train",
    response_model=TrainResponse,
    status_code=status.HTTP_200_OK,
    summary="Train & Evaluate Prediction Models",
    dependencies=[Depends(require_permission(Permission.PREDICTIONS_EXECUTE))],
)
async def train_models(
    req: TrainRequest = TrainRequest(),
    ctx: TenantContext = Depends(get_tenant_context),
) -> TrainResponse:
    """Train XGBoost classifier and regressor on synthetic trace simulations and update registry."""
    trainer = ModelTrainer(random_state=req.random_state)
    X, y_fail, y_lat, groups = trainer.generate_synthetic_training_data(
        nominal_workflows=req.nominal_workflows,
        incident_workflows_per_scenario=req.incident_workflows_per_scenario,
    )

    report = trainer.train_and_evaluate(X, y_fail, y_lat, groups=groups)

    registry = ModelRegistry()
    registry.save_models(
        classifier=report["classifier"],
        regressor=report["regressor"],
        metrics=report["metrics"],
        version=req.version,
    )

    return TrainResponse(
        status="trained",
        version=req.version,
        training_samples=report["training_samples"],
        test_samples=report["test_samples"],
        metrics=report["metrics"],
    )


@router.get(
    "/models",
    response_model=ModelMetadataResponse,
    summary="Get Active Model Information",
)
async def get_model_info(
    ctx: TenantContext = Depends(get_tenant_context),
) -> ModelMetadataResponse:
    """Inspect active model version, evaluation metrics, and feature names."""
    registry = ModelRegistry()
    registry.get_models()  # Ensure initialized
    meta = registry.get_metadata()

    return ModelMetadataResponse(
        version=meta.get("version", "1.0.0"),
        model_name=meta.get("model_name", "xgboost_workflow_predictor"),
        status=meta.get("status", "ready"),
        features=FEATURE_NAMES,
        metrics=meta.get("metrics", {}),
    )

