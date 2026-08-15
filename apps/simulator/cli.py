"""Command-line interface for running TraceSim simulations and exporting datasets."""

import argparse
import sys
import time
from pathlib import Path

from apps.simulator.config import (
    WORKLOAD_SIZES,
    ExportFormat,
    SimulationConfig,
    WorkloadPreset,
)
from apps.simulator.exporter import DatasetExporter
from apps.simulator.stats import SimulationStats
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.incident import IncidentScenario

SCENARIO_MAP: dict[str, IncidentScenario | None] = {
    "none": None,
    "traffic_spike": IncidentScenario.TRAFFIC_SPIKE,
    "database_latency": IncidentScenario.DATABASE_LATENCY,
    "payment_degradation": IncidentScenario.PAYMENT_LATENCY_DEGRADATION,
    "service_failure": IncidentScenario.SERVICE_FAILURE,
    "network_latency": IncidentScenario.NETWORK_LATENCY,
    "retry_storm": IncidentScenario.RETRY_STORM,
    "cascading_failure": IncidentScenario.CASCADING_FAILURE,
}


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="TraceSim",
        description="Deterministic Synthetic Distributed-System Workflow Simulator",
    )
    parser.add_argument(
        "--workflows",
        type=int,
        default=None,
        help="Total workflow executions to simulate (e.g. 10000)",
    )
    parser.add_argument(
        "--workload",
        type=str,
        choices=["small", "medium", "large", "custom"],
        default="custom",
        help="Predefined workload preset (small=1k, medium=10k, large=100k)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic pseudo-random seed (default: 42)",
    )
    parser.add_argument(
        "--incident",
        type=str,
        choices=list(SCENARIO_MAP.keys()),
        default="none",
        help="Explicit incident scenario to inject into simulation run",
    )
    parser.add_argument(
        "--incident-probability",
        type=float,
        default=0.05,
        help="Stochastic probability of incident occurrence (default: 0.05)",
    )
    parser.add_argument(
        "--arrival-rate",
        type=float,
        default=20.0,
        help="Nominal workflows initiated per simulated second (default: 20.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Directory to save exported JSONL and Parquet datasets (default: data/generated)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["all", "jsonl", "parquet"],
        default="all",
        help="Dataset serialization format (default: all)",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Run simulation in-memory without writing datasets to disk",
    )
    return parser


def run_cli(args: list[str] | None = None) -> int:
    """CLI execution entrypoint."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    # Determine workflow count
    preset_str = parsed_args.workload.upper()
    preset = WorkloadPreset(preset_str)
    if parsed_args.workflows is not None:
        workflow_count = parsed_args.workflows
    elif preset in WORKLOAD_SIZES:
        workflow_count = WORKLOAD_SIZES[preset]
    else:
        workflow_count = 1000

    selected_scenario = SCENARIO_MAP.get(parsed_args.incident)
    export_fmt = ExportFormat(parsed_args.format.upper())

    config = SimulationConfig(
        seed=parsed_args.seed,
        workflow_count=workflow_count,
        workload_preset=preset,
        arrival_rate_per_second=parsed_args.arrival_rate,
        incident_scenario=selected_scenario,
        incident_probability=0.0
        if selected_scenario is not None
        else parsed_args.incident_probability,
        output_dir=Path(parsed_args.output_dir),
        export_format=export_fmt,
    )

    print("=================================================================")
    print("                    Starting TraceSim Engine                     ")
    print("=================================================================")
    print(f" Seed           : {config.seed}")
    print(f" Target Count   : {config.workflow_count:,} workflows")
    print(f" Incident Mode  : {parsed_args.incident}")
    print(f" Output Dir     : {config.output_dir}")
    print(" Executing discrete-event simulation...\n")

    start_wall_time = time.perf_counter()
    simulator = TraceSimulator(config=config)
    result = simulator.run()
    elapsed_wall_sec = time.perf_counter() - start_wall_time

    # Compute statistics
    stats = SimulationStats(result)
    print(stats.render_summary())
    print(
        f"\n Execution wall time : {elapsed_wall_sec:.2f}s "
        f"({config.workflow_count / max(0.001, elapsed_wall_sec):,.0f} workflows/sec)"
    )

    # Export dataset
    if not parsed_args.no_export:
        exporter = DatasetExporter(output_dir=config.output_dir)
        files = exporter.export(result, export_format=config.export_format)
        print("\n Exported Datasets:")
        for key, path in files.items():
            size_kb = path.stat().st_size / 1024.0
            print(f"   * {key:<20}: {path} ({size_kb:,.1f} KB)")

    print("=================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
