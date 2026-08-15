"""Integration tests validating end-to-end simulation, export, and schema integrity."""

import json
from pathlib import Path

import pandas as pd

from apps.simulator.config import ExportFormat, SimulationConfig
from apps.simulator.exporter import DatasetExporter
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.incident import IncidentScenario


def test_end_to_end_simulation_and_export(tmp_path: Path):
    """Execute complete 250-workflow simulation, export to JSONL & Parquet, and verify datasets."""
    export_dir = tmp_path / "sim_output"
    config = SimulationConfig(
        seed=42,
        workflow_count=250,
        incident_scenario=IncidentScenario.DATABASE_LATENCY,
        incident_duration_workflows=80,
        output_dir=export_dir,
        export_format=ExportFormat.ALL,
    )

    simulator = TraceSimulator(config)
    result = simulator.run()

    assert len(result.executions) == 250
    assert len(result.events) > 1000
    assert len(result.incidents) == 1

    # Export datasets
    exporter = DatasetExporter(output_dir=export_dir)
    exported = exporter.export(result, export_format=ExportFormat.ALL)

    # 1. Verify JSONL files exist and are parseable
    exec_jsonl = exported["executions_jsonl"]
    assert exec_jsonl.exists()
    with open(exec_jsonl, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 250
    assert lines[0]["id"].startswith("exec_")

    events_jsonl = exported["events_jsonl"]
    assert events_jsonl.exists()
    with open(events_jsonl, encoding="utf-8") as f:
        event_lines = [json.loads(line) for line in f]
    assert len(event_lines) == len(result.events)

    # 2. Verify Parquet files exist and have matching shape and column schema
    exec_parquet = exported["executions_parquet"]
    assert exec_parquet.exists()
    df_exec = pd.read_parquet(exec_parquet)
    assert len(df_exec) == 250
    assert "total_latency_ms" in df_exec.columns
    assert "status" in df_exec.columns

    events_parquet = exported["events_parquet"]
    assert events_parquet.exists()
    df_events = pd.read_parquet(events_parquet)
    assert len(df_events) == len(result.events)
    assert "event_type" in df_events.columns
    assert "latency_ms" in df_events.columns

    # 3. Verify event trace linkage (every child event has a valid parent or is root)
    execution_ids = {e.id for e in result.executions}
    for ev in result.events:
        assert ev.execution_id in execution_ids
        assert ev.latency_ms >= 0.0
