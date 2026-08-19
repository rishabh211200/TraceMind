"""Integration tests for end-to-end streaming trace ingestion pipeline."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from apps.simulator.config import SimulationConfig
from apps.simulator.streaming import stream_simulation
from apps.worker.stream_ingestor import StreamingIngestor
from packages.database.models.trace_event import TraceEventModel
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.events.bus import InMemoryEventBus


def _make_event(
    execution_id: str = "exec_pipe_001",
    event_id: str | None = None,
    service: str = "order-service",
) -> TraceEvent:
    return TraceEvent(
        event_id=event_id or f"evt_{uuid4().hex[:10]}",
        execution_id=execution_id,
        workflow_id="order_fulfillment",
        timestamp=datetime.now(UTC),
        service=service,
        operation="create_order",
        event_type=EventType.SERVICE_COMPLETED,
        status=EventStatus.SUCCESS,
        latency_ms=18.5,
        parent_event_id="evt_prev_001",
        correlation_id="corr_pipe_123",
        metadata={"step": 1},
    )


class MockSessionFactory:
    """Provides async context manager yielding test database session."""

    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_streaming_ingestor_flush_and_persistence(test_db_session) -> None:
    """Verify StreamingIngestor persists micro-batches into database and commits offsets."""
    bus = InMemoryEventBus()
    session_factory = MockSessionFactory(test_db_session)

    ingestor = StreamingIngestor(
        consumer=bus.consumer,
        session_factory=session_factory,  # type: ignore[arg-type]
        batch_size=10,
        flush_interval_ms=50,
    )

    await bus.producer.start()
    await ingestor.start()

    events = [_make_event(execution_id=f"exec_{i}") for i in range(25)]
    await bus.producer.publish_batch(events)

    # Run polling steps
    flushed_1 = await ingestor.run_step()
    assert flushed_1 == 10
    assert bus.consumer.committed_count == 10

    flushed_2 = await ingestor.run_step()
    assert flushed_2 == 10
    assert bus.consumer.committed_count == 20

    # Wait for time window flush for remaining 5
    await asyncio.sleep(0.06)
    flushed_3 = await ingestor.run_step()
    assert flushed_3 == 5
    assert bus.consumer.committed_count == 25

    # Verify rows in DB
    result = await test_db_session.execute(select(TraceEventModel))
    db_rows = result.scalars().all()
    assert len(db_rows) == 25

    await ingestor.stop()
    await bus.producer.stop()


@pytest.mark.asyncio
async def test_streaming_ingestor_idempotency(test_db_session) -> None:
    """Verify re-publishing identical event IDs updates idempotently without failure."""
    bus = InMemoryEventBus()
    session_factory = MockSessionFactory(test_db_session)

    ingestor = StreamingIngestor(
        consumer=bus.consumer,
        session_factory=session_factory,  # type: ignore[arg-type]
        batch_size=100,
        flush_interval_ms=20,
    )

    await bus.producer.start()
    await ingestor.start()

    # Publish 5 fixed event IDs
    fixed_events = [_make_event(event_id=f"fixed_evt_{i}") for i in range(5)]
    await bus.producer.publish_batch(fixed_events)

    await asyncio.sleep(0.03)
    await ingestor.run_step()

    # Re-publish same 5 fixed event IDs (simulating duplicate delivery / replay)
    await bus.producer.publish_batch(fixed_events)
    await asyncio.sleep(0.03)
    await ingestor.run_step()

    # Verify no duplicate count in database
    result = await test_db_session.execute(select(TraceEventModel))
    db_rows = result.scalars().all()
    assert len(db_rows) == 5

    await ingestor.stop()
    await bus.producer.stop()


@pytest.mark.asyncio
async def test_streaming_simulation_end_to_end(test_db_session) -> None:
    """Verify complete pipeline: Simulator -> Event Producer -> Consumer -> Ingestor -> DB."""
    bus = InMemoryEventBus()
    session_factory = MockSessionFactory(test_db_session)

    ingestor = StreamingIngestor(
        consumer=bus.consumer,
        session_factory=session_factory,  # type: ignore[arg-type]
        batch_size=50,
        flush_interval_ms=30,
    )

    await ingestor.start()

    cfg = SimulationConfig(seed=123, workflow_count=6, arrival_rate_per_second=10.0)
    sim_result = await stream_simulation(config=cfg, producer=bus.producer)

    assert len(sim_result.events) > 0

    # Drain ingestor until all events are consumed
    while bus.consumer.committed_count < len(sim_result.events):
        await ingestor.run_step()
        await asyncio.sleep(0.01)

    result = await test_db_session.execute(select(TraceEventModel))
    db_rows = result.scalars().all()
    assert len(db_rows) == len(sim_result.events)

    await ingestor.stop()


@pytest.mark.asyncio
async def test_api_generate_streaming_endpoint(async_client: AsyncClient) -> None:
    """Verify POST /api/v1/simulator/generate with stream_to_kafka=True."""
    mock_producer = AsyncMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.publish_batch = AsyncMock()
    mock_producer.flush = AsyncMock()

    with patch("packages.events.bus.create_producer", return_value=mock_producer):
        resp = await async_client.post(
            "/api/v1/simulator/generate",
            json={
                "workflow_count": 5,
                "arrival_rate_rps": 15.0,
                "seed": 999,
                "persist_to_db": False,
                "stream_to_kafka": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["streamed_to_kafka"] is True
        assert data["executions_generated"] == 5
        assert data["events_generated"] > 0
        assert mock_producer.start.called
        assert mock_producer.publish_batch.called
        assert mock_producer.stop.called
