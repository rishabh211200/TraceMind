"""Integration test for DatasetIngestor pipeline and idempotency."""

from pathlib import Path

import pytest

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor
from packages.database.repositories.service_repository import ServiceRepository
from packages.database.repositories.trace_event_repository import TraceEventRepository
from packages.database.repositories.workflow_repository import WorkflowRepository


@pytest.mark.asyncio
async def test_dataset_ingestion_and_idempotency(test_db_session, temp_dir: Path):
    """Verify that TraceSim parquet datasets are ingested accurately and idempotently."""
    out_dir = temp_dir / "sim_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate realistic dataset (100 workflows)
    cfg = SimulationConfig(
        seed=42,
        workflow_count=100,
        output_dir=out_dir,
        export_format=ExportFormat.ALL,
    )
    simulator = TraceSimulator(cfg)
    sim_result = simulator.run()

    exporter = DatasetExporter(out_dir)
    exporter.export(sim_result, ExportFormat.ALL)

    assert len(sim_result.executions) == 100
    assert len(sim_result.events) > 1000

    # 2. Run Ingestion Pipeline
    ingestor = DatasetIngestor(test_db_session)
    report1 = await ingestor.ingest_all(out_dir)

    assert report1.executions_count == 100
    assert report1.events_count == len(sim_result.events)
    assert report1.services_count >= 7

    # 3. Verify Database State
    wf_repo = WorkflowRepository(test_db_session)
    ev_repo = TraceEventRepository(test_db_session)
    svc_repo = ServiceRepository(test_db_session)

    count_execs_1 = await wf_repo.count_executions()
    assert count_execs_1 == 100

    services = await svc_repo.list_services()
    assert len(services) >= 7

    # Check sample execution
    sample_exec = await wf_repo.get_execution("exec_42_000000")
    assert sample_exec is not None
    assert sample_exec.workflow_definition_id == "order_fulfillment"

    # Check sample trace events
    events = await ev_repo.get_trace_events("exec_42_000000")
    assert len(events) > 0
    assert events[0].event_type == "WORKFLOW_STARTED"

    # 4. IDEMPOTENCY TEST: Ingest again
    report2 = await ingestor.ingest_all(out_dir)
    count_execs_2 = await wf_repo.count_executions()

    assert count_execs_2 == count_execs_1
    assert report2.executions_count == 100
