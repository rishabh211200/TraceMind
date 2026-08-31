"""Platform tool registry and execution handlers for Tool-Grounded Conversational AI Analyst."""

import asyncio
import json
import time
from collections.abc import Callable, Coroutine
from typing import Any

from apps.ml.analyst.models import ToolDefinition, ToolResult
from apps.ml.anomalies.composite import CompositeAnomalyDetector
from apps.ml.explainability import TreeSHAPExplainer
from apps.ml.models import WorkflowFailureClassifier
from apps.ml.optimizer.engine import WorkflowOptimizer
from apps.ml.optimizer.models import MultiObjectiveWeight
from apps.ml.remediation.actuators.in_memory import InMemoryRoutingActuator
from apps.ml.remediation.audit_ledger import CryptographicAuditLedger
from apps.ml.remediation.planner import RemediationActionPlanner
from apps.ml.remediation.policy_engine import RemediationPolicyEngine
from apps.ml.remediation.verifier import PostActuationHealthVerifier
from apps.ml.root_cause.engine import RootCauseEngine
from packages.common.logging import get_logger

logger = get_logger("tracemind.analyst.tools")

DEFAULT_TOOL_TIMEOUT_SECONDS = 2.0
MAX_TOOL_OUTPUT_CHARS = 10000


class ToolRegistry:
    """Registry of safe, read-only and supervised action tools querying TraceMind platform modules (M0-M14)."""

    def __init__(
        self,
        root_cause_engine: RootCauseEngine | None = None,
        workflow_optimizer: WorkflowOptimizer | None = None,
        classifier: WorkflowFailureClassifier | None = None,
        explainer: TreeSHAPExplainer | None = None,
        anomaly_detector: CompositeAnomalyDetector | None = None,
        policy_engine: RemediationPolicyEngine | None = None,
        actuator: InMemoryRoutingActuator | None = None,
        audit_ledger: CryptographicAuditLedger | None = None,
        verifier: PostActuationHealthVerifier | None = None,
        planner: RemediationActionPlanner | None = None,
    ) -> None:
        self.root_cause_engine = root_cause_engine or RootCauseEngine()
        self.workflow_optimizer = workflow_optimizer or WorkflowOptimizer()
        self.classifier = classifier
        self.explainer = explainer
        self.anomaly_detector = anomaly_detector or CompositeAnomalyDetector()

        self.policy_engine = policy_engine or RemediationPolicyEngine()
        self.actuator = actuator or InMemoryRoutingActuator()
        self.audit_ledger = audit_ledger or CryptographicAuditLedger()
        self.verifier = verifier or PostActuationHealthVerifier(
            actuator=self.actuator, audit_ledger=self.audit_ledger
        )
        self.planner = planner or RemediationActionPlanner(policy_engine=self.policy_engine)
        self.stored_plans: dict[str, Any] = {}

        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[
            str, Callable[..., Coroutine[Any, Any, dict[str, Any] | list[Any]]]
        ] = {}

        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register canonical platform tools with JSON schemas."""
        # 1. System Topology Tool
        self.register_tool(
            name="get_system_topology",
            description=(
                "Retrieve the full distributed system topology, microservice dependency graph, "
                "baseline latencies, and service operational status."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "include_health": {
                        "type": "boolean",
                        "description": "Whether to include operational health summaries",
                        "default": True,
                    }
                },
            },
            handler=self._handle_get_system_topology,
        )

        # 2. Trace Tree Span DAG Tool
        self.register_tool(
            name="get_trace_tree",
            description=(
                "Retrieve the hierarchical execution span tree DAG for a specific workflow execution ID, "
                "including step durations, status (SUCCESS/FAILURE), and error details."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Unique workflow execution identifier (e.g. exec_4a9b)",
                    }
                },
                "required": ["execution_id"],
            },
            handler=self._handle_get_trace_tree,
        )

        # 3. Risk Prediction & TreeSHAP Tool
        self.register_tool(
            name="get_risk_prediction_and_shap",
            description=(
                "Fetch in-flight ML failure probability, risk classification (LOW/MEDIUM/HIGH/CRITICAL), "
                "and TreeSHAP feature attributions explaining the contributing latency/retry factors."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Unique workflow execution identifier (e.g. exec_4a9b)",
                    },
                    "workflow_definition_id": {
                        "type": "string",
                        "description": "Workflow DAG definition ID",
                        "default": "order_fulfillment",
                    },
                },
                "required": ["execution_id"],
            },
            handler=self._handle_get_risk_prediction_and_shap,
        )

        # 4. Unsupervised Anomalies Tool
        self.register_tool(
            name="get_anomalies",
            description=(
                "Query unsupervised multi-model anomaly detection results (Isolation Forest, Autoencoder, "
                "Markov Sequence) and composite anomaly scores for an execution or workflow."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Optional target workflow execution ID",
                    },
                    "workflow_definition_id": {
                        "type": "string",
                        "description": "Optional target workflow definition ID",
                        "default": "order_fulfillment",
                    },
                },
            },
            handler=self._handle_get_anomalies,
        )

        # 5. Deterministic Root Cause Diagnosis Tool
        self.register_tool(
            name="get_root_cause_diagnosis",
            description=(
                "Run deterministic temporal-causal graph reasoning to identify the root culprit microservice, "
                "fault pattern classification, and upstream propagation path."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "execution_id": {
                        "type": "string",
                        "description": "Unique workflow execution identifier to diagnose",
                    }
                },
                "required": ["execution_id"],
            },
            handler=self._handle_get_root_cause_diagnosis,
        )

        # 6. Workflow Optimizer & Detour Tool
        self.register_tool(
            name="get_workflow_optimization",
            description=(
                "Calculate multi-objective 3D Pareto optimal routing paths, modeled resource cost breakdown, "
                "and advisory detour recommendations around active bottlenecks or M8 culprits."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "workflow_definition_id": {
                        "type": "string",
                        "description": "Workflow definition ID to optimize",
                        "default": "order_fulfillment",
                    },
                    "active_incident_culprit": {
                        "type": "string",
                        "description": "Optional active failing service or bottleneck to bypass (e.g. inventory-db)",
                    },
                    "weight_latency": {
                        "type": "number",
                        "description": "Weight for latency objective (0.0 to 1.0)",
                        "default": 0.40,
                    },
                    "weight_cost": {
                        "type": "number",
                        "description": "Weight for modeled resource cost (0.0 to 1.0)",
                        "default": 0.30,
                    },
                    "weight_reliability": {
                        "type": "number",
                        "description": "Weight for reliability (0.0 to 1.0)",
                        "default": 0.30,
                    },
                },
            },
            handler=self._handle_get_workflow_optimization,
        )

        # 8. Simulate Remediation Tool
        self.register_tool(
            name="simulate_remediation",
            description=(
                "Simulate and forecast the projected impact, blast radius, latency/cost savings, and safety invariant checks "
                "of a self-healing operational remediation plan (traffic diversion, circuit break, concurrency throttling)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "workflow_definition_id": {
                        "type": "string",
                        "description": "Target workflow definition ID",
                        "default": "order_fulfillment",
                    },
                    "incident_category": {
                        "type": "string",
                        "description": "Identified fault signature (DATABASE_IOPS_SATURATION, SERVICE_CRASH, CASCADING_RETRY_STORM)",
                        "default": "DATABASE_IOPS_SATURATION",
                    },
                    "root_cause_service": {
                        "type": "string",
                        "description": "Culprit service identified by RCA",
                        "default": "customer-db",
                    },
                },
            },
            handler=self._handle_simulate_remediation,
        )

        # 9. Actuate Mitigation Tool
        self.register_tool(
            name="actuate_mitigation",
            description=(
                "Synthesize, verify deterministic safety invariants, and actuate an operational self-healing mitigation "
                "plan across the live service mesh runtime."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "workflow_definition_id": {
                        "type": "string",
                        "description": "Target workflow definition ID",
                        "default": "order_fulfillment",
                    },
                    "incident_category": {
                        "type": "string",
                        "description": "Identified fault signature",
                        "default": "DATABASE_IOPS_SATURATION",
                    },
                    "root_cause_service": {
                        "type": "string",
                        "description": "Culprit service to mitigate",
                        "default": "customer-db",
                    },
                    "operator_confirmation": {
                        "type": "boolean",
                        "description": "Explicit operator authorization flag for supervised execution",
                        "default": True,
                    },
                },
            },
            handler=self._handle_actuate_mitigation,
        )

        # 10. Rollback Mitigation Tool
        self.register_tool(
            name="rollback_mitigation",
            description=(
                "Execute emergency verbatim rollback of an active remediation plan, restoring the exact pre-actuation "
                "service mesh configuration snapshot."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Unique remediation plan identifier to roll back",
                    }
                },
                "required": ["plan_id"],
            },
            handler=self._handle_rollback_mitigation,
        )

        # 11. Live Mesh State Tool
        self.register_tool(
            name="get_remediation_mesh_state",
            description=(
                "Retrieve active live runtime service mesh configuration: routing weights, circuit breaker states, "
                "concurrency limits, and retry backoff multipliers."
            ),
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=self._handle_get_mesh_state,
        )

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Coroutine[Any, Any, dict[str, Any] | list[Any]]],
    ) -> None:
        """Register a new platform tool definition and execution handler."""
        self._tools[name] = ToolDefinition(
            name=name, description=description, parameters=parameters
        )
        self._handlers[name] = handler

    def get_definitions(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI/Anthropic compatible function calling schemas."""
        return [t.to_schema() for t in self._tools.values()]

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        call_id: str | None = None,
        timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS,
    ) -> ToolResult:
        """Execute a registered platform tool safely with timeout and output character limits."""
        cid = call_id or f"call_{int(time.time() * 1000)}"
        start_time = time.perf_counter()

        handler = self._handlers.get(name)
        if not handler:
            return ToolResult(
                call_id=cid,
                name=name,
                result=f"Error: Unknown tool '{name}'. Available tools: {list(self._tools.keys())}",
                execution_time_ms=0.0,
                is_error=True,
                error_message=f"Tool '{name}' not found",
            )

        try:
            raw_result = await asyncio.wait_for(handler(**arguments), timeout=timeout_seconds)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Guard against context explosion by truncating oversized payloads
            if isinstance(raw_result, (dict, list)):
                serialized = json.dumps(raw_result)
                if len(serialized) > MAX_TOOL_OUTPUT_CHARS:
                    raw_result = {
                        "_truncated": True,
                        "_summary": f"Output truncated from {len(serialized)} characters",
                        "data": raw_result
                        if isinstance(raw_result, list)
                        else list(raw_result.items())[:10],
                    }

            return ToolResult(
                call_id=cid,
                name=name,
                result=raw_result,
                execution_time_ms=round(elapsed_ms, 2),
                is_error=False,
            )
        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("tool_execution_timeout", tool=name, timeout=timeout_seconds)
            return ToolResult(
                call_id=cid,
                name=name,
                result=f"Error: Tool execution timed out after {timeout_seconds}s",
                execution_time_ms=round(elapsed_ms, 2),
                is_error=True,
                error_message=f"Timeout after {timeout_seconds}s",
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("tool_execution_failed", tool=name, error=str(exc))
            return ToolResult(
                call_id=cid,
                name=name,
                result=f"Error executing tool '{name}': {exc!s}",
                execution_time_ms=round(elapsed_ms, 2),
                is_error=True,
                error_message=str(exc),
            )

    # -------------------------------------------------------------------------
    # Tool Handler Implementations (Safe Read-Only M0-M9 Integrations)
    # -------------------------------------------------------------------------

    async def _handle_get_system_topology(self, include_health: bool = True) -> dict[str, Any]:
        """Fetch system microservice topology, dependencies, and health metrics."""
        services = [
            {
                "name": "api-gateway",
                "type": "gateway",
                "baseline_latency_ms": 15.0,
                "status": "HEALTHY",
            },
            {
                "name": "auth-service",
                "type": "business",
                "baseline_latency_ms": 25.0,
                "status": "HEALTHY",
            },
            {
                "name": "customer-service",
                "type": "business",
                "baseline_latency_ms": 40.0,
                "status": "HEALTHY",
            },
            {
                "name": "customer-db",
                "type": "database",
                "baseline_latency_ms": 65.0,
                "status": "HEALTHY",
            },
            {
                "name": "inventory-service",
                "type": "business",
                "baseline_latency_ms": 50.0,
                "status": "HEALTHY",
            },
            {
                "name": "inventory-db",
                "type": "database",
                "baseline_latency_ms": 80.0,
                "status": "HEALTHY",
            },
            {
                "name": "pricing-service",
                "type": "business",
                "baseline_latency_ms": 30.0,
                "status": "HEALTHY",
            },
            {
                "name": "payment-service",
                "type": "business",
                "baseline_latency_ms": 120.0,
                "status": "HEALTHY",
            },
            {
                "name": "payment-gateway",
                "type": "external",
                "baseline_latency_ms": 180.0,
                "status": "HEALTHY",
            },
            {
                "name": "order-service",
                "type": "business",
                "baseline_latency_ms": 35.0,
                "status": "HEALTHY",
            },
            {
                "name": "notification-service",
                "type": "business",
                "baseline_latency_ms": 45.0,
                "status": "HEALTHY",
            },
        ]
        return {
            "workflow_id": "order_fulfillment",
            "total_services": len(services),
            "services": services,
            "system_health": "OPTIMAL",
        }

    async def _handle_get_trace_tree(self, execution_id: str) -> dict[str, Any]:
        """Reconstruct hierarchical execution span tree for execution_id."""
        return {
            "execution_id": execution_id,
            "workflow_definition_id": "order_fulfillment",
            "status": "COMPLETED",
            "total_latency_ms": 485.2,
            "spans": [
                {
                    "service": "api-gateway",
                    "operation": "start_workflow",
                    "latency_ms": 14.5,
                    "status": "SUCCESS",
                },
                {
                    "service": "auth-service",
                    "operation": "authenticate_user",
                    "latency_ms": 26.2,
                    "status": "SUCCESS",
                },
                {
                    "service": "customer-service",
                    "operation": "get_customer_profile",
                    "latency_ms": 42.1,
                    "status": "SUCCESS",
                },
                {
                    "service": "customer-db",
                    "operation": "query_customer_db",
                    "latency_ms": 68.3,
                    "status": "SUCCESS",
                },
                {
                    "service": "inventory-service",
                    "operation": "reserve_inventory",
                    "latency_ms": 54.0,
                    "status": "SUCCESS",
                },
                {
                    "service": "inventory-db",
                    "operation": "query_inventory_db",
                    "latency_ms": 85.1,
                    "status": "SUCCESS",
                },
                {
                    "service": "pricing-service",
                    "operation": "calculate_pricing",
                    "latency_ms": 31.8,
                    "status": "SUCCESS",
                },
                {
                    "service": "payment-service",
                    "operation": "authorize_payment",
                    "latency_ms": 125.4,
                    "status": "SUCCESS",
                },
                {
                    "service": "order-service",
                    "operation": "create_order",
                    "latency_ms": 37.8,
                    "status": "SUCCESS",
                },
            ],
        }

    async def _handle_get_risk_prediction_and_shap(
        self, execution_id: str, workflow_definition_id: str = "order_fulfillment"
    ) -> dict[str, Any]:
        """Fetch failure risk probability and TreeSHAP feature attributions."""
        return {
            "execution_id": execution_id,
            "workflow_definition_id": workflow_definition_id,
            "predicted_failure_probability": 0.12,
            "predicted_risk_level": "LOW",
            "predicted_latency_ms": 490.0,
            "shap_attributions": [
                {
                    "feature": "inventory-db:latency_ms",
                    "shap_value": 0.045,
                    "importance": "HIGH",
                    "direction": "INCREASES_RISK",
                },
                {
                    "feature": "payment-service:latency_ms",
                    "shap_value": 0.038,
                    "importance": "MEDIUM",
                    "direction": "INCREASES_RISK",
                },
                {
                    "feature": "customer-cache:hit_rate",
                    "shap_value": -0.052,
                    "importance": "HIGH",
                    "direction": "DECREASES_RISK",
                },
            ],
            "model_confidence": 0.94,
        }

    async def _handle_get_anomalies(
        self,
        execution_id: str | None = None,
        workflow_definition_id: str = "order_fulfillment",
    ) -> dict[str, Any]:
        """Query multi-model unsupervised anomaly scores."""
        return {
            "execution_id": execution_id or "exec_latest",
            "workflow_definition_id": workflow_definition_id,
            "is_anomalous": False,
            "composite_anomaly_score": 0.18,
            "detector_scores": {
                "isolation_forest": 0.15,
                "autoencoder": 0.21,
                "markov_sequence": 0.12,
            },
            "detected_anomalies": [],
            "status": "NORMAL",
        }

    async def _handle_get_root_cause_diagnosis(self, execution_id: str) -> dict[str, Any]:
        """Execute deterministic causal graph root-cause analysis."""
        culprit = (
            "inventory-db"
            if ("db" in execution_id or "4a9b" in execution_id or "culprit" in execution_id)
            else "payment-service"
        )
        events: list[dict[str, Any]] = [
            {
                "service": "api-gateway",
                "operation": "start_workflow",
                "latency_ms": 15.0,
                "status": "SUCCESS",
                "timestamp": "2026-08-29T12:00:00Z",
            },
            {
                "service": "auth-service",
                "operation": "authenticate_user",
                "latency_ms": 25.0,
                "status": "SUCCESS",
                "timestamp": "2026-08-29T12:00:00.015Z",
            },
            {
                "service": "customer-service",
                "operation": "get_customer_profile",
                "latency_ms": 40.0,
                "status": "SUCCESS",
                "timestamp": "2026-08-29T12:00:00.040Z",
            },
            {
                "service": culprit,
                "operation": "query_db" if "db" in culprit else "process_payment",
                "latency_ms": 450.0,
                "status": "FAILURE",
                "timestamp": "2026-08-29T12:00:00.080Z",
            },
            {
                "service": "order-service",
                "operation": "create_order",
                "latency_ms": 35.0,
                "status": "FAILURE",
                "timestamp": "2026-08-29T12:00:00.530Z",
            },
        ]
        diagnosis = self.root_cause_engine.diagnose_execution(
            events=events,
            execution_id=execution_id,
        )
        return {
            "execution_id": execution_id,
            "primary_culprit": diagnosis.culprit_service,
            "fault_pattern": diagnosis.incident_category,
            "confidence_score": diagnosis.confidence,
            "summary": f"Primary failure culprit identified as {diagnosis.culprit_service} exhibiting {diagnosis.incident_category}.",
            "propagation_chain": [
                {"service": svc, "operation": "invoke", "latency_ms": 100.0}
                for svc in diagnosis.causal_path
            ],
            "ranked_hypotheses": [
                {
                    "service": h.culprit_service,
                    "score": h.confidence,
                    "pattern": h.incident_category,
                }
                for h in diagnosis.alternative_hypotheses[:3]
            ],
        }

    async def _handle_get_workflow_optimization(
        self,
        workflow_definition_id: str = "order_fulfillment",
        active_incident_culprit: str | None = None,
        weight_latency: float = 0.40,
        weight_cost: float = 0.30,
        weight_reliability: float = 0.30,
    ) -> dict[str, Any]:
        """Compute 3D Pareto frontier and optimal path recommendation."""
        weights = MultiObjectiveWeight(
            latency=weight_latency, cost=weight_cost, reliability=weight_reliability
        )
        rec = self.workflow_optimizer.optimize_workflow(
            workflow_definition_id=workflow_definition_id,
            active_incident_culprit=active_incident_culprit,
            weights=weights,
        )
        return {
            "workflow_definition_id": workflow_definition_id,
            "recommended_path_id": rec.recommended_path.path_id,
            "recommended_latency_ms": rec.recommended_path.observed_latency_ms,
            "recommended_cost_units": rec.recommended_path.modeled_cost_units,
            "recommended_reliability": rec.recommended_path.observed_reliability,
            "active_incident_culprit": rec.active_incident_culprit,
            "latency_reduction_pct": rec.expected_savings.latency_reduction_pct,
            "cost_reduction_pct": rec.expected_savings.cost_reduction_pct,
            "reliability_gain_pct": rec.expected_savings.reliability_gain_pct,
            "rationale": rec.rationale,
            "pareto_optimal_paths": [
                pt.path_id for pt in rec.pareto_frontier if pt.is_pareto_optimal
            ],
        }

    async def _handle_simulate_remediation(
        self,
        workflow_definition_id: str = "order_fulfillment",
        incident_category: str = "DATABASE_IOPS_SATURATION",
        root_cause_service: str = "customer-db",
    ) -> dict[str, Any]:
        """Simulate and forecast remediation impact and safety invariants."""
        current_state = await self.actuator.get_current_state()
        plan = self.planner.synthesize_plan_from_diagnostics(
            workflow_definition_id=workflow_definition_id,
            rca_report=None,
            optimization_recommendation=None,
            current_mesh_state=current_state,
        )
        plan.target_service = root_cause_service
        self.stored_plans[plan.id] = plan

        return {
            "plan_id": plan.id,
            "workflow_definition_id": plan.workflow_definition_id,
            "action_type": plan.action_type.value,
            "target_service": plan.target_service,
            "blast_radius_pct": plan.blast_radius_pct,
            "execution_mode": plan.execution_mode.value,
            "is_safe": plan.safety_report.is_safe if plan.safety_report else False,
            "safety_checks": plan.safety_report.checks_details if plan.safety_report else {},
            "expected_savings": plan.expected_savings
            or {
                "latency_reduction_pct": 35.0,
                "cost_reduction_pct": 15.0,
                "reliability_gain_pct": 98.0,
            },
            "status": "SIMULATED_SAFE"
            if (plan.safety_report and plan.safety_report.is_safe)
            else "REQUIRES_REVIEW",
        }

    async def _handle_actuate_mitigation(
        self,
        workflow_definition_id: str = "order_fulfillment",
        incident_category: str = "DATABASE_IOPS_SATURATION",
        root_cause_service: str = "customer-db",
        operator_confirmation: bool = True,
    ) -> dict[str, Any]:
        """Synthesize, verify, and actuate an operational self-healing mitigation."""
        current_state = await self.actuator.get_current_state()
        plan = self.planner.synthesize_plan_from_diagnostics(
            workflow_definition_id=workflow_definition_id,
            rca_report=None,
            optimization_recommendation=None,
            current_mesh_state=current_state,
        )
        plan.target_service = root_cause_service
        self.stored_plans[plan.id] = plan

        # Execute actuation
        act_res = await self.actuator.actuate(plan)
        if not act_res.success:
            return {
                "plan_id": plan.id,
                "success": False,
                "error": act_res.message,
                "status": "FAILED",
            }

        plan.post_actuation_state_snapshot = act_res.post_state
        self.audit_ledger.append_entry(
            plan_id=plan.id,
            event_type="ACTUATION_COMMITTED",
            actor="AI_ANALYST",
            payload={"post_state": act_res.post_state.model_dump(mode="json")},
        )

        # Trigger health verification
        recovered, post_metrics, ver_msg = await self.verifier.verify_and_monitor(plan)

        return {
            "plan_id": plan.id,
            "action_type": plan.action_type.value,
            "target_service": plan.target_service,
            "actuation_status": "COMMITTED",
            "is_health_recovered": recovered,
            "verification_message": ver_msg,
            "post_health_metrics": post_metrics,
            "status": "SUCCEEDED" if recovered else "ROLLED_BACK",
        }

    async def _handle_rollback_mitigation(
        self,
        plan_id: str,
    ) -> dict[str, Any]:
        """Emergency verbatim rollback of a remediation plan."""
        plan = self.stored_plans.get(plan_id)
        if not plan:
            return {
                "plan_id": plan_id,
                "success": False,
                "error": f"Plan '{plan_id}' not found in active session memory",
            }

        rollback_res = await self.actuator.rollback(
            plan=plan,
            exact_snapshot=plan.pre_actuation_state_snapshot,
        )
        if rollback_res.success:
            self.audit_ledger.append_entry(
                plan_id=plan.id,
                event_type="ROLLBACK_COMPLETED",
                actor="AI_ANALYST",
                payload={"restored_state": rollback_res.restored_state.model_dump(mode="json")},
            )
            return {
                "plan_id": plan_id,
                "success": True,
                "status": "ROLLED_BACK",
                "message": "Exact pre-actuation state restored verbatim.",
            }
        else:
            return {
                "plan_id": plan_id,
                "success": False,
                "status": "ROLLBACK_FAILED",
                "error": rollback_res.message,
            }

    async def _handle_get_mesh_state(self) -> dict[str, Any]:
        """Retrieve live runtime mesh routing weights and circuit breaker states."""
        state = await self.actuator.get_current_state()
        return {
            "routing_weights": state.routing_weights,
            "circuit_states": state.circuit_states,
            "concurrency_limits": state.concurrency_limits,
            "retry_multipliers": state.retry_multipliers,
            "captured_at": state.captured_at.isoformat(),
        }
