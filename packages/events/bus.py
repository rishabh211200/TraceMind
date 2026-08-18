"""Event Bus registry and factory functions for streaming producer and consumer instances."""

import asyncio

from packages.common.config import Settings, get_settings
from packages.events.consumer import (
    AsyncTraceEventConsumer,
    InMemoryTraceEventConsumer,
    KafkaTraceEventConsumer,
)
from packages.events.producer import (
    AsyncTraceEventProducer,
    InMemoryTraceEventProducer,
    KafkaTraceEventProducer,
)


class InMemoryEventBus:
    """Paired in-memory event bus providing hermetic queue channels for testing."""

    def __init__(self, default_topic: str = "tracemind.events.raw") -> None:
        self.queue: asyncio.Queue[tuple[str, str, bytes]] = asyncio.Queue()
        self.default_topic = default_topic
        self.producer = InMemoryTraceEventProducer(
            event_queue=self.queue, default_topic=default_topic
        )
        self.consumer = InMemoryTraceEventConsumer(event_queue=self.queue)


def create_producer(
    settings: Settings | None = None,
    in_memory: bool = False,
    in_memory_bus: InMemoryEventBus | None = None,
) -> AsyncTraceEventProducer:
    """Instantiate a configured event producer (Kafka or In-Memory)."""
    if in_memory:
        if in_memory_bus is not None:
            return in_memory_bus.producer
        return InMemoryTraceEventProducer()

    cfg = settings or get_settings()
    return KafkaTraceEventProducer(
        bootstrap_servers=cfg.kafka_bootstrap_servers,
        default_topic=cfg.kafka_topic_traces,
    )


def create_consumer(
    settings: Settings | None = None,
    topics: list[str] | None = None,
    in_memory: bool = False,
    in_memory_bus: InMemoryEventBus | None = None,
) -> AsyncTraceEventConsumer:
    """Instantiate a configured event consumer (Kafka or In-Memory)."""
    if in_memory:
        if in_memory_bus is not None:
            return in_memory_bus.consumer
        return InMemoryTraceEventConsumer(event_queue=asyncio.Queue())

    cfg = settings or get_settings()
    target_topics = topics or [cfg.kafka_topic_traces]
    return KafkaTraceEventConsumer(
        topics=target_topics,
        bootstrap_servers=cfg.kafka_bootstrap_servers,
        group_id=cfg.kafka_consumer_group,
        auto_offset_reset=cfg.kafka_auto_offset_reset,
    )
