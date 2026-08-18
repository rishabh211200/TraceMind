"""High-performance streaming trace ingestion worker with micro-batch persistence."""

import argparse
import asyncio
import signal
import sys
import time
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.common.config import Settings, get_settings
from packages.common.logging import get_logger
from packages.database.models.trace_event import TraceEventModel
from packages.database.session import get_async_engine, get_async_session_factory, init_db
from packages.domain.events import TraceEvent
from packages.events.bus import create_consumer
from packages.events.consumer import AsyncTraceEventConsumer

logger = get_logger("tracemind.worker.stream_ingestor")


class StreamingIngestor:
    """Consumes trace events from Kafka and flushes micro-batches to TimescaleDB."""

    def __init__(
        self,
        consumer: AsyncTraceEventConsumer,
        session_factory: async_sessionmaker[AsyncSession],
        batch_size: int = 1000,
        flush_interval_ms: int = 50,
    ) -> None:
        self.consumer = consumer
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.flush_interval_ms = flush_interval_ms

        self._buffer: list[TraceEvent] = []
        self._last_flush_time = time.monotonic()
        self._running = False
        self._total_ingested = 0
        self._total_flushes = 0

    async def start(self) -> None:
        """Start the consumer and begin processing event streams."""
        await self.consumer.start()
        self._running = True
        self._last_flush_time = time.monotonic()
        logger.info(
            "streaming_ingestor_started",
            batch_size=self.batch_size,
            flush_interval_ms=self.flush_interval_ms,
        )

    async def stop(self) -> None:
        """Flush remaining buffer, commit offsets, and close consumer."""
        if not self._running:
            return

        logger.info("streaming_ingestor_stopping", pending_buffered=len(self._buffer))
        self._running = False

        # Drain and persist any lingering records
        if self._buffer:
            await self._flush_buffer()

        await self.consumer.stop()
        logger.info(
            "streaming_ingestor_stopped",
            total_ingested=self._total_ingested,
            total_flushes=self._total_flushes,
        )

    async def run_step(self) -> int:
        """Execute a single polling and micro-batch flush iteration."""
        if not self._running:
            return 0

        # Poll incoming batch from consumer
        new_events = await self.consumer.get_batch(
            max_records=self.batch_size - len(self._buffer),
            timeout_ms=self.flush_interval_ms,
        )
        if new_events:
            self._buffer.extend(new_events)

        elapsed_ms = (time.monotonic() - self._last_flush_time) * 1000.0
        should_flush = len(self._buffer) >= self.batch_size or (
            len(self._buffer) > 0 and elapsed_ms >= self.flush_interval_ms
        )

        flushed_count = 0
        if should_flush:
            flushed_count = await self._flush_buffer()

        return flushed_count

    async def run_loop(self) -> None:
        """Continuously consume and persist trace streams until stopped."""
        await self.start()
        try:
            while self._running:
                await self.run_step()
                # Yield control briefly to event loop
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            logger.info("streaming_ingestor_cancelled")
        finally:
            await self.stop()

    async def _flush_buffer(self) -> int:
        """Persist buffered records into TimescaleDB and commit consumer offsets."""
        if not self._buffer:
            return 0

        events_to_persist = list(self._buffer)
        self._buffer.clear()
        self._last_flush_time = time.monotonic()

        records: list[dict[str, Any]] = []
        for ev in events_to_persist:
            ev_type = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            ev_status = ev.status.value if hasattr(ev.status, "value") else str(ev.status)
            records.append(
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

        async with self.session_factory() as session:
            try:
                # Fast-path high-speed bulk insert
                await session.execute(insert(TraceEventModel), records)
                await session.commit()
            except Exception:
                # Idempotency fallback on duplicate primary key collision
                await session.rollback()
                for r in records:
                    await session.merge(TraceEventModel(**r))
                await session.commit()

        # Invariant: Commit Kafka offset ONLY after DB persistence succeeds
        await self.consumer.commit()

        count = len(records)
        self._total_ingested += count
        self._total_flushes += 1
        return count


async def run_worker_cli(settings: Settings | None = None) -> None:
    """CLI runner for background streaming ingestion daemon."""
    cfg = settings or get_settings()
    engine = get_async_engine(database_url=cfg.database_url)
    await init_db(engine)
    session_factory = get_async_session_factory(engine)

    consumer = create_consumer(settings=cfg)
    ingestor = StreamingIngestor(
        consumer=consumer,
        session_factory=session_factory,
        batch_size=cfg.kafka_batch_size,
        flush_interval_ms=cfg.kafka_flush_interval_ms,
    )

    loop = asyncio.get_running_loop()

    # Graceful termination signal trapping
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("shutdown_signal_received")
        stop_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

    worker_task = asyncio.create_task(ingestor.run_loop())

    if sys.platform == "win32":
        # On Windows, keep running until cancelled
        try:
            await worker_task
        except (KeyboardInterrupt, asyncio.CancelledError):
            await ingestor.stop()
    else:
        await stop_event.wait()
        await ingestor.stop()
        await worker_task


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TraceMind Streaming Ingestion Worker")
    args = parser.parse_args()
    asyncio.run(run_worker_cli())
