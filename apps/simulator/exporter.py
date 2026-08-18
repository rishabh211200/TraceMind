"""Dataset export module supporting high-throughput JSONL and Parquet serialization."""

import json
from pathlib import Path

import pandas as pd

from apps.simulator.config import ExportFormat
from apps.simulator.workflow_engine import SimulationResult


class DatasetExporter:
    """Exports simulated workflow traces, executions, and incidents to disk."""

    def __init__(self, output_dir: Path = Path("data/generated")) -> None:
        self.output_dir = Path(output_dir)

    def export(
        self,
        result: SimulationResult,
        export_format: ExportFormat = ExportFormat.ALL,
    ) -> dict[str, Path]:
        """Export simulation datasets to the configured target directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        exported_files: dict[str, Path] = {}

        # 1. JSONL Export
        if export_format in [ExportFormat.JSONL, ExportFormat.ALL]:
            exec_jsonl_path = self.output_dir / "executions.jsonl"
            with open(exec_jsonl_path, "w", encoding="utf-8") as f:
                for item in result.executions:
                    f.write(item.model_dump_json() + "\n")
            exported_files["executions_jsonl"] = exec_jsonl_path

            events_jsonl_path = self.output_dir / "events.jsonl"
            with open(events_jsonl_path, "w", encoding="utf-8") as f:
                for ev in result.events:
                    f.write(ev.model_dump_json() + "\n")
            exported_files["events_jsonl"] = events_jsonl_path

            incidents_jsonl_path = self.output_dir / "incidents.jsonl"
            with open(incidents_jsonl_path, "w", encoding="utf-8") as f:
                for inc in result.incidents:
                    f.write(inc.model_dump_json() + "\n")
            exported_files["incidents_jsonl"] = incidents_jsonl_path

        # 2. Parquet Export
        if export_format in [ExportFormat.PARQUET, ExportFormat.ALL]:
            # Convert executions
            exec_records = [
                {
                    "id": e.id,
                    "workflow_definition_id": e.workflow_definition_id,
                    "started_at": e.started_at,
                    "completed_at": e.completed_at,
                    "status": str(e.status),
                    "total_latency_ms": e.total_latency_ms,
                    "retry_count": e.retry_count,
                    "error_count": e.error_count,
                    "failure_reason": e.failure_reason,
                    "metadata": json.dumps(e.metadata),
                }
                for e in result.executions
            ]
            if exec_records:
                exec_df = pd.DataFrame(exec_records)
                exec_parquet_path = self.output_dir / "executions.parquet"
                exec_df.to_parquet(exec_parquet_path, index=False, engine="pyarrow")
                exported_files["executions_parquet"] = exec_parquet_path

            # Convert events
            event_records = [
                {
                    "event_id": ev.event_id,
                    "execution_id": ev.execution_id,
                    "workflow_id": ev.workflow_id,
                    "timestamp": ev.timestamp,
                    "service": ev.service,
                    "operation": ev.operation,
                    "event_type": str(ev.event_type),
                    "status": str(ev.status),
                    "latency_ms": ev.latency_ms,
                    "parent_event_id": ev.parent_event_id,
                    "correlation_id": ev.correlation_id,
                    "metadata": json.dumps(ev.metadata),
                }
                for ev in result.events
            ]
            if event_records:
                events_df = pd.DataFrame(event_records)
                events_parquet_path = self.output_dir / "events.parquet"
                events_df.to_parquet(events_parquet_path, index=False, engine="pyarrow")
                exported_files["events_parquet"] = events_parquet_path

            # Convert incidents
            inc_records = [
                {
                    "id": inc.id,
                    "scenario_type": str(inc.scenario_type),
                    "severity": str(inc.severity),
                    "started_at": inc.started_at,
                    "ended_at": inc.ended_at,
                    "affected_services": json.dumps(inc.affected_services),
                    "ground_truth_root_cause": inc.ground_truth_root_cause,
                    "description": inc.description,
                    "parameters": json.dumps(inc.parameters),
                }
                for inc in result.incidents
            ]
            if inc_records:
                inc_df = pd.DataFrame(inc_records)
                inc_parquet_path = self.output_dir / "incidents.parquet"
                inc_df.to_parquet(inc_parquet_path, index=False, engine="pyarrow")
                exported_files["incidents_parquet"] = inc_parquet_path

        return exported_files
