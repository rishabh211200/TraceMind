"""Unit tests for TraceMind Event Bus, Serializers, and In-Memory channels."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.simulator.config import SimulationConfig
from apps.simulator.streaming import StreamingTraceSimulator
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.events.bus import InMemoryEventBus, create_consumer, create_producer
from packages.events.serializers import (
    JsonTraceEventSerializer,
    deserialize_trace_event,
    serialize_trace_event,
)


def _create_sample_event(
    execution_id: str = "exec_test_001",
    event_id: str | None = None,
    service: str = "payment-service",
    operation: str = "authorize_payment",
) -> TraceEvent:
    """Helper to create a sample canonical TraceEvent."""
    return TraceEvent(
        event_id=event_id or f"evt_{uuid4().hex[:10]}",
        execution_id=execution_id,
        workflow_id="order_fulfillment",
        timestamp=datetime.now(UTC),
        service=service,
        operation=operation,
        event_type=EventType.SERVICE_COMPLETED,
        status=EventStatus.SUCCESS,
        latency_ms=45.2,
        parent_event_id="evt_root_001",
        correlation_id="corr_999",
        metadata={"client_id": "cust_123", "retries": 0},
    )


def test_json_serializer_roundtrip() -> None:
    """Verify exact serialization and deserialization of TraceEvent."""
    event = _create_sample_event()
    raw_bytes = serialize_trace_event(event)

    assert isinstance(raw_bytes, bytes)
    deserialized = deserialize_trace_event(raw_bytes)

    assert deserialized.event_id == event.event_id
    assert deserialized.execution_id == event.execution_id
    assert deserialized.workflow_id == event.workflow_id
    assert deserialized.service == event.service
    assert deserialized.operation == event.operation
    assert deserialized.event_type == event.event_type
    assert deserialized.status == event.status
    assert deserialized.latency_ms == event.latency_ms
    assert deserialized.parent_event_id == event.parent_event_id
    assert deserialized.correlation_id == event.correlation_id
    assert deserialized.metadata == event.metadata
    assert deserialized.timestamp == event.timestamp


def test_json_serializer_invalid_type() -> None:
    """Verify serializer rejects invalid types."""
    serializer = JsonTraceEventSerializer()
    with pytest.raises(TypeError):
        serializer.serialize("invalid_string_not_event")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        serializer.deserialize("not_bytes")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_in_memory_producer_consumer_batch() -> None:
    """Verify publishing and consuming micro-batches via InMemoryEventBus."""
    bus = InMemoryEventBus(default_topic="tracemind.events.raw")
    producer = bus.producer
    consumer = bus.consumer

    await producer.start()
    await consumer.start()

    events = [_create_sample_event(execution_id=f"exec_{i}") for i in range(15)]
    await producer.publish_batch(events)

    assert len(producer.published_events) == 15

    # Consume batch of 10
    batch_1 = await consumer.get_batch(max_records=10, timeout_ms=100)
    assert len(batch_1) == 10
    await consumer.commit()
    assert consumer.committed_count == 10

    # Consume remaining 5
    batch_2 = await consumer.get_batch(max_records=10, timeout_ms=100)
    assert len(batch_2) == 5
    await consumer.commit()
    assert consumer.committed_count == 15

    await producer.stop()
    await consumer.stop()


@pytest.mark.asyncio
async def test_event_bus_factory() -> None:
    """Verify factory functions create in-memory producer and consumer instances."""
    bus = InMemoryEventBus()
    producer = create_producer(in_memory=True, in_memory_bus=bus)
    consumer = create_consumer(in_memory=True, in_memory_bus=bus)

    await producer.start()
    await consumer.start()

    ev = _create_sample_event()
    await producer.publish_event(ev)

    batch = await consumer.get_batch(max_records=5, timeout_ms=100)
    assert len(batch) == 1
    assert batch[0].event_id == ev.event_id

    await producer.stop()
    await consumer.stop()


@pytest.mark.asyncio
async def test_streaming_trace_simulator() -> None:
    """Verify StreamingTraceSimulator streams events to producer in real time."""
    bus = InMemoryEventBus()
    cfg = SimulationConfig(seed=42, workflow_count=5, arrival_rate_per_second=20.0)

    emitted_via_callback: list[TraceEvent] = []
    simulator = StreamingTraceSimulator(
        config=cfg,
        producer=bus.producer,
        event_callback=lambda ev: emitted_via_callback.append(ev),
    )

    await bus.consumer.start()
    result = await simulator.run_streaming()

    assert len(result.executions) == 5
    assert len(result.events) > 0
    assert len(emitted_via_callback) == len(result.events)
    assert len(bus.producer.published_events) == len(result.events)

    # Consumer should be able to drain all streamed events
    all_consumed = []
    while True:
        batch = await bus.consumer.get_batch(max_records=100, timeout_ms=50)
        if not batch:
            break
        all_consumed.extend(batch)
        await bus.consumer.commit()

    assert len(all_consumed) == len(result.events)
    await bus.consumer.stop()
