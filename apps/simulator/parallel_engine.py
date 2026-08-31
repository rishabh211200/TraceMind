"""High-Performance Multiprocess Trace Simulator for 1M+ Execution Scale."""

import concurrent.futures
import math
import os
import time
from collections.abc import Generator
from dataclasses import dataclass

from apps.simulator.config import IncidentScenario, SimulationConfig
from apps.simulator.workflow_engine import TraceSimulator
from packages.common.logging import get_logger
from packages.common.profiler import PerformanceProfiler, get_current_process_rss_mb
from packages.domain.events import TraceEvent
from packages.domain.workflow import WorkflowExecution

logger = get_logger("tracemind.simulator.parallel")


def _simulate_chunk_worker(
    chunk_index: int,
    chunk_size: int,
    base_seed: int,
    incident_probability: float,
    incident_scenario: IncidentScenario | str | None,
) -> tuple[int, int, float]:
    """Top-level worker function executing a single deterministic simulation chunk."""
    # Deterministic chunk seed derivation
    chunk_seed = base_seed + (chunk_index * 1000)
    sc = (
        IncidentScenario(incident_scenario)
        if isinstance(incident_scenario, str)
        else incident_scenario
    )
    config = SimulationConfig(
        workflow_count=chunk_size,
        seed=chunk_seed,
        incident_probability=incident_probability,
        incident_scenario=sc,
    )
    start = time.perf_counter()
    simulator = TraceSimulator(config=config)
    result = simulator.run()
    elapsed = time.perf_counter() - start

    return len(result.executions), len(result.events), elapsed


def _simulate_chunk_data_worker(
    chunk_index: int,
    chunk_size: int,
    base_seed: int,
    incident_probability: float,
    incident_scenario: IncidentScenario | str | None,
) -> tuple[list[WorkflowExecution], list[TraceEvent]]:
    """Worker function returning generated execution models and trace events for streaming pipeline."""
    chunk_seed = base_seed + (chunk_index * 1000)
    sc = (
        IncidentScenario(incident_scenario)
        if isinstance(incident_scenario, str)
        else incident_scenario
    )
    config = SimulationConfig(
        workflow_count=chunk_size,
        seed=chunk_seed,
        incident_probability=incident_probability,
        incident_scenario=sc,
    )
    simulator = TraceSimulator(config=config)
    result = simulator.run()
    return result.executions, result.events


@dataclass
class ParallelSimulationSummary:
    """Statistical summary of large-scale parallel simulation run."""

    total_executions: int
    total_events: int
    num_chunks: int
    chunk_size: int
    workers_used: int
    wall_clock_seconds: float
    throughput_executions_per_sec: float
    throughput_events_per_sec: float
    peak_rss_mb: float
    chunk_durations_ms: list[float]


class MultiprocessTraceSimulator:
    """Scalable parallel trace simulation engine for 10K to 1M+ distributed executions."""

    def __init__(
        self,
        base_seed: int = 42,
        incident_probability: float = 0.05,
        incident_scenario: str | None = None,
        max_workers: int | None = None,
    ) -> None:
        self.base_seed = base_seed
        self.incident_probability = incident_probability
        self.incident_scenario = incident_scenario
        self.max_workers = max_workers or max(1, os.cpu_count() or 1)

    def run_parallel(
        self,
        total_executions: int = 1_000_000,
        chunk_size: int = 50_000,
        workers: int | None = None,
    ) -> ParallelSimulationSummary:
        """Execute parallel trace simulation using worker pool and bounded memory."""
        active_workers = workers or self.max_workers
        num_chunks = math.ceil(total_executions / chunk_size)

        profiler = PerformanceProfiler(
            name=f"Parallel Simulation ({total_executions:,} execs)",
            total_items=total_executions,
            parallel_workers=active_workers,
        ).start()

        chunk_durations_ms: list[float] = []
        total_events_generated = 0
        total_execs_generated = 0

        # Construct deterministic chunk arguments
        chunk_tasks: list[tuple[int, int, int, float, str | None]] = []
        remaining = total_executions
        for idx in range(num_chunks):
            count = min(chunk_size, remaining)
            chunk_tasks.append(
                (idx, count, self.base_seed, self.incident_probability, self.incident_scenario)
            )
            remaining -= count

        # Execute chunks across process pool
        if active_workers == 1:
            # Single-threaded execution baseline
            for task in chunk_tasks:
                exec_count, event_count, duration = _simulate_chunk_worker(*task)
                total_execs_generated += exec_count
                total_events_generated += event_count
                chunk_durations_ms.append(duration * 1000.0)
        else:
            try:
                with concurrent.futures.ProcessPoolExecutor(max_workers=active_workers) as executor:
                    futures = [
                        executor.submit(_simulate_chunk_worker, *task) for task in chunk_tasks
                    ]
                    for fut in concurrent.futures.as_completed(futures):
                        exec_count, event_count, duration = fut.result()
                        total_execs_generated += exec_count
                        total_events_generated += event_count
                        chunk_durations_ms.append(duration * 1000.0)
            except (PermissionError, OSError):
                # Fallback for restricted OS environments where multiprocessing IPC named pipes are disallowed
                for task in chunk_tasks:
                    exec_count, event_count, duration = _simulate_chunk_worker(*task)
                    total_execs_generated += exec_count
                    total_events_generated += event_count
                    chunk_durations_ms.append(duration * 1000.0)

        profile_res = profiler.stop()

        events_per_sec = total_events_generated / max(0.00001, profile_res.wall_clock_seconds)
        execs_per_sec = total_execs_generated / max(0.00001, profile_res.wall_clock_seconds)

        return ParallelSimulationSummary(
            total_executions=total_execs_generated,
            total_events=total_events_generated,
            num_chunks=num_chunks,
            chunk_size=chunk_size,
            workers_used=active_workers,
            wall_clock_seconds=profile_res.wall_clock_seconds,
            throughput_executions_per_sec=execs_per_sec,
            throughput_events_per_sec=events_per_sec,
            peak_rss_mb=get_current_process_rss_mb(),
            chunk_durations_ms=chunk_durations_ms,
        )

    def stream_chunks(
        self,
        total_executions: int = 1_000_000,
        chunk_size: int = 50_000,
    ) -> Generator[tuple[int, list[WorkflowExecution], list[TraceEvent]], None, None]:
        """Stream simulated execution chunks sequentially to guarantee memory bounded under 2GB."""
        num_chunks = math.ceil(total_executions / chunk_size)
        remaining = total_executions

        for idx in range(num_chunks):
            count = min(chunk_size, remaining)
            executions, events = _simulate_chunk_data_worker(
                idx, count, self.base_seed, self.incident_probability, self.incident_scenario
            )
            yield idx, executions, events
            remaining -= count
