"""Async repository for root-cause diagnoses and incident explanations."""

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.logging import get_logger
from packages.database.models.root_cause import RootCauseModel

logger = get_logger("tracemind.database.root_cause_repository")


class RootCauseRepository:
    """Repository managing asynchronous persistence and queries for root-cause reports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_root_cause_report(
        self,
        report_data: dict[str, Any] | RootCauseModel,
        tenant_id: str = "tenant_system",
    ) -> RootCauseModel:
        """Persist a newly generated root-cause diagnosis."""
        if isinstance(report_data, RootCauseModel):
            if not getattr(report_data, "tenant_id", None):
                report_data.tenant_id = tenant_id
            model = report_data
        else:
            model = RootCauseModel(
                id=report_data.get("id") or f"rc_{uuid4().hex[:10]}",
                tenant_id=report_data.get("tenant_id", tenant_id),
                execution_id=report_data["execution_id"],
                workflow_definition_id=report_data.get(
                    "workflow_definition_id", "order_fulfillment"
                ),
                culprit_service=report_data["culprit_service"],
                incident_category=report_data["incident_category"],
                confidence=float(report_data.get("confidence", 1.0)),
                causal_path=report_data.get("causal_path", []),
                supporting_evidence=report_data.get("supporting_evidence", []),
                alternative_hypotheses=report_data.get("alternative_hypotheses", []),
            )

        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        logger.info(
            "root_cause_report_created",
            id=model.id,
            tenant_id=model.tenant_id,
            execution_id=model.execution_id,
            culprit=model.culprit_service,
            category=model.incident_category,
        )
        return model

    async def get_by_id(self, id: str, tenant_id: str | None = None) -> RootCauseModel | None:
        """Fetch a single root-cause diagnosis by its unique ID."""
        stmt = select(RootCauseModel).where(RootCauseModel.id == id)
        if tenant_id:
            stmt = stmt.where(RootCauseModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_execution_id(self, execution_id: str, tenant_id: str | None = None) -> list[RootCauseModel]:
        """Fetch all root-cause diagnoses associated with a workflow execution."""
        stmt = (
            select(RootCauseModel)
            .where(RootCauseModel.execution_id == execution_id)
            .order_by(RootCauseModel.analyzed_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(RootCauseModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_reports(
        self,
        workflow_definition_id: str | None = None,
        culprit_service: str | None = None,
        incident_category: str | None = None,
        min_confidence: float | None = None,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> tuple[list[RootCauseModel], int]:
        """Search and filter historical root-cause diagnoses with pagination."""
        stmt = select(RootCauseModel)
        count_stmt = select(func.count()).select_from(RootCauseModel)

        if tenant_id:
            stmt = stmt.where(RootCauseModel.tenant_id == tenant_id)
            count_stmt = count_stmt.where(RootCauseModel.tenant_id == tenant_id)

        if workflow_definition_id:
            stmt = stmt.where(RootCauseModel.workflow_definition_id == workflow_definition_id)
            count_stmt = count_stmt.where(
                RootCauseModel.workflow_definition_id == workflow_definition_id
            )
        if culprit_service:
            stmt = stmt.where(RootCauseModel.culprit_service == culprit_service)
            count_stmt = count_stmt.where(RootCauseModel.culprit_service == culprit_service)
        if incident_category:
            stmt = stmt.where(RootCauseModel.incident_category == incident_category)
            count_stmt = count_stmt.where(RootCauseModel.incident_category == incident_category)
        if min_confidence is not None:
            stmt = stmt.where(RootCauseModel.confidence >= min_confidence)
            count_stmt = count_stmt.where(RootCauseModel.confidence >= min_confidence)

        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one() or 0)

        stmt = stmt.order_by(RootCauseModel.analyzed_at.desc()).limit(limit).offset(offset)
        items_result = await self.session.execute(stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def get_stats(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Aggregate summary statistics across all root-cause diagnoses."""
        count_stmt = select(func.count()).select_from(RootCauseModel)
        if tenant_id:
            count_stmt = count_stmt.where(RootCauseModel.tenant_id == tenant_id)
        total_res = await self.session.execute(count_stmt)
        total_reports = int(total_res.scalar_one() or 0)

        if total_reports == 0:
            return {
                "total_diagnoses": 0,
                "by_category": {},
                "by_culprit_service": {},
                "mean_confidence": 0.0,
            }

        # Counts by category
        cat_stmt = select(
            RootCauseModel.incident_category,
            func.count(RootCauseModel.id),
        )
        if tenant_id:
            cat_stmt = cat_stmt.where(RootCauseModel.tenant_id == tenant_id)
        cat_stmt = cat_stmt.group_by(RootCauseModel.incident_category)
        cat_res = await self.session.execute(cat_stmt)
        by_category = {row[0]: row[1] for row in cat_res.all()}

        # Counts by culprit service
        culprit_stmt = select(
            RootCauseModel.culprit_service,
            func.count(RootCauseModel.id),
        )
        if tenant_id:
            culprit_stmt = culprit_stmt.where(RootCauseModel.tenant_id == tenant_id)
        culprit_stmt = (
            culprit_stmt.group_by(RootCauseModel.culprit_service)
            .order_by(func.count(RootCauseModel.id).desc())
            .limit(10)
        )
        culprit_res = await self.session.execute(culprit_stmt)
        by_culprit = {row[0]: row[1] for row in culprit_res.all()}

        # Mean confidence
        mean_stmt = select(func.avg(RootCauseModel.confidence))
        if tenant_id:
            mean_stmt = mean_stmt.where(RootCauseModel.tenant_id == tenant_id)
        mean_res = await self.session.execute(mean_stmt)
        mean_conf = float(mean_res.scalar_one() or 0.0)

        return {
            "total_diagnoses": total_reports,
            "by_category": by_category,
            "by_culprit_service": by_culprit,
            "mean_confidence": round(mean_conf, 3),
        }

