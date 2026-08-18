"""Synthetic chaos injection and incident engine with ground-truth preservation."""

from datetime import datetime, timedelta
from typing import Any

from apps.simulator.distributions import DeterministicSampler
from packages.domain.incident import Incident, IncidentScenario, Severity

ChaosScenario = IncidentScenario

INCIDENT_PRESETS: dict[IncidentScenario, dict[str, Any]] = {
    IncidentScenario.DATABASE_LATENCY: {
        "name": "Database IOPS Saturation & Latency",
        "description": "Database read/write queries degraded 5.5x, propagating latency to customer, inventory, and payment dependencies.",
        "severity": Severity.HIGH,
        "affected_services": [
            "database-service",
            "customer-service",
            "inventory-service",
            "payment-service",
            "order-service",
        ],
        "ground_truth_root_cause": "Database shared storage IOPS degradation and connection pool saturation",
        "parameters": {"db_latency_multiplier": 5.5, "db_failure_adder": 0.04},
    },
    IncidentScenario.PAYMENT_LATENCY_DEGRADATION: {
        "name": "Payment Gateway Timeout & Degradation",
        "description": "Payment processing latency increased 4.2x with a 45% transient timeout rate triggering client retries.",
        "severity": Severity.HIGH,
        "affected_services": ["payment-service", "order-service"],
        "ground_truth_root_cause": "Third-party payment gateway latency spike and HTTP 504 gateway timeouts",
        "parameters": {"payment_latency_multiplier": 4.2, "payment_failure_rate": 0.45},
    },
    IncidentScenario.TRAFFIC_SPIKE: {
        "name": "Flash Traffic Volume Surge",
        "description": "Workflow arrival rate multiplied by 5x, causing queue buildup and client timeouts across all services.",
        "severity": Severity.HIGH,
        "affected_services": [
            "auth-service",
            "customer-service",
            "inventory-service",
            "pricing-service",
            "payment-service",
            "order-service",
            "notification-service",
        ],
        "ground_truth_root_cause": "Flash traffic volume surge exceeding upstream concurrency capacity limits",
        "parameters": {"arrival_rate_multiplier": 5.0, "queue_delay_factor": 3.0},
    },
    IncidentScenario.SERVICE_FAILURE: {
        "name": "Inventory Service Hard Crash",
        "description": "Inventory service experienced complete failure with a 95% error rate, short-circuiting downstream workflows.",
        "severity": Severity.CRITICAL,
        "affected_services": ["inventory-service", "order-service"],
        "ground_truth_root_cause": "Inventory Service out-of-memory crash leading to unhandled 500 internal server errors",
        "parameters": {"target_service": "inventory-service", "failure_rate_override": 0.95},
    },
    IncidentScenario.NETWORK_LATENCY: {
        "name": "Cross-Zone Network Packet Loss",
        "description": "Network transit latency increased by 180ms across all inter-service RPC invocations.",
        "severity": Severity.MEDIUM,
        "affected_services": [
            "auth-service",
            "customer-service",
            "database-service",
            "inventory-service",
            "pricing-service",
            "payment-service",
            "order-service",
            "notification-service",
        ],
        "ground_truth_root_cause": "Inter-service overlay network packet loss and cross-zone routing delay",
        "parameters": {"extra_network_delay_ms": 180.0},
    },
    IncidentScenario.RETRY_STORM: {
        "name": "Cascading Retry Storm & Thundering Herd",
        "description": "Initial transient payment errors triggered concurrent retries, amplifying load and driving failure rate to 70%.",
        "severity": Severity.CRITICAL,
        "affected_services": ["payment-service", "inventory-service", "database-service"],
        "ground_truth_root_cause": "Aggressive client retry loops saturating degraded payment and database resources without circuit breaking",
        "parameters": {"retry_amplification_multiplier": 2.5, "payment_failure_rate": 0.60},
    },
    IncidentScenario.CASCADING_FAILURE: {
        "name": "Multi-Tier Cascading Service Collapse",
        "description": "Database latency doubled, causing payment timeouts which backed up order-service worker queues until cascade failure.",
        "severity": Severity.CRITICAL,
        "affected_services": [
            "database-service",
            "inventory-service",
            "payment-service",
            "order-service",
        ],
        "ground_truth_root_cause": "Database lock contention cascading into payment authorization timeout and order queue exhaustion",
        "parameters": {
            "db_latency_multiplier": 4.0,
            "payment_failure_rate": 0.50,
            "order_queue_choke": True,
        },
    },
}


class ServiceDegradationModifier:
    """Active degradation parameters applied to a service during an incident."""

    def __init__(
        self,
        latency_multiplier: float = 1.0,
        extra_network_delay_ms: float = 0.0,
        failure_rate_adder: float = 0.0,
        failure_rate_override: float | None = None,
        capacity_multiplier: float = 1.0,
    ) -> None:
        self.latency_multiplier = latency_multiplier
        self.extra_network_delay_ms = extra_network_delay_ms
        self.failure_rate_adder = failure_rate_adder
        self.failure_rate_override = failure_rate_override
        self.capacity_multiplier = capacity_multiplier


class IncidentEngine:
    """Manages generation, scheduling, and active lifecycle of synthetic chaos incidents."""

    def __init__(
        self,
        sampler: DeterministicSampler,
        incident_scenario: IncidentScenario | None = None,
        incident_probability: float = 0.05,
        affected_duration_workflows: int = 150,
    ) -> None:
        self.sampler = sampler
        self.explicit_scenario = incident_scenario
        self.incident_probability = incident_probability
        self.duration_workflows = affected_duration_workflows
        self.scheduled_incidents: list[dict[str, Any]] = []
        self.recorded_incidents: list[Incident] = []

    def plan_incidents(self, total_workflows: int, base_time: datetime) -> None:
        """Plan incident execution windows across the simulated workflow sequence."""
        self.scheduled_incidents.clear()
        self.recorded_incidents.clear()

        if total_workflows < 20:
            return

        if self.explicit_scenario is not None:
            # Plan a single deterministic explicit incident in the middle of simulation
            start_wf = max(5, int(total_workflows * 0.25))
            duration = min(self.duration_workflows, int(total_workflows * 0.5))
            self._schedule_scenario(self.explicit_scenario, start_wf, duration, base_time)
        elif self.incident_probability > 0.0:
            # Stochastic planning of incidents across timeline
            available_scenarios = [
                IncidentScenario.DATABASE_LATENCY,
                IncidentScenario.PAYMENT_LATENCY_DEGRADATION,
                IncidentScenario.TRAFFIC_SPIKE,
                IncidentScenario.SERVICE_FAILURE,
                IncidentScenario.NETWORK_LATENCY,
                IncidentScenario.RETRY_STORM,
                IncidentScenario.CASCADING_FAILURE,
            ]

            step = self.duration_workflows + 50
            for start_wf in range(50, total_workflows - 50, step):
                if self.sampler.sample_bernoulli(self.incident_probability):
                    scenario = self.sampler.choice(available_scenarios)
                    self._schedule_scenario(scenario, start_wf, self.duration_workflows, base_time)

    def _schedule_scenario(
        self,
        scenario: IncidentScenario,
        start_wf: int,
        duration_wf: int,
        base_time: datetime,
    ) -> None:
        """Create incident specification and record canonical Incident entity."""
        incident_id = f"inc_{start_wf:06d}_{scenario.lower()[:8]}"
        sim_start_time = base_time + timedelta(seconds=start_wf * 0.05)
        sim_end_time = sim_start_time + timedelta(seconds=duration_wf * 0.05)

        affected_services: list[str]
        severity: Severity
        root_cause: str
        description: str
        params: dict[str, Any]

        if scenario == IncidentScenario.DATABASE_LATENCY:
            affected_services = [
                "database-service",
                "customer-service",
                "inventory-service",
                "payment-service",
                "order-service",
            ]
            severity = Severity.HIGH
            root_cause = "Database shared storage IOPS degradation and connection pool saturation"
            description = "Database read/write queries degraded 5.5x, propagating latency to customer, inventory, and payment dependencies."
            params = {"db_latency_multiplier": 5.5, "db_failure_adder": 0.04}

        elif scenario == IncidentScenario.PAYMENT_LATENCY_DEGRADATION:
            affected_services = ["payment-service", "order-service"]
            severity = Severity.HIGH
            root_cause = "Third-party payment gateway latency spike and HTTP 504 gateway timeouts"
            description = "Payment processing latency increased 4.2x with a 45% transient timeout rate triggering client retries."
            params = {"payment_latency_multiplier": 4.2, "payment_failure_rate": 0.45}

        elif scenario == IncidentScenario.TRAFFIC_SPIKE:
            affected_services = [
                "auth-service",
                "customer-service",
                "inventory-service",
                "pricing-service",
                "payment-service",
                "order-service",
                "notification-service",
            ]
            severity = Severity.HIGH
            root_cause = "Flash traffic volume surge exceeding upstream concurrency capacity limits"
            description = "Workflow arrival rate multiplied by 5x, causing queue buildup and client timeouts across all services."
            params = {"arrival_rate_multiplier": 5.0, "queue_delay_factor": 3.0}

        elif scenario == IncidentScenario.SERVICE_FAILURE:
            affected_services = ["inventory-service", "order-service"]
            severity = Severity.CRITICAL
            root_cause = "Inventory Service out-of-memory crash leading to unhandled 500 internal server errors"
            description = "Inventory service experienced complete failure with a 95% error rate, short-circuiting downstream workflows."
            params = {"target_service": "inventory-service", "failure_rate_override": 0.95}

        elif scenario == IncidentScenario.NETWORK_LATENCY:
            affected_services = [
                "auth-service",
                "customer-service",
                "database-service",
                "inventory-service",
                "pricing-service",
                "payment-service",
                "order-service",
                "notification-service",
            ]
            severity = Severity.MEDIUM
            root_cause = "Inter-service overlay network packet loss and cross-zone routing delay"
            description = "Network transit latency increased by 180ms across all inter-service RPC invocations."
            params = {"extra_network_delay_ms": 180.0}

        elif scenario == IncidentScenario.RETRY_STORM:
            affected_services = ["payment-service", "inventory-service", "database-service"]
            severity = Severity.CRITICAL
            root_cause = "Aggressive client retry loops saturating degraded payment and database resources without circuit breaking"
            description = "Initial transient payment errors triggered concurrent retries, amplifying load and driving failure rate to 70%."
            params = {"retry_amplification_multiplier": 2.5, "payment_failure_rate": 0.60}

        elif scenario == IncidentScenario.CASCADING_FAILURE:
            affected_services = [
                "database-service",
                "inventory-service",
                "payment-service",
                "order-service",
            ]
            severity = Severity.CRITICAL
            root_cause = "Database lock contention cascading into payment authorization timeout and order queue exhaustion"
            description = "Database latency doubled, causing payment timeouts which backed up order-service worker queues until cascade failure."
            params = {
                "db_latency_multiplier": 4.0,
                "payment_failure_rate": 0.50,
                "order_queue_choke": True,
            }

        else:
            affected_services = ["database-service"]
            severity = Severity.MEDIUM
            root_cause = "Generic service degradation"
            description = f"Synthetic execution of {scenario}"
            params = {}

        incident_record = Incident(
            id=incident_id,
            scenario_type=scenario,
            severity=severity,
            started_at=sim_start_time,
            ended_at=sim_end_time,
            affected_services=affected_services,
            ground_truth_root_cause=root_cause,
            description=description,
            parameters=params,
        )

        self.recorded_incidents.append(incident_record)
        self.scheduled_incidents.append(
            {
                "incident": incident_record,
                "start_wf": start_wf,
                "end_wf": start_wf + duration_wf,
            }
        )

    def _apply_db_latency(
        self, mod: ServiceDegradationModifier, params: dict[str, Any], svc: str
    ) -> None:
        if svc in ["customer-db", "inventory-db", "database-service"]:
            mod.latency_multiplier *= params.get("db_latency_multiplier", 5.0)
            mod.failure_rate_adder += params.get("db_failure_adder", 0.03)
        elif svc in ["customer-service", "inventory-service", "payment-service", "order-service"]:
            mod.latency_multiplier *= 2.2
            mod.failure_rate_adder += 0.02

    def _apply_payment_latency(
        self, mod: ServiceDegradationModifier, params: dict[str, Any], svc: str
    ) -> None:
        if svc in ["payment-service", "payment-gateway"]:
            mod.latency_multiplier *= params.get("payment_latency_multiplier", 4.0)
            mod.failure_rate_override = params.get("payment_failure_rate", 0.45)
        elif svc == "order-service":
            mod.latency_multiplier *= 1.5

    def _apply_retry_storm(self, mod: ServiceDegradationModifier, svc: str) -> None:
        if svc in ["payment-service", "inventory-service", "customer-db", "inventory-db"]:
            mod.latency_multiplier *= 3.0
            mod.failure_rate_adder += 0.35
            mod.capacity_multiplier *= 0.4

    def _apply_cascading_failure(self, mod: ServiceDegradationModifier, svc: str) -> None:
        if svc in ["customer-db", "inventory-db"]:
            mod.latency_multiplier *= 4.0
        elif svc in ["payment-service", "payment-gateway"]:
            mod.latency_multiplier *= 3.5
            mod.failure_rate_override = 0.50
        elif svc == "order-service":
            mod.latency_multiplier *= 2.5
            mod.failure_rate_adder += 0.20

    def _apply_modifier(
        self,
        modifier: ServiceDegradationModifier,
        scenario: IncidentScenario,
        params: dict[str, Any],
        service_name: str,
    ) -> None:
        """Apply incident-specific modifiers to the target service."""
        if scenario == IncidentScenario.DATABASE_LATENCY:
            self._apply_db_latency(modifier, params, service_name)
        elif scenario == IncidentScenario.PAYMENT_LATENCY_DEGRADATION:
            self._apply_payment_latency(modifier, params, service_name)
        elif scenario == IncidentScenario.TRAFFIC_SPIKE:
            modifier.capacity_multiplier *= 0.35
            modifier.latency_multiplier *= 1.8
        elif scenario == IncidentScenario.SERVICE_FAILURE:
            if service_name == params.get("target_service", "inventory-service"):
                modifier.failure_rate_override = params.get("failure_rate_override", 0.95)
        elif scenario == IncidentScenario.NETWORK_LATENCY:
            modifier.extra_network_delay_ms += params.get("extra_network_delay_ms", 150.0)
        elif scenario == IncidentScenario.RETRY_STORM:
            self._apply_retry_storm(modifier, service_name)
        elif scenario == IncidentScenario.CASCADING_FAILURE:
            self._apply_cascading_failure(modifier, service_name)

    def get_active_modifiers(
        self, workflow_index: int, service_name: str
    ) -> ServiceDegradationModifier:
        """Compute composite degradation modifiers for a service at a specific workflow sequence index."""
        modifier = ServiceDegradationModifier()
        for item in self.scheduled_incidents:
            if item["start_wf"] <= workflow_index < item["end_wf"]:
                incident: Incident = item["incident"]
                self._apply_modifier(
                    modifier, incident.scenario_type, incident.parameters, service_name
                )
        return modifier

    def get_arrival_rate_multiplier(self, workflow_index: int) -> float:
        """Check if traffic spike multiplier applies to the current workflow arrival."""
        mult = 1.0
        for item in self.scheduled_incidents:
            if item["start_wf"] <= workflow_index < item["end_wf"]:
                incident: Incident = item["incident"]
                if incident.scenario_type == IncidentScenario.TRAFFIC_SPIKE:
                    mult *= float(incident.parameters.get("arrival_rate_multiplier", 5.0))
        return mult

    def get_active_incident(self, workflow_index: int) -> Incident | None:
        """Retrieve the active ground-truth incident for a workflow index if present."""
        for item in self.scheduled_incidents:
            if item["start_wf"] <= workflow_index < item["end_wf"]:
                inc: Incident = item["incident"]
                return inc
        return None
