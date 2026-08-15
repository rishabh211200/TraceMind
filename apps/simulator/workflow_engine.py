"""Discrete-event workflow execution engine simulating end-to-end distributed traces."""

from datetime import UTC, datetime, timedelta

from apps.simulator.config import SimulationConfig, get_default_service_configs
from apps.simulator.distributions import DeterministicSampler
from apps.simulator.incidents import IncidentEngine
from apps.simulator.services import ServiceCallResult, SimulatedService
from packages.domain.events import EventStatus, EventType, TraceEvent
from packages.domain.incident import Incident
from packages.domain.workflow import ExecutionStatus, WorkflowExecution


class SimulationResult:
    """Complete collection of generated artifacts from a simulation run."""

    def __init__(
        self,
        config: SimulationConfig,
        executions: list[WorkflowExecution],
        events: list[TraceEvent],
        incidents: list[Incident],
    ) -> None:
        self.config = config
        self.executions = executions
        self.events = events
        self.incidents = incidents


class TraceSimulator:
    """Deterministic discrete-event simulator for distributed microservice workflows."""

    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self.sampler = DeterministicSampler(seed=self.config.seed)
        self.incident_engine = IncidentEngine(
            sampler=self.sampler,
            incident_scenario=self.config.incident_scenario,
            incident_probability=self.config.incident_probability,
            affected_duration_workflows=self.config.incident_duration_workflows,
        )

        # Initialize the 7 core business microservices
        service_configs = get_default_service_configs()
        if self.config.services:
            service_configs.update(self.config.services)

        self.services: dict[str, SimulatedService] = {
            name: SimulatedService(
                config=cfg,
                sampler=self.sampler,
                incident_engine=self.incident_engine,
            )
            for name, cfg in service_configs.items()
        }

    def run(self) -> SimulationResult:
        """Execute the configured batch of workflows in simulated time."""
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        total_workflows = self.config.workflow_count

        self.incident_engine.plan_incidents(total_workflows, base_time)

        executions: list[WorkflowExecution] = []
        events: list[TraceEvent] = []

        current_sim_time = base_time

        for wf_idx in range(total_workflows):
            traffic_mult = self.incident_engine.get_arrival_rate_multiplier(wf_idx)
            effective_arrival_rate = self.config.arrival_rate_per_second * traffic_mult
            interarrival_ms = self.sampler.sample_interarrival_ms(effective_arrival_rate)
            current_sim_time += timedelta(milliseconds=interarrival_ms)

            exec_record, wf_events = self._simulate_single_workflow(wf_idx, current_sim_time)
            executions.append(exec_record)
            events.extend(wf_events)

        return SimulationResult(
            config=self.config,
            executions=executions,
            events=events,
            incidents=self.incident_engine.recorded_incidents,
        )

    def _execute_service_step(
        self,
        service_name: str,
        operation: str,
        wf_idx: int,
        execution_id: str,
        workflow_id: str,
        correlation_id: str,
        sim_time: datetime,
        parent_event_id: str,
    ) -> ServiceCallResult:
        """Helper to invoke a microservice step."""
        return self.services[service_name].execute(
            operation=operation,
            workflow_index=wf_idx,
            execution_id=execution_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            sim_start_time=sim_time,
            parent_event_id=parent_event_id,
        )

    def _handle_customer_subspans(
        self,
        wf_idx: int,
        execution_id: str,
        workflow_id: str,
        correlation_id: str,
        wf_start_time: datetime,
        elapsed_wf_ms: float,
        parent_span_id: str,
        inc_id: str | None,
        is_incident: bool,
    ) -> tuple[float, list[TraceEvent]]:
        """Model customer-cache hit/miss and customer-db query child spans."""
        events: list[TraceEvent] = []
        cache_hit = self.sampler.sample_bernoulli(
            self.services["customer-service"].config.cache_hit_rate
        )
        branch_time = wf_start_time + timedelta(milliseconds=elapsed_wf_ms)
        added_ms = 0.0

        if cache_hit:
            cache_latency_ms = self.sampler.sample_latency(baseline_ms=3.0, sigma=0.20)
            added_ms += cache_latency_ms
            events.append(
                TraceEvent(
                    event_id=f"evt_{execution_id}_cache_hit",
                    execution_id=execution_id,
                    workflow_id=workflow_id,
                    timestamp=branch_time + timedelta(milliseconds=cache_latency_ms),
                    service="customer-cache",
                    operation="cache_lookup",
                    event_type=EventType.CACHE_HIT,
                    status=EventStatus.SUCCESS,
                    latency_ms=cache_latency_ms,
                    parent_event_id=parent_span_id,
                    correlation_id=correlation_id,
                    metadata={"incident_id": inc_id, "is_incident": is_incident},
                )
            )
        else:
            cache_miss_latency_ms = 1.5
            added_ms += cache_miss_latency_ms
            events.append(
                TraceEvent(
                    event_id=f"evt_{execution_id}_cache_miss",
                    execution_id=execution_id,
                    workflow_id=workflow_id,
                    timestamp=branch_time + timedelta(milliseconds=cache_miss_latency_ms),
                    service="customer-cache",
                    operation="cache_lookup",
                    event_type=EventType.CACHE_MISS,
                    status=EventStatus.SUCCESS,
                    latency_ms=cache_miss_latency_ms,
                    parent_event_id=parent_span_id,
                    correlation_id=correlation_id,
                    metadata={"incident_id": inc_id, "is_incident": is_incident},
                )
            )
            # Query customer-db infrastructure dependency
            db_mod = self.incident_engine.get_active_modifiers(wf_idx, "customer-db")
            db_base = self.sampler.sample_latency(baseline_ms=35.0, sigma=0.30)
            db_latency_ms = round(
                (db_base * db_mod.latency_multiplier) + db_mod.extra_network_delay_ms, 2
            )
            added_ms += db_latency_ms
            events.append(
                TraceEvent(
                    event_id=f"evt_{execution_id}_customer_db",
                    execution_id=execution_id,
                    workflow_id=workflow_id,
                    timestamp=branch_time + timedelta(milliseconds=added_ms),
                    service="customer-db",
                    operation="query_customer_db",
                    event_type=EventType.DATABASE_QUERY,
                    status=EventStatus.SUCCESS,
                    latency_ms=db_latency_ms,
                    parent_event_id=parent_span_id,
                    correlation_id=correlation_id,
                    metadata={"incident_id": inc_id, "is_incident": is_incident},
                )
            )

        return added_ms, events

    def _simulate_single_workflow(
        self, wf_idx: int, wf_start_time: datetime
    ) -> tuple[WorkflowExecution, list[TraceEvent]]:
        """Simulate execution of one workflow across distributed microservices."""
        execution_id = f"exec_{self.config.seed}_{wf_idx:06d}"
        correlation_id = f"corr_{self.config.seed}_{wf_idx:06d}"
        workflow_id = "order_fulfillment"

        active_inc = self.incident_engine.get_active_incident(wf_idx)
        inc_id = active_inc.id if active_inc else None
        is_incident = active_inc is not None

        wf_events: list[TraceEvent] = []
        elapsed_wf_ms = 0.0
        total_retries = 0
        total_errors = 0
        failed_reason: str | None = None
        is_successful = True

        root_event_id = f"evt_{self.config.seed}_{wf_idx:06d}_root"
        wf_events.append(
            TraceEvent(
                event_id=root_event_id,
                execution_id=execution_id,
                workflow_id=workflow_id,
                timestamp=wf_start_time,
                service="api-gateway",
                operation="start_workflow",
                event_type=EventType.WORKFLOW_STARTED,
                status=EventStatus.SUCCESS,
                latency_ms=0.0,
                correlation_id=correlation_id,
                metadata={
                    "workflow_index": wf_idx,
                    "incident_id": inc_id,
                    "is_incident": is_incident,
                },
            )
        )

        steps = [
            ("auth-service", "authenticate_user", "Authentication failed"),
            ("customer-service", "get_customer_profile", "Customer profile lookup failed"),
            ("inventory-service", "reserve_inventory", "Inventory reservation failed"),
            ("pricing-service", "calculate_pricing", "Pricing calculation failed"),
            ("payment-service", "authorize_payment", "Payment authorization failed"),
            ("order-service", "create_order", "Order creation failed"),
            ("notification-service", "send_notification", "Notification delivery failed"),
        ]

        for svc_name, op, err_prefix in steps:
            if not is_successful:
                break

            step_start = wf_start_time + timedelta(milliseconds=elapsed_wf_ms)
            res = self._execute_service_step(
                svc_name,
                op,
                wf_idx,
                execution_id,
                workflow_id,
                correlation_id,
                step_start,
                root_event_id,
            )
            wf_events.extend(res.events)
            elapsed_wf_ms += res.total_duration_ms
            total_retries += res.retry_count

            if not res.success:
                is_successful = False
                total_errors += 1
                failed_reason = f"{err_prefix}: {res.error_message}"
                break

            # Handle internal infrastructure sub-spans
            parent_span_id = res.events[-1].event_id if res.events else root_event_id

            if svc_name == "customer-service":
                cust_added_ms, cust_events = self._handle_customer_subspans(
                    wf_idx,
                    execution_id,
                    workflow_id,
                    correlation_id,
                    wf_start_time,
                    elapsed_wf_ms,
                    parent_span_id,
                    inc_id,
                    is_incident,
                )
                elapsed_wf_ms += cust_added_ms
                wf_events.extend(cust_events)

            elif svc_name == "inventory-service":
                inv_db_mod = self.incident_engine.get_active_modifiers(wf_idx, "inventory-db")
                inv_base = self.sampler.sample_latency(baseline_ms=25.0, sigma=0.25)
                inv_db_lat = round(
                    (inv_base * inv_db_mod.latency_multiplier) + inv_db_mod.extra_network_delay_ms,
                    2,
                )
                elapsed_wf_ms += inv_db_lat
                wf_events.append(
                    TraceEvent(
                        event_id=f"evt_{execution_id}_inventory_db",
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        timestamp=wf_start_time + timedelta(milliseconds=elapsed_wf_ms),
                        service="inventory-db",
                        operation="query_inventory_db",
                        event_type=EventType.DATABASE_QUERY,
                        status=EventStatus.SUCCESS,
                        latency_ms=inv_db_lat,
                        parent_event_id=parent_span_id,
                        correlation_id=correlation_id,
                        metadata={"incident_id": inc_id, "is_incident": is_incident},
                    )
                )

            elif svc_name == "payment-service":
                pay_gw_mod = self.incident_engine.get_active_modifiers(wf_idx, "payment-gateway")
                pay_base = self.sampler.sample_latency(baseline_ms=65.0, sigma=0.35)
                pay_lat = round(
                    (pay_base * pay_gw_mod.latency_multiplier) + pay_gw_mod.extra_network_delay_ms,
                    2,
                )
                elapsed_wf_ms += pay_lat
                wf_events.append(
                    TraceEvent(
                        event_id=f"evt_{execution_id}_payment_gw",
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        timestamp=wf_start_time + timedelta(milliseconds=elapsed_wf_ms),
                        service="payment-gateway",
                        operation="process_charge",
                        event_type=EventType.SERVICE_COMPLETED,
                        status=EventStatus.SUCCESS,
                        latency_ms=pay_lat,
                        parent_event_id=parent_span_id,
                        correlation_id=correlation_id,
                        metadata={"incident_id": inc_id, "is_incident": is_incident},
                    )
                )

        # Finalize Workflow Execution
        wf_completed_time = wf_start_time + timedelta(milliseconds=elapsed_wf_ms)
        terminal_event_type = (
            EventType.WORKFLOW_COMPLETED if is_successful else EventType.WORKFLOW_FAILED
        )
        terminal_status = EventStatus.SUCCESS if is_successful else EventStatus.FAILURE

        wf_events.append(
            TraceEvent(
                event_id=f"evt_{execution_id}_end",
                execution_id=execution_id,
                workflow_id=workflow_id,
                timestamp=wf_completed_time,
                service="api-gateway",
                operation="end_workflow",
                event_type=terminal_event_type,
                status=terminal_status,
                latency_ms=round(elapsed_wf_ms, 2),
                parent_event_id=root_event_id,
                correlation_id=correlation_id,
                metadata={
                    "total_retries": total_retries,
                    "total_errors": total_errors,
                    "incident_id": inc_id,
                    "is_incident": is_incident,
                },
            )
        )

        execution_record = WorkflowExecution(
            id=execution_id,
            workflow_definition_id=workflow_id,
            started_at=wf_start_time,
            completed_at=wf_completed_time,
            status=ExecutionStatus.COMPLETED if is_successful else ExecutionStatus.FAILED,
            total_latency_ms=round(elapsed_wf_ms, 2),
            retry_count=total_retries,
            error_count=total_errors,
            failure_reason=failed_reason,
            metadata={
                "correlation_id": correlation_id,
                "workflow_index": wf_idx,
                "incident_id": inc_id,
                "is_incident_affected": is_incident,
            },
        )

        return execution_record, wf_events
