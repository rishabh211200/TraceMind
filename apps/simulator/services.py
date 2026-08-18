"""Simulated microservice actor modeling latency, queueing, retries, timeouts, and events."""

from datetime import datetime, timedelta

from apps.simulator.config import ServiceConfig
from apps.simulator.distributions import DeterministicSampler
from apps.simulator.incidents import IncidentEngine, ServiceDegradationModifier
from packages.domain.events import EventStatus, EventType, TraceEvent


class ServiceCallResult:
    """Outcome and collected telemetry for a service invocation."""

    def __init__(
        self,
        service_name: str,
        operation: str,
        success: bool,
        total_duration_ms: float,
        retry_count: int,
        events: list[TraceEvent],
        error_message: str | None = None,
        is_timeout: bool = False,
    ) -> None:
        self.service_name = service_name
        self.operation = operation
        self.success = success
        self.total_duration_ms = total_duration_ms
        self.retry_count = retry_count
        self.events = events
        self.error_message = error_message
        self.is_timeout = is_timeout


class SimulatedService:
    """Manages execution logic, queuing dynamics, and failure semantics for a microservice."""

    def __init__(
        self,
        config: ServiceConfig,
        sampler: DeterministicSampler,
        incident_engine: IncidentEngine,
    ) -> None:
        self.config = config
        self.sampler = sampler
        self.incident_engine = incident_engine
        self.current_in_flight = 0

    def execute(
        self,
        operation: str,
        workflow_index: int,
        execution_id: str,
        workflow_id: str,
        correlation_id: str,
        sim_start_time: datetime,
        parent_event_id: str | None = None,
        custom_latency_factor: float = 1.0,
    ) -> ServiceCallResult:
        """Execute a service operation including degradation, queuing, retries, and timeouts."""
        events: list[TraceEvent] = []
        mod: ServiceDegradationModifier = self.incident_engine.get_active_modifiers(
            workflow_index, self.config.name
        )

        effective_capacity = max(1, int(self.config.capacity * mod.capacity_multiplier))
        queue_wait_ms = 0.0
        if self.current_in_flight > effective_capacity:
            overload_ratio = (self.current_in_flight - effective_capacity) / effective_capacity
            queue_wait_ms = round(overload_ratio * self.config.baseline_latency_ms * 1.5, 2)

        svc_prefix = self.config.name.replace("-service", "")[:4]
        start_event_id = f"evt_{execution_id}_{svc_prefix}_start"
        events.append(
            TraceEvent(
                event_id=start_event_id,
                execution_id=execution_id,
                workflow_id=workflow_id,
                timestamp=sim_start_time,
                service=self.config.name,
                operation=operation,
                event_type=EventType.SERVICE_STARTED,
                status=EventStatus.SUCCESS,
                latency_ms=0.0,
                parent_event_id=parent_event_id,
                correlation_id=correlation_id,
                metadata={"in_flight": self.current_in_flight, "capacity": effective_capacity},
            )
        )

        effective_failure_rate = (
            mod.failure_rate_override
            if mod.failure_rate_override is not None
            else min(0.99, self.config.baseline_failure_rate + mod.failure_rate_adder)
        )

        elapsed_ms = queue_wait_ms
        retries_done = 0
        attempt = 0
        last_error: str | None = None
        is_timeout = False
        call_success = False

        while attempt <= self.config.max_retries:
            # Sample operation processing latency
            nominal_latency = self.sampler.sample_latency(
                baseline_ms=self.config.baseline_latency_ms * custom_latency_factor,
                sigma=self.config.latency_sigma,
                distribution_type=self.config.distribution_type,
                spike_probability=self.config.spike_probability,
                spike_multiplier=self.config.spike_multiplier,
            )
            attempt_latency = round(
                (nominal_latency * mod.latency_multiplier) + mod.extra_network_delay_ms, 2
            )

            # Check client timeout constraint
            if attempt_latency > self.config.timeout_ms:
                is_timeout = True
                attempt_latency = self.config.timeout_ms
                last_error = f"Operation timeout after {attempt_latency}ms (threshold: {self.config.timeout_ms}ms)"
                attempt_success = False
            else:
                is_timeout = False
                attempt_success = not self.sampler.sample_bernoulli(effective_failure_rate)
                if not attempt_success:
                    last_error = (
                        f"HTTP 503 Service Unavailable / Internal error in {self.config.name}"
                    )

            elapsed_ms += attempt_latency
            attempt_end_time = sim_start_time + timedelta(milliseconds=elapsed_ms)

            if attempt == 0:
                if attempt_success:
                    call_success = True
                    events.append(
                        TraceEvent(
                            event_id=f"evt_{execution_id}_{svc_prefix}_comp",
                            execution_id=execution_id,
                            workflow_id=workflow_id,
                            timestamp=attempt_end_time,
                            service=self.config.name,
                            operation=operation,
                            event_type=EventType.SERVICE_COMPLETED,
                            status=EventStatus.SUCCESS,
                            latency_ms=attempt_latency,
                            parent_event_id=start_event_id,
                            correlation_id=correlation_id,
                        )
                    )
                    break
                else:
                    event_type = (
                        EventType.SERVICE_TIMEOUT if is_timeout else EventType.SERVICE_FAILED
                    )
                    event_status = EventStatus.TIMEOUT if is_timeout else EventStatus.FAILURE
                    events.append(
                        TraceEvent(
                            event_id=f"evt_{execution_id}_{svc_prefix}_fail_0",
                            execution_id=execution_id,
                            workflow_id=workflow_id,
                            timestamp=attempt_end_time,
                            service=self.config.name,
                            operation=operation,
                            event_type=event_type,
                            status=event_status,
                            latency_ms=attempt_latency,
                            parent_event_id=start_event_id,
                            correlation_id=correlation_id,
                            metadata={"attempt": 0, "error": last_error},
                        )
                    )
            else:
                # Retry attempt
                retries_done += 1
                if attempt_success:
                    call_success = True
                    events.append(
                        TraceEvent(
                            event_id=f"evt_{execution_id}_{svc_prefix}_retry_done_{attempt}",
                            execution_id=execution_id,
                            workflow_id=workflow_id,
                            timestamp=attempt_end_time,
                            service=self.config.name,
                            operation=operation,
                            event_type=EventType.RETRY_COMPLETED,
                            status=EventStatus.SUCCESS,
                            latency_ms=attempt_latency,
                            parent_event_id=start_event_id,
                            correlation_id=correlation_id,
                            metadata={"retry_attempt": attempt},
                        )
                    )
                    events.append(
                        TraceEvent(
                            event_id=f"evt_{execution_id}_{svc_prefix}_comp",
                            execution_id=execution_id,
                            workflow_id=workflow_id,
                            timestamp=attempt_end_time,
                            service=self.config.name,
                            operation=operation,
                            event_type=EventType.SERVICE_COMPLETED,
                            status=EventStatus.SUCCESS,
                            latency_ms=elapsed_ms,
                            parent_event_id=start_event_id,
                            correlation_id=correlation_id,
                            metadata={"retries_required": retries_done},
                        )
                    )
                    break
                else:
                    events.append(
                        TraceEvent(
                            event_id=f"evt_{execution_id}_{svc_prefix}_fail_{attempt}",
                            execution_id=execution_id,
                            workflow_id=workflow_id,
                            timestamp=attempt_end_time,
                            service=self.config.name,
                            operation=operation,
                            event_type=EventType.SERVICE_FAILED,
                            status=EventStatus.FAILURE,
                            latency_ms=attempt_latency,
                            parent_event_id=start_event_id,
                            correlation_id=correlation_id,
                            metadata={"retry_attempt": attempt, "error": last_error},
                        )
                    )

            attempt += 1
            if attempt <= self.config.max_retries:
                # Apply backoff before next retry
                backoff_ms = self.sampler.sample_retry_backoff(
                    self.config.retry_backoff_ms, attempt
                )
                retry_start_time = attempt_end_time + timedelta(milliseconds=backoff_ms)
                events.append(
                    TraceEvent(
                        event_id=f"evt_{execution_id}_{svc_prefix}_retry_start_{attempt}",
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        timestamp=retry_start_time,
                        service=self.config.name,
                        operation=operation,
                        event_type=EventType.RETRY_STARTED,
                        status=EventStatus.RETRY,
                        latency_ms=backoff_ms,
                        parent_event_id=start_event_id,
                        correlation_id=correlation_id,
                        metadata={"attempt": attempt, "backoff_ms": backoff_ms},
                    )
                )
                elapsed_ms += backoff_ms

        return ServiceCallResult(
            service_name=self.config.name,
            operation=operation,
            success=call_success,
            total_duration_ms=round(elapsed_ms, 2),
            retry_count=retries_done,
            events=events,
            error_message=last_error if not call_success else None,
            is_timeout=is_timeout if not call_success else False,
        )
