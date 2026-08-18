"""High-performance dataset ingestion pipeline for TraceSim Parquet & JSONL datasets."""

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.simulator.config import get_default_service_configs
from packages.common.logging import get_logger
from packages.database.models.incident import IncidentModel
from packages.database.models.service import ServiceModel
from packages.database.models.trace_event import TraceEventModel
from packages.database.models.workflow import (
    WorkflowDefinitionModel,
    WorkflowExecutionModel,
)
from packages.database.session import get_async_engine, get_async_session_factory, init_db

logger = get_logger("tracemind.ingestion")


class IngestionReport:
    """Summary metrics of dataset ingestion run."""

    def __init__(
        self,
        services_count: int,
        workflow_definitions_count: int,
        incidents_count: int,
        executions_count: int,
        events_count: int,
        duration_seconds: float,
    ) -> None:
        self.services_count = services_count
        self.workflow_definitions_count = workflow_definitions_count
        self.incidents_count = incidents_count
        self.executions_count = executions_count
        self.events_count = events_count
        self.duration_seconds = duration_seconds
        self.events_per_sec = (
            round(events_count / duration_seconds, 2) if duration_seconds > 0 else 0.0
        )
        self.workflows_per_sec = (
            round(executions_count / duration_seconds, 2) if duration_seconds > 0 else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "services_ingested": self.services_count,
            "workflow_definitions_ingested": self.workflow_definitions_count,
            "incidents_ingested": self.incidents_count,
            "executions_ingested": self.executions_count,
            "events_ingested": self.events_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "events_per_second": self.events_per_sec,
            "workflows_per_second": self.workflows_per_sec,
        }

    def render_summary(self) -> str:
        """Produce formatted console summary."""
        lines = [
            "=================================================================",
            "             TraceMind Telemetry Ingestion Report                ",
            "=================================================================",
            f" Services Registered      : {self.services_count}",
            f" Workflow Definitions     : {self.workflow_definitions_count}",
            f" Incidents Ingested       : {self.incidents_count:,}",
            f" Executions Ingested      : {self.executions_count:,}",
            f" Trace Events Ingested    : {self.events_count:,}",
            "-----------------------------------------------------------------",
            f" Wall Time                : {self.duration_seconds:.2f}s",
            f" Event Ingestion Speed    : {self.events_per_sec:,.0f} events/sec",
            f" Workflow Ingestion Speed : {self.workflows_per_sec:,.0f} workflows/sec",
            "=================================================================",
        ]
        return "\n".join(lines)


class DatasetIngestor:
    """Ingests generated Parquet and JSONL datasets into PostgreSQL/TimescaleDB."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed_metadata_and_topology(self) -> tuple[int, int]:
        """Seed default service profiles and workflow topology definition."""
        svc_configs = get_default_service_configs()
        # Include infrastructure dependencies in services catalog
        infra_services = [
            ServiceModel(
                name="customer-cache",
                service_type="infrastructure_cache",
                capacity=1000,
                baseline_latency_ms=3.0,
                baseline_failure_rate=0.0,
            ),
            ServiceModel(
                name="customer-db",
                service_type="infrastructure_database",
                capacity=200,
                baseline_latency_ms=35.0,
                baseline_failure_rate=0.002,
            ),
            ServiceModel(
                name="inventory-db",
                service_type="infrastructure_database",
                capacity=200,
                baseline_latency_ms=25.0,
                baseline_failure_rate=0.002,
            ),
            ServiceModel(
                name="payment-gateway",
                service_type="infrastructure_gateway",
                capacity=150,
                baseline_latency_ms=65.0,
                baseline_failure_rate=0.005,
            ),
            ServiceModel(
                name="api-gateway",
                service_type="api_gateway",
                capacity=2000,
                baseline_latency_ms=1.0,
                baseline_failure_rate=0.0,
            ),
        ]

        services_to_insert = [
            ServiceModel(
                name=cfg.name,
                service_type="business_microservice",
                capacity=cfg.capacity,
                baseline_latency_ms=cfg.baseline_latency_ms,
                baseline_failure_rate=cfg.baseline_failure_rate,
                timeout_ms=cfg.timeout_ms,
                max_retries=cfg.max_retries,
                retry_backoff_ms=cfg.retry_backoff_ms,
                dependencies=cfg.dependencies,
                metadata_=cfg.metadata,
            )
            for cfg in svc_configs.values()
        ] + infra_services

        for svc in services_to_insert:
            await self.session.merge(svc)

        # Seed default workflow definition
        wf_def = WorkflowDefinitionModel(
            id="order_fulfillment",
            name="Distributed Order Fulfillment Pipeline",
            version="1.0.0",
            description="End-to-end commerce checkout and fulfillment across 7 microservices",
            nodes=[
                {"id": "auth", "service": "auth-service", "operation": "authenticate_user"},
                {
                    "id": "customer",
                    "service": "customer-service",
                    "operation": "get_customer_profile",
                },
                {
                    "id": "inventory",
                    "service": "inventory-service",
                    "operation": "reserve_inventory",
                },
                {"id": "pricing", "service": "pricing-service", "operation": "calculate_pricing"},
                {"id": "payment", "service": "payment-service", "operation": "authorize_payment"},
                {"id": "order", "service": "order-service", "operation": "create_order"},
                {
                    "id": "notification",
                    "service": "notification-service",
                    "operation": "send_notification",
                },
            ],
            edges=[
                {"from": "auth", "to": "customer"},
                {"from": "customer", "to": "inventory"},
                {"from": "inventory", "to": "pricing"},
                {"from": "pricing", "to": "payment"},
                {"from": "payment", "to": "order"},
                {"from": "order", "to": "notification"},
            ],
        )
        await self.session.merge(wf_def)
        await self.session.commit()
        return len(services_to_insert), 1

    async def ingest_incidents(self, input_dir: Path) -> int:
        """Ingest incidents from parquet or jsonl."""
        parquet_path = input_dir / "incidents.parquet"
        jsonl_path = input_dir / "incidents.jsonl"

        records: list[dict[str, Any]] = []
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            for _, row in df.iterrows():
                params = row["parameters"]
                if isinstance(params, str):
                    params = json.loads(params)
                aff_services = row["affected_services"]
                if isinstance(aff_services, str):
                    aff_services = json.loads(aff_services)

                started = pd.to_datetime(row["started_at"]).to_pydatetime()
                ended = pd.to_datetime(row["ended_at"]).to_pydatetime()
                duration = (ended - started).total_seconds()

                records.append(
                    {
                        "id": str(row["id"]),
                        "scenario_type": str(row["scenario_type"]),
                        "severity": str(row["severity"]),
                        "started_at": started,
                        "ended_at": ended,
                        "duration_seconds": duration,
                        "affected_services": aff_services,
                        "ground_truth_root_cause": str(row["ground_truth_root_cause"]),
                        "description": str(row["description"]),
                        "parameters": params,
                        "metadata_": {},
                    }
                )
        elif jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        started = pd.to_datetime(item["started_at"]).to_pydatetime()
                        ended = pd.to_datetime(item["ended_at"]).to_pydatetime()
                        records.append(
                            {
                                "id": str(item["id"]),
                                "scenario_type": str(item["scenario_type"]),
                                "severity": str(item["severity"]),
                                "started_at": started,
                                "ended_at": ended,
                                "duration_seconds": (ended - started).total_seconds(),
                                "affected_services": item["affected_services"],
                                "ground_truth_root_cause": str(item["ground_truth_root_cause"]),
                                "description": str(item["description"]),
                                "parameters": item["parameters"],
                                "metadata_": {},
                            }
                        )

        for r in records:
            inc = IncidentModel(**r)
            await self.session.merge(inc)
        await self.session.commit()
        return len(records)

    async def ingest_executions(self, input_dir: Path, batch_size: int = 2000) -> int:
        """Ingest workflow executions in chunked batches."""
        parquet_path = input_dir / "executions.parquet"
        jsonl_path = input_dir / "executions.jsonl"

        records: list[dict[str, Any]] = []
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            for _, row in df.iterrows():
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                started = pd.to_datetime(row["started_at"]).to_pydatetime()
                completed = (
                    pd.to_datetime(row["completed_at"]).to_pydatetime()
                    if pd.notna(row["completed_at"])
                    else None
                )

                records.append(
                    {
                        "id": str(row["id"]),
                        "workflow_definition_id": str(
                            row.get("workflow_definition_id", "order_fulfillment")
                        ),
                        "started_at": started,
                        "completed_at": completed,
                        "duration_ms": float(row["total_latency_ms"]),
                        "status": str(row["status"]),
                        "retry_count": int(row["retry_count"]),
                        "error_count": int(row["error_count"]),
                        "failure_reason": str(row["failure_reason"])
                        if pd.notna(row["failure_reason"])
                        else None,
                        "incident_id": meta.get("incident_id"),
                        "is_incident_affected": bool(meta.get("is_incident_affected", False)),
                        "metadata_": meta,
                    }
                )
        elif jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        started = pd.to_datetime(item["started_at"]).to_pydatetime()
                        completed = (
                            pd.to_datetime(item["completed_at"]).to_pydatetime()
                            if item.get("completed_at")
                            else None
                        )
                        meta = item.get("metadata", {})
                        records.append(
                            {
                                "id": str(item["id"]),
                                "workflow_definition_id": str(
                                    item.get("workflow_definition_id", "order_fulfillment")
                                ),
                                "started_at": started,
                                "completed_at": completed,
                                "duration_ms": float(item["total_latency_ms"]),
                                "status": str(item["status"]),
                                "retry_count": int(item["retry_count"]),
                                "error_count": int(item["error_count"]),
                                "failure_reason": item.get("failure_reason"),
                                "incident_id": meta.get("incident_id"),
                                "is_incident_affected": bool(
                                    meta.get("is_incident_affected", False)
                                ),
                                "metadata_": meta,
                            }
                        )

        # Batch insert with high-speed insert(Model) and fallback for idempotency
        for i in range(0, len(records), batch_size):
            chunk = records[i : i + batch_size]
            try:
                await self.session.execute(insert(WorkflowExecutionModel), chunk)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                for r in chunk:
                    await self.session.merge(WorkflowExecutionModel(**r))
                await self.session.commit()

        return len(records)

    async def ingest_events(self, input_dir: Path, batch_size: int = 5000) -> int:
        """Ingest trace events in high-throughput chunked batches."""
        parquet_path = input_dir / "events.parquet"
        jsonl_path = input_dir / "events.jsonl"

        records: list[dict[str, Any]] = []
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            for _, row in df.iterrows():
                meta = row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                ts = pd.to_datetime(row["timestamp"]).to_pydatetime()

                records.append(
                    {
                        "event_id": str(row["event_id"]),
                        "timestamp": ts,
                        "execution_id": str(row["execution_id"]),
                        "workflow_id": str(row.get("workflow_id", "order_fulfillment")),
                        "service": str(row["service"]),
                        "operation": str(row["operation"]),
                        "event_type": str(row["event_type"]),
                        "status": str(row["status"]),
                        "latency_ms": float(row["latency_ms"]),
                        "parent_event_id": str(row["parent_event_id"])
                        if pd.notna(row["parent_event_id"])
                        else None,
                        "correlation_id": str(row["correlation_id"])
                        if pd.notna(row["correlation_id"])
                        else None,
                        "metadata_": meta,
                    }
                )
        elif jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        ts = pd.to_datetime(item["timestamp"]).to_pydatetime()
                        records.append(
                            {
                                "event_id": str(item["event_id"]),
                                "timestamp": ts,
                                "execution_id": str(item["execution_id"]),
                                "workflow_id": str(item.get("workflow_id", "order_fulfillment")),
                                "service": str(item["service"]),
                                "operation": str(item["operation"]),
                                "event_type": str(item["event_type"]),
                                "status": str(item["status"]),
                                "latency_ms": float(item["latency_ms"]),
                                "parent_event_id": item.get("parent_event_id"),
                                "correlation_id": item.get("correlation_id"),
                                "metadata_": item.get("metadata", {}),
                            }
                        )

        # Batch insert with high-speed insert(Model) and fallback for idempotency
        for i in range(0, len(records), batch_size):
            chunk = records[i : i + batch_size]
            try:
                await self.session.execute(insert(TraceEventModel), chunk)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                for r in chunk:
                    await self.session.merge(TraceEventModel(**r))
                await self.session.commit()

        return len(records)

    async def ingest_all(self, input_dir: Path, batch_size: int = 5000) -> IngestionReport:
        """Run end-to-end ingestion pipeline."""
        start_time = time.perf_counter()
        input_dir = Path(input_dir)

        svc_count, wf_count = await self.seed_metadata_and_topology()
        inc_count = await self.ingest_incidents(input_dir)
        exec_count = await self.ingest_executions(input_dir, batch_size=batch_size)
        events_count = await self.ingest_events(input_dir, batch_size=batch_size)

        duration = time.perf_counter() - start_time
        return IngestionReport(
            services_count=svc_count,
            workflow_definitions_count=wf_count,
            incidents_count=inc_count,
            executions_count=exec_count,
            events_count=events_count,
            duration_seconds=duration,
        )

    async def ingest_simulation_result(
        self, result: Any, batch_size: int = 5000
    ) -> IngestionReport:
        """Directly ingest in-memory SimulationResult into the database."""
        start_time = time.perf_counter()
        svc_count, wf_count = await self.seed_metadata_and_topology()

        # Ingest incidents
        for inc in result.incidents:
            duration = (inc.ended_at - inc.started_at).total_seconds() if inc.ended_at else 0.0
            rec = {
                "id": inc.id,
                "scenario_type": str(
                    inc.scenario_type.value
                    if hasattr(inc.scenario_type, "value")
                    else inc.scenario_type
                ),
                "severity": str(
                    inc.severity.value if hasattr(inc.severity, "value") else inc.severity
                ),
                "started_at": inc.started_at,
                "ended_at": inc.ended_at,
                "duration_seconds": duration,
                "affected_services": inc.affected_services,
                "ground_truth_root_cause": inc.ground_truth_root_cause,
                "description": inc.description,
                "parameters": inc.parameters,
                "metadata_": {},
            }
            await self.session.merge(IncidentModel(**rec))
        await self.session.commit()
        inc_count = len(result.incidents)

        # Ingest executions
        exec_records = []
        for item in result.executions:
            meta = item.metadata or {}
            status_val = item.status.value if hasattr(item.status, "value") else str(item.status)
            exec_records.append(
                {
                    "id": str(item.id),
                    "workflow_definition_id": str(
                        item.workflow_definition_id or "order_fulfillment"
                    ),
                    "started_at": item.started_at,
                    "completed_at": item.completed_at,
                    "duration_ms": float(item.total_latency_ms),
                    "status": status_val,
                    "retry_count": int(item.retry_count),
                    "error_count": int(item.error_count),
                    "failure_reason": item.failure_reason,
                    "incident_id": meta.get("incident_id"),
                    "is_incident_affected": bool(meta.get("is_incident_affected", False)),
                    "metadata_": meta,
                }
            )

        for i in range(0, len(exec_records), batch_size):
            chunk = exec_records[i : i + batch_size]
            try:
                await self.session.execute(insert(WorkflowExecutionModel), chunk)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                for r in chunk:
                    await self.session.merge(WorkflowExecutionModel(**r))
                await self.session.commit()

        # Ingest events
        event_records = []
        for ev in result.events:
            ev_type = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            ev_status = ev.status.value if hasattr(ev.status, "value") else str(ev.status)
            event_records.append(
                {
                    "event_id": str(ev.event_id),
                    "timestamp": ev.timestamp,
                    "execution_id": str(ev.execution_id),
                    "workflow_id": str(ev.workflow_id or "order_fulfillment"),
                    "service": str(ev.service),
                    "operation": str(ev.operation),
                    "event_type": ev_type,
                    "status": ev_status,
                    "latency_ms": float(ev.latency_ms),
                    "parent_event_id": ev.parent_event_id,
                    "correlation_id": ev.correlation_id,
                    "metadata_": ev.metadata or {},
                }
            )

        for i in range(0, len(event_records), batch_size):
            chunk_ev = event_records[i : i + batch_size]
            try:
                await self.session.execute(insert(TraceEventModel), chunk_ev)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                for r in chunk_ev:
                    await self.session.merge(TraceEventModel(**r))
                await self.session.commit()

        duration = time.perf_counter() - start_time
        return IngestionReport(
            services_count=svc_count,
            workflow_definitions_count=wf_count,
            incidents_count=inc_count,
            executions_count=len(exec_records),
            events_count=len(event_records),
            duration_seconds=duration,
        )


async def run_ingestion_cli(
    input_dir: str = "data/generated", batch_size: int = 5000
) -> IngestionReport:
    """CLI runner function for dataset ingestion."""
    engine = get_async_engine()
    await init_db(engine)
    session_factory = get_async_session_factory(engine)

    async with session_factory() as session:
        ingestor = DatasetIngestor(session)
        report = await ingestor.ingest_all(Path(input_dir), batch_size=batch_size)
        print(report.render_summary())
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TraceMind Telemetry Ingestion Pipeline")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/generated",
        help="Directory with generated Parquet/JSONL",
    )
    parser.add_argument("--batch-size", type=int, default=5000, help="Ingestion batch size")
    args = parser.parse_args()

    asyncio.run(run_ingestion_cli(input_dir=args.input_dir, batch_size=args.batch_size))
