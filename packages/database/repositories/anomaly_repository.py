"""Async repository for querying and persisting workflow anomaly detection records."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.anomaly import AnomalyModel


class AnomalyRepository:
    """Async repository providing CRUD operations for workflow anomaly records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_anomaly(
        self,
        execution_id: str,
        workflow_definition_id: str,
        anomaly_type: str,
        score: float,
        explanation: str,
        severity: str = "INFO",
        affected_services: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        anomaly_id: str | None = None,
        detected_at: datetime | None = None,
    ) -> AnomalyModel:
        """Create and persist a new anomaly detection record."""
        record_id = anomaly_id or f"anom_{uuid4().hex[:12]}"
        now = detected_at or datetime.now(UTC)

        anomaly = AnomalyModel(
            id=record_id,
            execution_id=execution_id,
            workflow_definition_id=workflow_definition_id,
            anomaly_type=anomaly_type,
            score=float(score),
            severity=severity,
            affected_services=affected_services or [],
            explanation=explanation,
            evidence=evidence or {},
            detected_at=now,
        )
        self.session.add(anomaly)
        await self.session.commit()
        await self.session.refresh(anomaly)
        return anomaly

    async def save_anomalies_batch(
        self,
        anomalies_data: list[dict[str, Any]],
    ) -> list[AnomalyModel]:
        """Persist a batch of anomaly records in a single database transaction."""
        models: list[AnomalyModel] = []
        now = datetime.now(UTC)

        for data in anomalies_data:
            rec_id = data.get("id") or f"anom_{uuid4().hex[:12]}"
            det_at = data.get("detected_at") or now
            if isinstance(det_at, str):
                det_at = datetime.fromisoformat(det_at.replace("Z", "+00:00"))

            model = AnomalyModel(
                id=rec_id,
                execution_id=data["execution_id"],
                workflow_definition_id=data.get("workflow_definition_id", "default_workflow"),
                anomaly_type=data["anomaly_type"],
                score=float(data["score"]),
                severity=data.get("severity", "INFO"),
                affected_services=data.get("affected_services", []),
                explanation=data.get("explanation", ""),
                evidence=data.get("evidence", {}),
                detected_at=det_at,
            )
            models.append(model)
            self.session.add(model)

        if models:
            await self.session.commit()
            for m in models:
                await self.session.refresh(m)

        return models

    async def get_anomaly(self, anomaly_id: str) -> AnomalyModel | None:
        """Retrieve an anomaly record by its unique ID."""
        stmt = select(AnomalyModel).where(AnomalyModel.id == anomaly_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_anomalies_by_execution(self, execution_id: str) -> list[AnomalyModel]:
        """Retrieve all detected anomalies for a specific workflow execution run."""
        stmt = (
            select(AnomalyModel)
            .where(AnomalyModel.execution_id == execution_id)
            .order_by(AnomalyModel.score.desc(), AnomalyModel.detected_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_anomalies(
        self,
        workflow_definition_id: str | None = None,
        anomaly_type: str | None = None,
        severity: str | None = None,
        min_score: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnomalyModel], int]:
        """List anomalies matching multi-column criteria with pagination."""
        stmt = select(AnomalyModel)
        count_stmt = select(func.count(AnomalyModel.id))

        if workflow_definition_id:
            stmt = stmt.where(AnomalyModel.workflow_definition_id == workflow_definition_id)
            count_stmt = count_stmt.where(
                AnomalyModel.workflow_definition_id == workflow_definition_id
            )

        if anomaly_type:
            stmt = stmt.where(AnomalyModel.anomaly_type == anomaly_type)
            count_stmt = count_stmt.where(AnomalyModel.anomaly_type == anomaly_type)

        if severity:
            stmt = stmt.where(AnomalyModel.severity == severity)
            count_stmt = count_stmt.where(AnomalyModel.severity == severity)

        if min_score is not None:
            stmt = stmt.where(AnomalyModel.score >= min_score)
            count_stmt = count_stmt.where(AnomalyModel.score >= min_score)

        # Count total
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        # Fetch page
        stmt = stmt.order_by(AnomalyModel.detected_at.desc(), AnomalyModel.score.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_anomaly_stats(self) -> dict[str, Any]:
        """Calculate aggregated anomaly counts by type, severity, and impacted services."""
        # Total count
        total_stmt = select(func.count(AnomalyModel.id))
        total_res = await self.session.execute(total_stmt)
        total_anomalies = total_res.scalar() or 0

        # By severity
        sev_stmt = select(AnomalyModel.severity, func.count(AnomalyModel.id)).group_by(
            AnomalyModel.severity
        )
        sev_res = await self.session.execute(sev_stmt)
        by_severity = {row[0]: row[1] for row in sev_res.all()}

        # By anomaly type
        type_stmt = select(AnomalyModel.anomaly_type, func.count(AnomalyModel.id)).group_by(
            AnomalyModel.anomaly_type
        )
        type_res = await self.session.execute(type_stmt)
        by_type = {row[0]: row[1] for row in type_res.all()}

        return {
            "total_anomalies": total_anomalies,
            "by_severity": by_severity,
            "by_type": by_type,
        }
