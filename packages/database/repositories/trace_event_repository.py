"""Trace event repository providing time-series querying, tree reconstruction, and DB-side analytics."""

from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.trace_event import TraceEventModel


class TraceEventRepository:
    """Async repository for high-volume trace event telemetry."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert_events(self, records: list[dict[str, Any]]) -> int:
        """Bulk insert trace events with idempotency."""
        if not records:
            return 0
        objects = [TraceEventModel(**r) for r in records]
        for obj in objects:
            await self.session.merge(obj)
        await self.session.commit()
        return len(records)

    async def get_trace_events(self, execution_id: str) -> list[TraceEventModel]:
        """Retrieve all events for a trace strictly ordered by timestamp."""
        stmt = (
            select(TraceEventModel)
            .where(TraceEventModel.execution_id == execution_id)
            .order_by(TraceEventModel.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_trace_tree(self, execution_id: str) -> dict[str, Any] | None:
        """Reconstruct the hierarchical parent-child trace execution DAG tree."""
        events = await self.get_trace_events(execution_id)
        if not events:
            return None

        # Build lookup table of spans and adjacency map
        nodes: dict[str, dict[str, Any]] = {}
        children_map: dict[str, list[str]] = {}
        root_event_id: str | None = None

        for ev in events:
            ev_dict = {
                "event_id": ev.event_id,
                "timestamp": ev.timestamp.isoformat(),
                "service": ev.service,
                "operation": ev.operation,
                "event_type": ev.event_type,
                "status": ev.status,
                "latency_ms": ev.latency_ms,
                "parent_event_id": ev.parent_event_id,
                "correlation_id": ev.correlation_id,
                "metadata": ev.metadata_,
                "children": [],
            }
            nodes[ev.event_id] = ev_dict

            parent_id = ev.parent_event_id
            if not parent_id or parent_id not in nodes:
                # If no parent or parent not yet seen, candidate for root
                if not parent_id and not root_event_id:
                    root_event_id = ev.event_id
            else:
                children_map.setdefault(parent_id, []).append(ev.event_id)

        # Assemble tree recursively
        def build_subtree(node_id: str) -> dict[str, Any]:
            node = nodes[node_id]
            child_ids = children_map.get(node_id, [])
            node["children"] = [build_subtree(cid) for cid in child_ids]
            return node

        if root_event_id and root_event_id in nodes:
            return build_subtree(root_event_id)
        elif events:
            # If explicit root not marked, use the earliest event
            return build_subtree(events[0].event_id)
        return None

    async def get_service_latency_stats(
        self,
        service: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute P50, P90, P95, P99, Mean, Min, and Max latency for a service over a time window."""
        # Query database-side metrics
        dialect_name = self.session.bind.dialect.name if self.session.bind else "postgresql"

        base_stmt = select(TraceEventModel).where(
            TraceEventModel.service == service,
            TraceEventModel.latency_ms > 0.0,
        )
        if start_time:
            base_stmt = base_stmt.where(TraceEventModel.timestamp >= start_time)
        if end_time:
            base_stmt = base_stmt.where(TraceEventModel.timestamp <= end_time)

        if dialect_name == "postgresql":
            # Native PostgreSQL percentile_cont database-side analytics
            p_stmt = select(
                func.count(TraceEventModel.event_id).label("event_count"),
                func.avg(TraceEventModel.latency_ms).label("mean"),
                func.min(TraceEventModel.latency_ms).label("min"),
                func.max(TraceEventModel.latency_ms).label("max"),
                func.percentile_cont(0.50).within_group(TraceEventModel.latency_ms).label("p50"),
                func.percentile_cont(0.90).within_group(TraceEventModel.latency_ms).label("p90"),
                func.percentile_cont(0.95).within_group(TraceEventModel.latency_ms).label("p95"),
                func.percentile_cont(0.99).within_group(TraceEventModel.latency_ms).label("p99"),
            ).where(
                TraceEventModel.service == service,
                TraceEventModel.latency_ms > 0.0,
            )
            if start_time:
                p_stmt = p_stmt.where(TraceEventModel.timestamp >= start_time)
            if end_time:
                p_stmt = p_stmt.where(TraceEventModel.timestamp <= end_time)

            row = (await self.session.execute(p_stmt)).one()
            count = int(row.event_count or 0)
            if count == 0:
                return {
                    "service": service,
                    "count": 0,
                    "mean_latency_ms": 0.0,
                    "median_p50_latency_ms": 0.0,
                    "p90_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "p99_latency_ms": 0.0,
                    "min_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                }
            return {
                "service": service,
                "count": count,
                "mean_latency_ms": round(float(row.mean or 0.0), 2),
                "median_p50_latency_ms": round(float(row.p50 or 0.0), 2),
                "p90_latency_ms": round(float(row.p90 or 0.0), 2),
                "p95_latency_ms": round(float(row.p95 or 0.0), 2),
                "p99_latency_ms": round(float(row.p99 or 0.0), 2),
                "min_latency_ms": round(float(row.min or 0.0), 2),
                "max_latency_ms": round(float(row.max or 0.0), 2),
            }
        else:
            # Fallback for SQLite / unit testing
            stmt = select(TraceEventModel.latency_ms).where(
                TraceEventModel.service == service,
                TraceEventModel.latency_ms > 0.0,
            )
            if start_time:
                stmt = stmt.where(TraceEventModel.timestamp >= start_time)
            if end_time:
                stmt = stmt.where(TraceEventModel.timestamp <= end_time)

            rows = (await self.session.execute(stmt)).scalars().all()
            if not rows:
                return {
                    "service": service,
                    "count": 0,
                    "mean_latency_ms": 0.0,
                    "median_p50_latency_ms": 0.0,
                    "p90_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "p99_latency_ms": 0.0,
                    "min_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                }
            arr = np.array(rows, dtype=float)
            return {
                "service": service,
                "count": len(arr),
                "mean_latency_ms": round(float(np.mean(arr)), 2),
                "median_p50_latency_ms": round(float(np.median(arr)), 2),
                "p90_latency_ms": round(float(np.percentile(arr, 90)), 2),
                "p95_latency_ms": round(float(np.percentile(arr, 95)), 2),
                "p99_latency_ms": round(float(np.percentile(arr, 99)), 2),
                "min_latency_ms": round(float(np.min(arr)), 2),
                "max_latency_ms": round(float(np.max(arr)), 2),
            }

    async def get_service_health(
        self,
        service: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate call volume, error rate, retry rate, and timeout rate for a service."""
        stmt = select(
            func.count(TraceEventModel.event_id).label("total_events"),
            func.sum(case((TraceEventModel.status == "FAILURE", 1), else_=0)).label("failures"),
            func.sum(case((TraceEventModel.status == "TIMEOUT", 1), else_=0)).label("timeouts"),
            func.sum(case((TraceEventModel.status == "RETRY", 1), else_=0)).label("retries"),
        ).where(TraceEventModel.service == service)

        if start_time:
            stmt = stmt.where(TraceEventModel.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(TraceEventModel.timestamp <= end_time)

        row = (await self.session.execute(stmt)).one()
        total_events = int(row.total_events or 0)
        failures = int(row.failures or 0)
        timeouts = int(row.timeouts or 0)
        retries = int(row.retries or 0)

        error_rate = (failures / total_events * 100.0) if total_events > 0 else 0.0
        retry_rate = (retries / total_events * 100.0) if total_events > 0 else 0.0
        timeout_rate = (timeouts / total_events * 100.0) if total_events > 0 else 0.0

        latency_stats = await self.get_service_latency_stats(service, start_time, end_time)

        return {
            "service": service,
            "total_events": total_events,
            "failure_count": failures,
            "error_rate_percent": round(error_rate, 2),
            "retry_count": retries,
            "retry_rate_percent": round(retry_rate, 2),
            "timeout_count": timeouts,
            "timeout_rate_percent": round(timeout_rate, 2),
            "latency": latency_stats,
        }

    async def _get_telemetry_summary_pg(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Native single-query PostgreSQL percentile_cont + aggregations GROUP BY service."""
        stmt = (
            select(
                TraceEventModel.service,
                func.count(TraceEventModel.event_id).label("total_events"),
                func.sum(case((TraceEventModel.status == "FAILURE", 1), else_=0)).label("failures"),
                func.sum(case((TraceEventModel.status == "TIMEOUT", 1), else_=0)).label("timeouts"),
                func.sum(case((TraceEventModel.status == "RETRY", 1), else_=0)).label("retries"),
                func.count(case((TraceEventModel.latency_ms > 0.0, 1), else_=None)).label(
                    "lat_count"
                ),
                func.avg(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                ).label("mean_lat"),
                func.min(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                ).label("min_lat"),
                func.max(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                ).label("max_lat"),
                func.percentile_cont(0.50)
                .within_group(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                )
                .label("p50"),
                func.percentile_cont(0.90)
                .within_group(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                )
                .label("p90"),
                func.percentile_cont(0.95)
                .within_group(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                )
                .label("p95"),
                func.percentile_cont(0.99)
                .within_group(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                )
                .label("p99"),
            )
            .group_by(TraceEventModel.service)
            .order_by(TraceEventModel.service.asc())
        )

        if start_time:
            stmt = stmt.where(TraceEventModel.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(TraceEventModel.timestamp <= end_time)

        rows = (await self.session.execute(stmt)).all()
        summaries = []
        for r in rows:
            tot = int(r.total_events or 0)
            fail = int(r.failures or 0)
            tout = int(r.timeouts or 0)
            ret = int(r.retries or 0)
            l_count = int(r.lat_count or 0)

            error_rate = (fail / tot * 100.0) if tot > 0 else 0.0
            retry_rate = (ret / tot * 100.0) if tot > 0 else 0.0
            timeout_rate = (tout / tot * 100.0) if tot > 0 else 0.0

            summaries.append(
                {
                    "service": str(r.service),
                    "total_events": tot,
                    "failure_count": fail,
                    "error_rate_percent": round(error_rate, 2),
                    "retry_count": ret,
                    "retry_rate_percent": round(retry_rate, 2),
                    "timeout_count": tout,
                    "timeout_rate_percent": round(timeout_rate, 2),
                    "latency": {
                        "service": str(r.service),
                        "count": l_count,
                        "mean_latency_ms": round(float(r.mean_lat), 2) if r.mean_lat else 0.0,
                        "median_p50_latency_ms": round(float(r.p50), 2) if r.p50 else 0.0,
                        "p90_latency_ms": round(float(r.p90), 2) if r.p90 else 0.0,
                        "p95_latency_ms": round(float(r.p95), 2) if r.p95 else 0.0,
                        "p99_latency_ms": round(float(r.p99), 2) if r.p99 else 0.0,
                        "min_latency_ms": round(float(r.min_lat), 2) if r.min_lat else 0.0,
                        "max_latency_ms": round(float(r.max_lat), 2) if r.max_lat else 0.0,
                    },
                }
            )
        return summaries

    async def _get_telemetry_summary_fallback(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """SQLite / Dialect Fallback: Single GROUP BY query for counts/aggregates + grouped latencies."""
        stmt = (
            select(
                TraceEventModel.service,
                func.count(TraceEventModel.event_id).label("total_events"),
                func.sum(case((TraceEventModel.status == "FAILURE", 1), else_=0)).label("failures"),
                func.sum(case((TraceEventModel.status == "TIMEOUT", 1), else_=0)).label("timeouts"),
                func.sum(case((TraceEventModel.status == "RETRY", 1), else_=0)).label("retries"),
                func.count(case((TraceEventModel.latency_ms > 0.0, 1), else_=None)).label(
                    "lat_count"
                ),
                func.avg(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                ).label("mean_lat"),
                func.min(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                ).label("min_lat"),
                func.max(
                    case((TraceEventModel.latency_ms > 0.0, TraceEventModel.latency_ms), else_=None)
                ).label("max_lat"),
            )
            .group_by(TraceEventModel.service)
            .order_by(TraceEventModel.service.asc())
        )

        if start_time:
            stmt = stmt.where(TraceEventModel.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(TraceEventModel.timestamp <= end_time)

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return []

        lat_stmt = select(TraceEventModel.service, TraceEventModel.latency_ms).where(
            TraceEventModel.latency_ms > 0.0
        )
        if start_time:
            lat_stmt = lat_stmt.where(TraceEventModel.timestamp >= start_time)
        if end_time:
            lat_stmt = lat_stmt.where(TraceEventModel.timestamp <= end_time)

        lat_rows = (await self.session.execute(lat_stmt)).all()
        service_latencies: dict[str, list[float]] = {}
        for s_row in lat_rows:
            svc_name = str(s_row[0])
            val = float(s_row[1])
            if svc_name not in service_latencies:
                service_latencies[svc_name] = []
            service_latencies[svc_name].append(val)

        summaries = []
        for r in rows:
            svc = str(r.service)
            tot = int(r.total_events or 0)
            fail = int(r.failures or 0)
            tout = int(r.timeouts or 0)
            ret = int(r.retries or 0)
            l_count = int(r.lat_count or 0)

            error_rate = (fail / tot * 100.0) if tot > 0 else 0.0
            retry_rate = (ret / tot * 100.0) if tot > 0 else 0.0
            timeout_rate = (tout / tot * 100.0) if tot > 0 else 0.0

            lat_arr = service_latencies.get(svc, [])
            if lat_arr:
                p50 = float(np.percentile(lat_arr, 50))
                p90 = float(np.percentile(lat_arr, 90))
                p95 = float(np.percentile(lat_arr, 95))
                p99 = float(np.percentile(lat_arr, 99))
                min_l = float(np.min(lat_arr))
                max_l = float(np.max(lat_arr))
                mean_l = float(np.mean(lat_arr))
            else:
                p50 = p90 = p95 = p99 = min_l = max_l = mean_l = 0.0

            summaries.append(
                {
                    "service": svc,
                    "total_events": tot,
                    "failure_count": fail,
                    "error_rate_percent": round(error_rate, 2),
                    "retry_count": ret,
                    "retry_rate_percent": round(retry_rate, 2),
                    "timeout_count": tout,
                    "timeout_rate_percent": round(timeout_rate, 2),
                    "latency": {
                        "service": svc,
                        "count": l_count,
                        "mean_latency_ms": round(mean_l, 2),
                        "median_p50_latency_ms": round(p50, 2),
                        "p90_latency_ms": round(p90, 2),
                        "p95_latency_ms": round(p95, 2),
                        "p99_latency_ms": round(p99, 2),
                        "min_latency_ms": round(min_l, 2),
                        "max_latency_ms": round(max_l, 2),
                    },
                }
            )
        return summaries

    async def get_service_telemetry_summary(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Produce telemetry health summary aggregated across all distinct services in a single database pass."""
        dialect_name = self.session.bind.dialect.name if self.session.bind else "postgresql"
        if dialect_name == "postgresql":
            return await self._get_telemetry_summary_pg(start_time, end_time)
        return await self._get_telemetry_summary_fallback(start_time, end_time)
