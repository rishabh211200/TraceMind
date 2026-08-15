"""Simulation statistics calculation and reporting."""

from typing import Any

import numpy as np

from apps.simulator.workflow_engine import SimulationResult
from packages.domain.events import EventStatus
from packages.domain.workflow import ExecutionStatus


class SimulationStats:
    """Computes comprehensive performance, reliability, and incident metrics."""

    def __init__(self, result: SimulationResult) -> None:
        self.result = result
        self.total_workflows = len(result.executions)
        self.successful_workflows = sum(
            1 for e in result.executions if e.status == ExecutionStatus.COMPLETED
        )
        self.failed_workflows = sum(
            1 for e in result.executions if e.status == ExecutionStatus.FAILED
        )
        self.success_rate = (
            (self.successful_workflows / self.total_workflows * 100.0)
            if self.total_workflows > 0
            else 0.0
        )
        self.failure_rate = 100.0 - self.success_rate

        # Latency statistics (ms)
        latencies = [e.total_latency_ms for e in result.executions]
        if latencies:
            self.avg_latency_ms = round(float(np.mean(latencies)), 2)
            self.median_latency_ms = round(float(np.median(latencies)), 2)
            self.p90_latency_ms = round(float(np.percentile(latencies, 90)), 2)
            self.p95_latency_ms = round(float(np.percentile(latencies, 95)), 2)
            self.p99_latency_ms = round(float(np.percentile(latencies, 99)), 2)
            self.min_latency_ms = round(float(np.min(latencies)), 2)
            self.max_latency_ms = round(float(np.max(latencies)), 2)
        else:
            self.avg_latency_ms = 0.0
            self.median_latency_ms = 0.0
            self.p90_latency_ms = 0.0
            self.p95_latency_ms = 0.0
            self.p99_latency_ms = 0.0
            self.min_latency_ms = 0.0
            self.max_latency_ms = 0.0

        # Reliability & Retries
        self.total_retries = sum(e.retry_count for e in result.executions)
        self.avg_retries_per_wf = (
            round(self.total_retries / self.total_workflows, 3) if self.total_workflows > 0 else 0.0
        )
        self.timeout_events_count = sum(
            1 for ev in result.events if ev.status == EventStatus.TIMEOUT
        )
        self.total_events = len(result.events)
        self.avg_events_per_wf = (
            round(self.total_events / self.total_workflows, 2) if self.total_workflows > 0 else 0.0
        )

        # Incident breakdown
        self.total_incidents = len(result.incidents)
        self.incident_types = [str(inc.scenario_type) for inc in result.incidents]

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to structured dictionary."""
        return {
            "total_workflows": self.total_workflows,
            "successful_workflows": self.successful_workflows,
            "failed_workflows": self.failed_workflows,
            "success_rate_percent": round(self.success_rate, 2),
            "failure_rate_percent": round(self.failure_rate, 2),
            "latency_ms": {
                "mean": self.avg_latency_ms,
                "median_p50": self.median_latency_ms,
                "p90": self.p90_latency_ms,
                "p95": self.p95_latency_ms,
                "p99": self.p99_latency_ms,
                "min": self.min_latency_ms,
                "max": self.max_latency_ms,
            },
            "reliability": {
                "total_retries": self.total_retries,
                "avg_retries_per_workflow": self.avg_retries_per_wf,
                "timeout_count": self.timeout_events_count,
            },
            "events": {
                "total_events": self.total_events,
                "avg_events_per_workflow": self.avg_events_per_wf,
            },
            "incidents": {
                "total_injected": self.total_incidents,
                "scenarios": self.incident_types,
            },
        }

    def render_summary(self) -> str:
        """Produce a formatted console report."""
        lines = [
            "=================================================================",
            "             TraceMind Simulation Summary Report                 ",
            "=================================================================",
            f" Seed                     : {self.result.config.seed}",
            f" Total Workflows Simulated: {self.total_workflows:,}",
            f" Successful Workflows     : {self.successful_workflows:,} ({self.success_rate:.2f}%)",
            f" Failed Workflows         : {self.failed_workflows:,} ({self.failure_rate:.2f}%)",
            "-----------------------------------------------------------------",
            " Latency Distribution (ms):",
            f"   * Mean                 : {self.avg_latency_ms:,.2f} ms",
            f"   * Median (P50)         : {self.median_latency_ms:,.2f} ms",
            f"   * 90th Percentile (P90): {self.p90_latency_ms:,.2f} ms",
            f"   * 95th Percentile (P95): {self.p95_latency_ms:,.2f} ms",
            f"   * 99th Percentile (P99): {self.p99_latency_ms:,.2f} ms",
            f"   * Min / Max            : {self.min_latency_ms:,.2f} ms / {self.max_latency_ms:,.2f} ms",
            "-----------------------------------------------------------------",
            " Reliability & Operational Metrics:",
            f"   * Total Retries        : {self.total_retries:,} (Avg: {self.avg_retries_per_wf:.3f}/wf)",
            f"   * Timeout Events       : {self.timeout_events_count:,}",
            f"   * Trace Events Emitted : {self.total_events:,} (Avg: {self.avg_events_per_wf:.1f}/wf)",
            f"   * Incidents Injected   : {self.total_incidents:,}",
        ]
        if self.result.incidents:
            lines.append("   * Injected Scenarios   :")
            for inc in self.result.incidents:
                lines.append(
                    f"       - [{inc.severity}] {inc.scenario_type}: {inc.ground_truth_root_cause}"
                )
        lines.append("=================================================================")
        return "\n".join(lines)
