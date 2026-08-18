"""Asynchronous TraceEvent Producer implementations for Kafka and In-Memory streams."""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from aiokafka import AIOKafkaProducer

from packages.common.logging import get_logger
from packages.domain.events import TraceEvent
from packages.events.serializers import EventSerializer, JsonTraceEventSerializer

logger = get_logger("tracemind.events.producer")


class AsyncTraceEventProducer(Protocol):
    """Protocol defining asynchronous event publishing interface."""

    async def start(self) -> None:
        """Initialize and start the underlying producer connection."""
        ...

    async def stop(self) -> None:
        """Flush pending buffers and close producer connections."""
        ...

    async def publish_event(self, event: TraceEvent, topic: str | None = None) -> None:
        """Publish a single TraceEvent record."""
        ...

    async def publish_batch(self, events: Sequence[TraceEvent], topic: str | None = None) -> None:
        """Publish a batch of TraceEvent records."""
        ...

    async def flush(self) -> None:
        """Ensure all buffered events are sent over the wire."""
        ...


class KafkaTraceEventProducer:
    """Production-grade asynchronous Kafka producer backed by aiokafka."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        default_topic: str = "tracemind.events.raw",
        serializer: EventSerializer[TraceEvent] | None = None,
        **kafka_kwargs,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.default_topic = default_topic
        self.serializer = serializer or JsonTraceEventSerializer()
        self._producer: AIOKafkaProducer | None = None
        self._kafka_kwargs = kafka_kwargs
        self._started = False

    async def start(self) -> None:
        """Start the AIOKafkaProducer."""
        if self._started and self._producer is not None:
            return

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            acks="all",
            enable_idempotence=True,
            **self._kafka_kwargs,
        )
        await self._producer.start()
        self._started = True
        logger.info(
            "kafka_producer_started",
            bootstrap_servers=self.bootstrap_servers,
            default_topic=self.default_topic,
        )

    async def stop(self) -> None:
        """Flush and stop the AIOKafkaProducer."""
        if not self._started or self._producer is None:
            return

        try:
            await self._producer.flush()
            await self._producer.stop()
        finally:
            self._started = False
            self._producer = None
            logger.info("kafka_producer_stopped")

    async def publish_event(self, event: TraceEvent, topic: str | None = None) -> None:
        """Publish a single TraceEvent to Kafka partitioned by execution_id."""
        if not self._started or self._producer is None:
            raise RuntimeError("KafkaTraceEventProducer is not started. Call start() first.")

        target_topic = topic or self.default_topic
        key_bytes = event.execution_id.encode("utf-8")
        value_bytes = self.serializer.serialize(event)

        await self._producer.send_and_wait(
            topic=target_topic,
            key=key_bytes,
            value=value_bytes,
        )

    async def publish_batch(self, events: Sequence[TraceEvent], topic: str | None = None) -> None:
        """Publish a sequence of TraceEvents concurrently to Kafka."""
        if not events:
            return
        if not self._started or self._producer is None:
            raise RuntimeError("KafkaTraceEventProducer is not started. Call start() first.")

        target_topic = topic or self.default_topic
        tasks = []
        for ev in events:
            key_bytes = ev.execution_id.encode("utf-8")
            val_bytes = self.serializer.serialize(ev)
            tasks.append(
                self._producer.send(
                    topic=target_topic,
                    key=key_bytes,
                    value=val_bytes,
                )
            )
        await asyncio.gather(*tasks)

    async def flush(self) -> None:
        """Flush buffered messages to Kafka brokers."""
        if self._started and self._producer is not None:
            await self._producer.flush()


class InMemoryTraceEventProducer:
    """In-memory event producer for hermetic unit and integration testing."""

    def __init__(
        self,
        event_queue: asyncio.Queue[tuple[str, str, bytes]] | None = None,
        default_topic: str = "tracemind.events.raw",
        serializer: EventSerializer[TraceEvent] | None = None,
    ) -> None:
        self.default_topic = default_topic
        self.serializer = serializer or JsonTraceEventSerializer()
        self.queue = event_queue if event_queue is not None else asyncio.Queue()
        self.published_events: list[TraceEvent] = []
        self._started = False

    async def start(self) -> None:
        """Initialize in-memory producer state."""
        self._started = True

    async def stop(self) -> None:
        """Shut down in-memory producer state."""
        self._started = False

    async def publish_event(self, event: TraceEvent, topic: str | None = None) -> None:
        """Emit a TraceEvent to the in-memory queue."""
        if not self._started:
            raise RuntimeError("InMemoryTraceEventProducer is not started.")

        target_topic = topic or self.default_topic
        key = event.execution_id
        payload = self.serializer.serialize(event)
        await self.queue.put((target_topic, key, payload))
        self.published_events.append(event)

    async def publish_batch(self, events: Sequence[TraceEvent], topic: str | None = None) -> None:
        """Emit multiple TraceEvents to the in-memory queue."""
        for event in events:
            await self.publish_event(event, topic=topic)

    async def flush(self) -> None:
        """No-op for in-memory queue."""
        pass
