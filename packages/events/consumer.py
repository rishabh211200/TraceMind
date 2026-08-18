"""Asynchronous TraceEvent Consumer implementations for Kafka and In-Memory streams."""

import asyncio
from typing import Protocol

from aiokafka import AIOKafkaConsumer

from packages.common.logging import get_logger
from packages.domain.events import TraceEvent
from packages.events.serializers import EventSerializer, JsonTraceEventSerializer

logger = get_logger("tracemind.events.consumer")


class AsyncTraceEventConsumer(Protocol):
    """Protocol defining asynchronous event consuming interface."""

    async def start(self) -> None:
        """Initialize consumer and subscribe to topics."""
        ...

    async def stop(self) -> None:
        """Close consumer connections and release partitions."""
        ...

    async def get_batch(self, max_records: int = 1000, timeout_ms: int = 50) -> list[TraceEvent]:
        """Fetch a micro-batch of deserialized TraceEvents."""
        ...

    async def commit(self) -> None:
        """Commit consumer offsets after successful batch persistence."""
        ...


class KafkaTraceEventConsumer:
    """Production-grade asynchronous Kafka consumer backed by aiokafka."""

    def __init__(
        self,
        topics: list[str] | None = None,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "tracemind-ingestor",
        auto_offset_reset: str = "earliest",
        serializer: EventSerializer[TraceEvent] | None = None,
        **kafka_kwargs,
    ) -> None:
        self.topics = topics or ["tracemind.events.raw"]
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.serializer = serializer or JsonTraceEventSerializer()
        self._consumer: AIOKafkaConsumer | None = None
        self._kafka_kwargs = kafka_kwargs
        self._started = False

    async def start(self) -> None:
        """Start the AIOKafkaConsumer with manual offset commits enabled."""
        if self._started and self._consumer is not None:
            return

        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=False,  # Enforce manual commit only after successful DB write
            **self._kafka_kwargs,
        )
        await self._consumer.start()
        self._started = True
        logger.info(
            "kafka_consumer_started",
            topics=self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
        )

    async def stop(self) -> None:
        """Close the AIOKafkaConsumer."""
        if not self._started or self._consumer is None:
            return

        try:
            await self._consumer.stop()
        finally:
            self._started = False
            self._consumer = None
            logger.info("kafka_consumer_stopped")

    async def get_batch(self, max_records: int = 1000, timeout_ms: int = 50) -> list[TraceEvent]:
        """Fetch records from subscribed partitions and deserialize into TraceEvents."""
        if not self._started or self._consumer is None:
            raise RuntimeError("KafkaTraceEventConsumer is not started. Call start() first.")

        records_map = await self._consumer.getmany(timeout_ms=timeout_ms, max_records=max_records)

        events: list[TraceEvent] = []
        for partition_records in records_map.values():
            for msg in partition_records:
                try:
                    event = self.serializer.deserialize(msg.value)
                    events.append(event)
                except Exception as exc:
                    logger.error(
                        "trace_event_deserialization_failed",
                        error=str(exc),
                        topic=msg.topic,
                        partition=msg.partition,
                        offset=msg.offset,
                    )
        return events

    async def commit(self) -> None:
        """Commit consumer offsets for all partitions fetched in the latest batch."""
        if self._started and self._consumer is not None:
            await self._consumer.commit()


class InMemoryTraceEventConsumer:
    """In-memory event consumer for hermetic testing and isolated pipelines."""

    def __init__(
        self,
        event_queue: asyncio.Queue[tuple[str, str, bytes]],
        serializer: EventSerializer[TraceEvent] | None = None,
    ) -> None:
        self.queue = event_queue
        self.serializer = serializer or JsonTraceEventSerializer()
        self.consumed_events: list[TraceEvent] = []
        self._started = False
        self.committed_count = 0
        self._pending_count = 0

    async def start(self) -> None:
        """Initialize in-memory consumer."""
        self._started = True

    async def stop(self) -> None:
        """Shut down in-memory consumer."""
        self._started = False

    async def get_batch(self, max_records: int = 1000, timeout_ms: int = 50) -> list[TraceEvent]:
        """Drain up to max_records from the queue within timeout_ms."""
        if not self._started:
            raise RuntimeError("InMemoryTraceEventConsumer is not started.")

        events: list[TraceEvent] = []
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)

        while len(events) < max_records:
            remaining_time = deadline - asyncio.get_event_loop().time()
            if remaining_time <= 0 and events:
                break

            timeout = max(0.001, remaining_time)
            try:
                topic, key, payload = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                event = self.serializer.deserialize(payload)
                events.append(event)
                self.consumed_events.append(event)
            except TimeoutError:
                break

        self._pending_count = len(events)
        return events

    async def commit(self) -> None:
        """Acknowledge processed records."""
        self.committed_count += self._pending_count
        self._pending_count = 0
