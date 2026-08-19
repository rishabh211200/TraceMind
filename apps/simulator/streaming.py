"""Streaming trace event generator for real-time publishing to Kafka / Event Bus."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from apps.simulator.config import SimulationConfig
from apps.simulator.workflow_engine import SimulationResult, TraceSimulator
from packages.common.logging import get_logger
from packages.domain.events import TraceEvent
from packages.domain.workflow import WorkflowExecution
from packages.events.producer import AsyncTraceEventProducer

logger = get_logger("tracemind.simulator.streaming")


class StreamingTraceSimulator(TraceSimulator):
    """Extends TraceSimulator to emit TraceEvent records to an async producer in real-time."""

    def __init__(
        self,
        config: SimulationConfig | None = None,
        producer: AsyncTraceEventProducer | None = None,
        event_callback: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        super().__init__(config=config)
        self.producer = producer
        self.event_callback = event_callback

    async def run_streaming(
        self,
        topic: str | None = None,
    ) -> SimulationResult:
        """Execute discrete-event simulation while streaming events live to producer."""
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        total_workflows = self.config.workflow_count

        self.incident_engine.plan_incidents(total_workflows, base_time)

        executions: list[WorkflowExecution] = []
        events: list[TraceEvent] = []
        current_sim_time = base_time

        if self.producer is not None:
            await self.producer.start()

        try:
            for wf_idx in range(total_workflows):
                traffic_mult = self.incident_engine.get_arrival_rate_multiplier(wf_idx)
                effective_arrival_rate = self.config.arrival_rate_per_second * traffic_mult
                interarrival_ms = self.sampler.sample_interarrival_ms(effective_arrival_rate)
                current_sim_time += timedelta(milliseconds=interarrival_ms)

                exec_record, wf_events = self._simulate_single_workflow(wf_idx, current_sim_time)
                executions.append(exec_record)
                events.extend(wf_events)

                # Emit to callback if provided
                if self.event_callback is not None:
                    for ev in wf_events:
                        self.event_callback(ev)

                # Stream to async producer partitioned by execution_id
                if self.producer is not None:
                    await self.producer.publish_batch(wf_events, topic=topic)

            if self.producer is not None:
                await self.producer.flush()

        finally:
            if self.producer is not None:
                # Producer stopped by caller or flush
                pass

        logger.info(
            "streaming_simulation_completed",
            workflows=len(executions),
            events=len(events),
            incidents=len(self.incident_engine.recorded_incidents),
        )

        return SimulationResult(
            config=self.config,
            executions=executions,
            events=events,
            incidents=self.incident_engine.recorded_incidents,
        )


async def stream_simulation(
    config: SimulationConfig,
    producer: AsyncTraceEventProducer,
    topic: str | None = None,
) -> SimulationResult:
    """Convenience helper to stream a simulated workload batch to an async producer."""
    simulator = StreamingTraceSimulator(config=config, producer=producer)
    return await simulator.run_streaming(topic=topic)
