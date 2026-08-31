"""Prediction repository for workflow failure probabilities and TreeSHAP attributions."""

from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.prediction import PredictionModel


class PredictionRepository:
    """Async repository for PredictionModel entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_prediction(
        self,
        execution_id: str,
        workflow_definition_id: str,
        failure_probability: float,
        predicted_risk_level: str,
        predicted_latency_ms: float,
        step_index: int = 0,
        confidence: float = 1.0,
        feature_attributions: list[dict[str, Any]] | None = None,
        feature_vector: dict[str, Any] | None = None,
        model_name: str = "xgboost_workflow_predictor",
        model_version: str = "1.0.0",
        prediction_id: str | None = None,
        tenant_id: str = "tenant_system",
    ) -> PredictionModel:
        """Create and persist a new workflow prediction record."""
        pred = PredictionModel(
            id=prediction_id or f"pred_{uuid4().hex[:10]}",
            tenant_id=tenant_id,
            execution_id=execution_id,
            workflow_definition_id=workflow_definition_id,
            step_index=step_index,
            failure_probability=failure_probability,
            predicted_risk_level=predicted_risk_level,
            predicted_latency_ms=predicted_latency_ms,
            confidence=confidence,
            feature_attributions=feature_attributions or [],
            feature_vector=feature_vector or {},
            model_name=model_name,
            model_version=model_version,
        )
        self.session.add(pred)
        await self.session.commit()
        await self.session.refresh(pred)
        return pred

    async def get_prediction(self, prediction_id: str, tenant_id: str | None = None) -> PredictionModel | None:
        """Fetch a specific prediction by its unique identifier."""
        stmt = select(PredictionModel).where(PredictionModel.id == prediction_id)
        if tenant_id:
            stmt = stmt.where(PredictionModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_predictions_for_execution(
        self, execution_id: str, tenant_id: str | None = None
    ) -> list[PredictionModel]:
        """Fetch all chronological in-flight predictions made for a given execution."""
        stmt = (
            select(PredictionModel)
            .where(PredictionModel.execution_id == execution_id)
            .order_by(PredictionModel.step_index.asc(), PredictionModel.created_at.asc())
        )
        if tenant_id:
            stmt = stmt.where(PredictionModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent_predictions(
        self,
        workflow_definition_id: str | None = None,
        min_failure_probability: float | None = None,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[PredictionModel]:
        """Query recent predictions with optional risk and workflow filtering."""
        stmt = select(PredictionModel)

        if tenant_id:
            stmt = stmt.where(PredictionModel.tenant_id == tenant_id)
        if workflow_definition_id:
            stmt = stmt.where(PredictionModel.workflow_definition_id == workflow_definition_id)
        if min_failure_probability is not None:
            stmt = stmt.where(PredictionModel.failure_probability >= min_failure_probability)

        stmt = stmt.order_by(desc(PredictionModel.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_predictions(
        self,
        workflow_definition_id: str | None = None,
        min_failure_probability: float | None = None,
        tenant_id: str | None = None,
    ) -> int:
        """Count total predictions matching criteria."""
        stmt = select(func.count(PredictionModel.id))
        if tenant_id:
            stmt = stmt.where(PredictionModel.tenant_id == tenant_id)
        if workflow_definition_id:
            stmt = stmt.where(PredictionModel.workflow_definition_id == workflow_definition_id)
        if min_failure_probability is not None:
            stmt = stmt.where(PredictionModel.failure_probability >= min_failure_probability)
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

