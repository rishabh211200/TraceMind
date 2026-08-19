"""TraceMind Milestone 5 — Streaming Pipeline & Micro-Batching Ingestion Benchmark."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.simulator.config import SimulationConfig
from apps.simulator.streaming import StreamingTraceSimulator
from apps.worker.stream_ingestor import StreamingIngestor
from packages.database.models import Base
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.events.bus import InMemoryEventBus


class BenchAsyncSession:
    """Async session adapter wrapping synchronous Session for in-memory SQLite benchmark."""

    def __init__(self, sync_session: Session) -> None:
        self._sync = sync_session

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self._sync.execute(*args, **kwargs)

    async def commit(self) -> None:
        self._sync.commit()

    async def rollback(self) -> None:
        self._sync.rollback()

    async def merge(self, obj: Any) -> Any:
        return self._sync.merge(obj)

    async def close(self) -> None:
        self._sync.close()


class BenchSessionFactory:
    """Session factory for in-memory SQLite performance testing."""

    def __init__(self, engine):
        self.engine = engine

    def __call__(self):
        return self

    async def __aenter__(self):
        self._sync_session = Session(self.engine)
        return BenchAsyncSession(self._sync_session)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._sync_session.close()


def generate_benchmark_events(count: int = 10000) -> list[TraceEvent]:
    """Generate in-memory synthetic canonical TraceEvent records."""
    events: list[TraceEvent] = []
    now = datetime.now(UTC)
    for i in range(count):
        exec_idx = i // 10
        events.append(
            TraceEvent(
                event_id=f"evt_bench_{i}_{uuid4().hex[:6]}",
                execution_id=f"exec_bench_{exec_idx}",
                workflow_id="order_fulfillment",
                timestamp=now,
                service="payment-service" if i % 2 == 0 else "inventory-service",
                operation="authorize_payment" if i % 2 == 0 else "reserve_inventory",
                event_type=EventType.SERVICE_COMPLETED,
                status=EventStatus.SUCCESS,
                latency_ms=15.4,
                parent_event_id=f"evt_root_{exec_idx}",
                correlation_id=f"corr_{exec_idx}",
                metadata={"batch_run": True, "seq": i},
            )
        )
    return events


async def run_benchmark(event_count: int = 25000, batch_size: int = 1000) -> dict[str, Any]:
    """Execute end-to-end streaming ingestion benchmark."""
    # Setup in-memory database with SQLite StaticPool for microsecond latency testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = BenchSessionFactory(engine)

    bus = InMemoryEventBus()
    ingestor = StreamingIngestor(
        consumer=bus.consumer,
        session_factory=session_factory,  # type: ignore[arg-type]
        batch_size=batch_size,
        flush_interval_ms=20,
    )

    await bus.producer.start()
    await ingestor.start()

    # 1. Producer Benchmark
    print(f"[*] Generating {event_count:,} synthetic trace events...")
    events = generate_benchmark_events(event_count)

    print(f"[*] Benchmarking Producer throughput ({event_count:,} events)...")
    t_prod_start = time.perf_counter()
    await bus.producer.publish_batch(events)
    t_prod_end = time.perf_counter()

    prod_duration = t_prod_end - t_prod_start
    prod_throughput = event_count / prod_duration if prod_duration > 0 else 0.0

    # 2. Consumer Ingestion Benchmark
    print(f"[*] Benchmarking Streaming Ingestor & DB Persistence ({event_count:,} events)...")
    batch_latencies: list[float] = []
    t_ingest_start = time.perf_counter()

    while bus.consumer.committed_count < event_count:
        t_step_start = time.perf_counter()
        flushed = await ingestor.run_step()
        t_step_end = time.perf_counter()
        if flushed > 0:
            batch_latencies.append((t_step_end - t_step_start) * 1000.0)
        await asyncio.sleep(0.0001)

    t_ingest_end = time.perf_counter()
    ingest_duration = t_ingest_end - t_ingest_start
    ingest_throughput = event_count / ingest_duration if ingest_duration > 0 else 0.0

    total_pipeline_time = prod_duration + ingest_duration
    e2e_throughput = event_count / total_pipeline_time if total_pipeline_time > 0 else 0.0

    # 3. Streaming Simulator Integration Benchmark
    print("[*] Benchmarking Streaming TraceSimulator live emission...")
    sim_bus = InMemoryEventBus()
    cfg = SimulationConfig(seed=42, workflow_count=200, arrival_rate_per_second=50.0)
    sim = StreamingTraceSimulator(config=cfg, producer=sim_bus.producer)

    t_sim_start = time.perf_counter()
    sim_result = await sim.run_streaming()
    t_sim_end = time.perf_counter()

    sim_duration = t_sim_end - t_sim_start
    sim_events_count = len(sim_result.events)
    sim_throughput = sim_events_count / sim_duration if sim_duration > 0 else 0.0

    await ingestor.stop()
    await bus.producer.stop()
    Base.metadata.drop_all(engine)

    # Compute percentile latencies
    p50_lat = float(np.percentile(batch_latencies, 50)) if batch_latencies else 0.0
    p95_lat = float(np.percentile(batch_latencies, 95)) if batch_latencies else 0.0
    p99_lat = float(np.percentile(batch_latencies, 99)) if batch_latencies else 0.0
    mean_lat = float(np.mean(batch_latencies)) if batch_latencies else 0.0

    metrics = {
        "event_count": event_count,
        "batch_size": batch_size,
        "producer_duration_s": prod_duration,
        "producer_events_per_sec": prod_throughput,
        "ingest_duration_s": ingest_duration,
        "ingest_events_per_sec": ingest_throughput,
        "e2e_duration_s": total_pipeline_time,
        "e2e_events_per_sec": e2e_throughput,
        "batch_flush_p50_ms": p50_lat,
        "batch_flush_p95_ms": p95_lat,
        "batch_flush_p99_ms": p99_lat,
        "batch_flush_mean_ms": mean_lat,
        "sim_live_events": sim_events_count,
        "sim_live_duration_s": sim_duration,
        "sim_live_events_per_sec": sim_throughput,
    }

    render_report(metrics)
    return metrics


def render_report(m: dict[str, Any]) -> None:
    """Print ASCII formatted performance benchmark report."""
    print("\n" + "=" * 80)
    print("                TraceMind Milestone 5 Streaming Pipeline Benchmark             ")
    print("=" * 80)
    print(f" Total Benchmark Events Processed   : {m['event_count']:,} spans")
    print(f" Micro-Batch Buffer Limit           : {m['batch_size']:,} events / batch")
    print("-" * 80)
    print(
        f" 1. Producer Stream Ingestion Rate  : {m['producer_events_per_sec']:,.0f} events/sec ({m['producer_duration_s']:.3f}s)"
    )
    print(
        f" 2. Consumer & DB Persistence Rate  : {m['ingest_events_per_sec']:,.0f} events/sec ({m['ingest_duration_s']:.3f}s)"
    )
    print(
        f" 3. End-to-End Pipeline Throughput  : {m['e2e_events_per_sec']:,.0f} events/sec ({m['e2e_duration_s']:.3f}s)"
    )
    print(
        f" 4. Simulator Live Stream Rate      : {m['sim_live_events_per_sec']:,.0f} events/sec ({m['sim_live_events']:,} spans in {m['sim_live_duration_s']:.3f}s)"
    )
    print("-" * 80)
    print(" Micro-Batch Flush Latencies (per 1,000-event batch):")
    print(f"   • P50 Flush Latency              : {m['batch_flush_p50_ms']:.2f} ms")
    print(f"   • P95 Flush Latency              : {m['batch_flush_p95_ms']:.2f} ms")
    print(f"   • P99 Flush Latency              : {m['batch_flush_p99_ms']:.2f} ms")
    print(f"   • Mean Flush Latency             : {m['batch_flush_mean_ms']:.2f} ms")
    print("=" * 80)
    target_met = m["ingest_events_per_sec"] >= 5000
    print(
        f" Target Throughput Criteria (>5,000 events/sec) : {'[PASSED]' if target_met else '[FAILED]'}"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark(event_count=25000, batch_size=1000))
