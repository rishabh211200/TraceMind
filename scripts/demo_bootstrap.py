"""TraceMind Demo Bootstrap & Deterministic Showcase Seeder.

Initializes the database, generates baseline telemetry, trains local ML models,
and seeds the 4 deterministic showcase scenarios for technical demonstrations.

Usage:
    python scripts/demo_bootstrap.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from apps.ml.anomalies.registry import AnomalyDetectorRegistry
from apps.ml.optimizer.engine import WorkflowOptimizer
from apps.ml.registry import ModelRegistry
from apps.ml.remediation.actuators.in_memory import InMemoryRoutingActuator
from apps.ml.remediation.audit_ledger import CryptographicAuditLedger
from apps.ml.remediation.planner import RemediationActionPlanner
from apps.ml.remediation.policy_engine import RemediationPolicyEngine
from apps.ml.remediation.safety_guards import SafetyInvariantEvaluator
from apps.ml.root_cause.engine import RootCauseEngine
from apps.simulator.config import SimulationConfig, get_default_service_configs
from apps.simulator.incidents import ChaosScenario
from apps.simulator.workflow_engine import TraceSimulator
from packages.common.logging import configure_logging, get_logger
from packages.common.security.crypto import PasswordHasher, hash_api_key_secret
from packages.database.ingestion import DatasetIngestor
from packages.database.models.optimization import OptimizationModel
from packages.database.models.remediation import (
    RemediationActionPlanModel,
    RemediationAuditLedgerModel,
)
from packages.database.models.root_cause import RootCauseModel
from packages.database.models.security import ApiKeyModel, TenantModel, UserModel
from packages.database.models.service import ServiceModel
from packages.database.models.workflow import WorkflowDefinitionModel
from packages.database.session import get_async_engine, get_async_session_factory, init_db
from packages.domain.remediation import (
    ActionPlanStatus,
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
    StateSnapshot,
)
from packages.domain.security import Permission, Role
from packages.domain.workflow import ExecutionStatus

configure_logging(log_level="INFO")
logger = get_logger("tracemind.demo_bootstrap")

hasher = PasswordHasher()

DEMO_TENANT_ID = "tenant_system"
DEMO_WORKFLOW_ID = "order_fulfillment"


async def seed_services_and_workflows(session) -> None:
    """Seed default services and the canonical order_fulfillment workflow DAG."""
    logger.info("seeding_services_and_workflows")
    now = datetime.now(UTC)

    # 1. Services
    service_configs = get_default_service_configs()
    for svc_name, svc_cfg in service_configs.items():
        existing = await session.get(ServiceModel, (svc_name, DEMO_TENANT_ID))
        if not existing:
            svc_model = ServiceModel(
                name=svc_name,
                tenant_id=DEMO_TENANT_ID,
                service_type="business_microservice",
                capacity=svc_cfg.capacity,
                baseline_latency_ms=svc_cfg.baseline_latency_ms,
                baseline_failure_rate=svc_cfg.baseline_failure_rate,
                timeout_ms=svc_cfg.timeout_ms,
                max_retries=svc_cfg.max_retries,
                retry_backoff_ms=svc_cfg.retry_backoff_ms,
                dependencies=svc_cfg.dependencies,
                metadata_={
                    "description": f"Core microservice {svc_name}",
                    "team": "core-platform",
                },
                created_at=now,
                updated_at=now,
            )
            session.add(svc_model)

    # 2. Workflow Definition
    wf_existing = await session.get(WorkflowDefinitionModel, DEMO_WORKFLOW_ID)
    if not wf_existing:
        nodes = [
            {"id": "auth", "service": "auth-service", "operation": "verify_token"},
            {"id": "customer", "service": "customer-service", "operation": "get_customer_profile"},
            {"id": "inventory", "service": "inventory-service", "operation": "reserve_stock"},
            {"id": "pricing", "service": "pricing-service", "operation": "calculate_discounts"},
            {"id": "payment", "service": "payment-service", "operation": "process_charge"},
            {"id": "order", "service": "order-service", "operation": "create_order_record"},
            {
                "id": "notification",
                "service": "notification-service",
                "operation": "send_order_confirmation",
            },
        ]
        edges = [
            {"source": "auth", "target": "customer"},
            {"source": "customer", "target": "inventory"},
            {"source": "customer", "target": "pricing"},
            {"source": "inventory", "target": "payment"},
            {"source": "pricing", "target": "payment"},
            {"source": "payment", "target": "order"},
            {"source": "order", "target": "notification"},
        ]
        wf_model = WorkflowDefinitionModel(
            id=DEMO_WORKFLOW_ID,
            tenant_id=DEMO_TENANT_ID,
            name="Order Fulfillment Pipeline",
            version="1.0.0",
            description="Canonical end-to-end distributed order checkout and inventory fulfillment DAG",
            nodes=nodes,
            edges=edges,
            metadata_={"criticality": "TIER_1_CRITICAL", "sla_latency_ms": 500.0},
            created_at=now,
            updated_at=now,
        )
        session.add(wf_model)

    await session.commit()


async def seed_security_and_users(session) -> None:
    """Seed default tenants, admin/demo users, and fixed demo API keys."""
    logger.info("seeding_security_and_users")
    now = datetime.now(UTC)

    # 1. Default Tenant
    tenant = await session.get(TenantModel, DEMO_TENANT_ID)
    if not tenant:
        tenant = TenantModel(
            id=DEMO_TENANT_ID,
            name="TraceMind Showcase Organization",
            slug="tracemind-showcase",
            is_active=True,
            tier="ENTERPRISE",
            created_at=now,
        )
        session.add(tenant)
        await session.flush()

    # 2. System Admin User
    admin_email = "admin@tracemind.io"
    res = await session.execute(
        select(UserModel).where(
            UserModel.email == admin_email, UserModel.tenant_id == DEMO_TENANT_ID
        )
    )
    admin_user = res.scalar_one_or_none()
    if not admin_user:
        admin_user = UserModel(
            id="usr_admin_demo_01",
            tenant_id=DEMO_TENANT_ID,
            email=admin_email,
            full_name="Platform Administrator",
            hashed_password=hasher.hash_password("TraceMind#Admin2026!"),
            roles=[Role.PLATFORM_ADMIN.value, Role.TENANT_ADMIN.value],
            is_active=True,
            is_verified=True,
            created_at=now,
            last_login_at=now,
        )
        session.add(admin_user)

    # 3. Viewer User (Public Read-Only Exploration)
    viewer_email = "viewer@tracemind.io"
    res_v = await session.execute(
        select(UserModel).where(
            UserModel.email == viewer_email, UserModel.tenant_id == DEMO_TENANT_ID
        )
    )
    viewer_user = res_v.scalar_one_or_none()
    if not viewer_user:
        viewer_user = UserModel(
            id="usr_viewer_demo_01",
            tenant_id=DEMO_TENANT_ID,
            email=viewer_email,
            full_name="Demo Showcase Guest",
            hashed_password=hasher.hash_password("Viewer#Demo2026!"),
            roles=[Role.VIEWER.value],
            is_active=True,
            is_verified=True,
            created_at=now,
            last_login_at=now,
        )
        session.add(viewer_user)

    # 4. Fixed Demo API Key for Programmatic Testing (tm_live_demo_0123456789abcdef...)
    key_prefix = "tm_demo"
    key_secret = "0123456789abcdef0123456789abcdef"
    res_k = await session.execute(
        select(ApiKeyModel).where(
            ApiKeyModel.key_prefix == key_prefix, ApiKeyModel.tenant_id == DEMO_TENANT_ID
        )
    )
    demo_key = res_k.scalar_one_or_none()
    if not demo_key:
        demo_key = ApiKeyModel(
            id="key_demo_showcase_01",
            tenant_id=DEMO_TENANT_ID,
            user_id="usr_admin_demo_01",
            key_name="Showcase Pipeline Actuator Key",
            key_prefix=key_prefix,
            hashed_secret=hash_api_key_secret(key_secret),
            scopes=[p.value for p in Permission],
            is_active=True,
            created_at=now,
        )
        session.add(demo_key)

    await session.commit()


async def seed_ml_and_anomaly_models() -> None:
    """Bootstrap and persist XGBoost, TreeSHAP, and Composite Anomaly models."""
    logger.info("bootstrapping_machine_learning_models")
    # 1. XGBoost Failure Predictor & TreeSHAP
    reg = ModelRegistry()
    reg.bootstrap_default_models()

    # 2. Anomaly Detectors
    anom_reg = AnomalyDetectorRegistry()
    anom_reg.get_detector()
    logger.info("ml_and_anomaly_models_bootstrapped")


async def seed_showcase_scenarios(session) -> dict[str, Any]:
    """Seed the 4 deterministic showcase demonstration scenarios."""
    logger.info("seeding_showcase_scenarios")
    ingestor = DatasetIngestor(session, tenant_id=DEMO_TENANT_ID)
    rca_engine = RootCauseEngine()
    optimizer = WorkflowOptimizer()
    safety_evaluator = SafetyInvariantEvaluator()
    policy_engine = RemediationPolicyEngine(safety_evaluator=safety_evaluator)
    planner = RemediationActionPlanner(policy_engine=policy_engine)
    actuator = InMemoryRoutingActuator()
    audit_ledger = CryptographicAuditLedger()

    scenario_results: dict[str, Any] = {}

    # --------------------------------------------------------------------------
    # SCENARIO 1: Database Saturation & Causal Root Cause Recovery
    # --------------------------------------------------------------------------
    logger.info("running_scenario_1_database_saturation")
    sim1 = TraceSimulator(
        SimulationConfig(
            seed=101, workflow_count=10, incident_scenario=ChaosScenario.DATABASE_LATENCY
        )
    )
    res1 = sim1.run()
    await ingestor.ingest_simulation_result(res1)

    degraded_exec1 = max(res1.executions, key=lambda e: e.total_latency_ms)
    exec1_events = [ev for ev in res1.events if ev.execution_id == degraded_exec1.id]

    # Run RCA
    rca_report1 = rca_engine.diagnose_execution(
        events=exec1_events,
        execution_id=degraded_exec1.id,
        workflow_definition_id=DEMO_WORKFLOW_ID,
    )

    # Persist RCA Report
    rca_model1 = RootCauseModel(
        id=f"rc_{uuid.uuid4().hex[:10]}",
        execution_id=degraded_exec1.id,
        workflow_definition_id=DEMO_WORKFLOW_ID,
        tenant_id=DEMO_TENANT_ID,
        culprit_service=rca_report1.culprit_service,
        incident_category=rca_report1.incident_category,
        confidence=rca_report1.confidence,
        causal_path=rca_report1.causal_path,
        supporting_evidence=rca_report1.supporting_evidence,
        alternative_hypotheses=[
            {
                "id": h.id,
                "culprit_service": h.culprit_service,
                "incident_category": h.incident_category,
                "confidence": h.confidence,
            }
            for h in rca_report1.alternative_hypotheses
        ],
        analyzed_at=datetime.now(UTC),
    )
    session.add(rca_model1)

    # Run 3D Pareto Optimizer
    opt_rec1 = optimizer.optimize_workflow(
        workflow_definition_id=DEMO_WORKFLOW_ID,
        current_path_id="path_default",
        active_incident_culprit="inventory-db",
        events=res1.events,
    )
    opt_model1 = OptimizationModel(
        id=f"opt_{uuid.uuid4().hex[:10]}",
        workflow_definition_id=DEMO_WORKFLOW_ID,
        tenant_id=DEMO_TENANT_ID,
        optimization_type="INCIDENT_DIVERSION",
        weight_latency=0.40,
        weight_cost=0.30,
        weight_reliability=0.30,
        current_path=dataclasses.asdict(opt_rec1.current_path) if opt_rec1.current_path else {},
        recommended_path=dataclasses.asdict(opt_rec1.recommended_path),
        pareto_frontier=[dataclasses.asdict(p) for p in opt_rec1.pareto_frontier],
        all_evaluated_paths=[dataclasses.asdict(p) for p in opt_rec1.all_evaluated_paths],
        expected_savings=dataclasses.asdict(opt_rec1.expected_savings),
        cost_model_breakdown=dataclasses.asdict(opt_rec1.recommended_path.cost_breakdown)
        if opt_rec1.recommended_path.cost_breakdown
        else {},
        rationale=opt_rec1.rationale,
        active_incident_culprit="inventory-db",
        created_at=datetime.now(UTC),
    )
    session.add(opt_model1)

    # Synthesize & Actuate Remediation Plan
    plan1 = planner.synthesize_plan_from_diagnostics(
        workflow_definition_id=DEMO_WORKFLOW_ID,
        rca_report=rca_report1,
        optimization_recommendation=opt_rec1,
    )

    # Execute in-memory
    _act_res1 = await actuator.actuate(plan1)
    plan1.status = ActionPlanStatus.SUCCEEDED

    # Record Audit Ledger
    audit_entry1 = audit_ledger.append_entry(
        plan_id=plan1.id,
        event_type="PLAN_EXECUTED",
        actor="AUTONOMOUS_POLICY_ENGINE",
        payload={
            "action_type": plan1.action_type.value,
            "target_service": plan1.target_service,
            "divert_target": opt_rec1.recommended_path.path_id,
        },
    )

    plan_model1 = RemediationActionPlanModel(
        id=plan1.id,
        tenant_id=DEMO_TENANT_ID,
        workflow_definition_id=DEMO_WORKFLOW_ID,
        incident_id=plan1.incident_id,
        trigger_rca_id=rca_model1.id,
        action_type=plan1.action_type.value,
        execution_mode=plan1.execution_mode.value,
        status=plan1.status.value,
        target_service=plan1.target_service,
        target_parameters=plan1.target_parameters,
        blast_radius_pct=plan1.blast_radius_pct,
        idempotency_key=f"idemp_{uuid.uuid4().hex[:12]}",
        expected_savings=dataclasses.asdict(opt_rec1.expected_savings),
        safety_report=plan1.safety_report.model_dump() if plan1.safety_report else None,
        created_at=plan1.created_at,
        executed_at=datetime.now(UTC),
    )
    session.add(plan_model1)

    audit_model1 = RemediationAuditLedgerModel(
        entry_id=audit_entry1.entry_id,
        plan_id=plan1.id,
        tenant_id=DEMO_TENANT_ID,
        event_type=audit_entry1.event_type,
        actor=audit_entry1.actor,
        payload=audit_entry1.payload,
        previous_hash=audit_entry1.previous_hash,
        entry_hash=audit_entry1.entry_hash,
        timestamp=audit_entry1.timestamp,
    )
    session.add(audit_model1)

    scenario_results["scenario_1"] = {
        "name": "Database Saturation & Closed-Loop Remediation",
        "execution_id": degraded_exec1.id,
        "culprit_identified": rca_report1.culprit_service,
        "confidence": f"{rca_report1.confidence * 100:.1f}%",
        "latency_reduction": f"{opt_rec1.expected_savings.latency_reduction_pct:.1f}%",
        "plan_id": plan1.id,
        "audit_hash": audit_entry1.entry_hash[:16] + "...",
    }

    # --------------------------------------------------------------------------
    # SCENARIO 2: Cascading Multi-Service Failure & Safety Invariant Rejection
    # --------------------------------------------------------------------------
    logger.info("running_scenario_2_cascading_failure")
    sim2 = TraceSimulator(
        SimulationConfig(
            seed=102, workflow_count=6, incident_scenario=ChaosScenario.CASCADING_FAILURE
        )
    )
    res2 = sim2.run()
    await ingestor.ingest_simulation_result(res2)

    degraded_exec2 = next(
        (e for e in res2.executions if e.status == ExecutionStatus.FAILED), res2.executions[0]
    )
    exec2_events = [ev for ev in res2.events if ev.execution_id == degraded_exec2.id]

    rca_report2 = rca_engine.diagnose_execution(
        events=exec2_events,
        execution_id=degraded_exec2.id,
        workflow_definition_id=DEMO_WORKFLOW_ID,
    )

    # Synthesize an unsafe remediation plan that routes back into an active culprit
    unsafe_plan = RemediationActionPlan(
        id=f"plan-unsafe-{uuid.uuid4().hex[:8]}",
        workflow_definition_id=DEMO_WORKFLOW_ID,
        incident_id=degraded_exec2.id,
        action_type=ActionType.TRAFFIC_DIVERT,
        execution_mode=ExecutionMode.AUTONOMOUS,
        status=ActionPlanStatus.STAGED,
        target_service="payment-service",
        target_parameters={"target_path_services": ["payment-service", "customer-service"]},
        blast_radius_pct=0.30,
        idempotency_key=f"unsafe_key_{uuid.uuid4().hex[:12]}",
        pre_actuation_state_snapshot=StateSnapshot(),
    )
    # Evaluate safety guards -> expect rejection due to active culprit traversal
    safety_report2 = safety_evaluator.evaluate_all_invariants(
        plan=unsafe_plan,
        root_cause_culprit="payment-service",
        target_path_services=["payment-service", "customer-service"],
        actuation_history=[],
    )
    unsafe_plan.safety_report = safety_report2
    unsafe_plan.status = (
        ActionPlanStatus.SUCCEEDED if safety_report2.is_safe else ActionPlanStatus.FAILED
    )

    plan_model2 = RemediationActionPlanModel(
        id=unsafe_plan.id,
        tenant_id=DEMO_TENANT_ID,
        workflow_definition_id=DEMO_WORKFLOW_ID,
        incident_id=unsafe_plan.incident_id,
        trigger_rca_id=f"rc_{uuid.uuid4().hex[:10]}",
        action_type=unsafe_plan.action_type.value,
        execution_mode=unsafe_plan.execution_mode.value,
        status=unsafe_plan.status.value,
        target_service=unsafe_plan.target_service,
        target_parameters=unsafe_plan.target_parameters,
        blast_radius_pct=0.30,
        idempotency_key=unsafe_plan.idempotency_key,
        safety_report=safety_report2.model_dump(),
        created_at=unsafe_plan.created_at,
    )
    session.add(plan_model2)

    scenario_results["scenario_2"] = {
        "name": "Cascading Failure & Safety Invariant Rejection",
        "execution_id": degraded_exec2.id,
        "culprit_identified": rca_report2.culprit_service,
        "plan_status": unsafe_plan.status.value,
        "safety_rejections": safety_report2.rejection_reasons,
    }

    # --------------------------------------------------------------------------
    # SCENARIO 3: Upstream Retry Storm & Anti-Flapping Cooldown
    # --------------------------------------------------------------------------
    logger.info("running_scenario_3_retry_storm")
    sim3 = TraceSimulator(
        SimulationConfig(seed=103, workflow_count=6, incident_scenario=ChaosScenario.RETRY_STORM)
    )
    res3 = sim3.run()
    await ingestor.ingest_simulation_result(res3)

    degraded_exec3 = max(res3.executions, key=lambda e: e.retry_count)
    exec3_events = [ev for ev in res3.events if ev.execution_id == degraded_exec3.id]

    rca_report3 = rca_engine.diagnose_execution(
        events=exec3_events,
        execution_id=degraded_exec3.id,
        workflow_definition_id=DEMO_WORKFLOW_ID,
    )

    scenario_results["scenario_3"] = {
        "name": "Upstream Retry Storm & Anomaly Cascade",
        "execution_id": degraded_exec3.id,
        "culprit_identified": rca_report3.culprit_service,
        "confidence": f"{rca_report3.confidence * 100:.1f}%",
    }

    # --------------------------------------------------------------------------
    # SCENARIO 4: Nominal System Performance Baseline
    # --------------------------------------------------------------------------
    logger.info("running_scenario_4_nominal_baseline")
    sim4 = TraceSimulator(SimulationConfig(seed=42, workflow_count=20))
    res4 = sim4.run()
    await ingestor.ingest_simulation_result(res4)

    scenario_results["scenario_4"] = {
        "name": "Nominal Multi-Service Benchmark",
        "total_nominal_executions": len(res4.executions),
        "mean_latency_ms": f"{sum(e.total_latency_ms for e in res4.executions) / len(res4.executions):.1f}ms",
    }

    await session.commit()
    return scenario_results


async def main() -> None:
    """Execute complete TraceMind demo bootstrap sequence."""
    t0 = time.perf_counter()
    print("=" * 80)
    print("        TraceMind Showcase & Demo Bootstrap Initializer (M0–M15)        ")
    print("=" * 80)

    # 1. Initialize Tables
    print("[1/5] Initializing database schema...")
    engine = get_async_engine()
    await init_db(engine)

    session_factory = get_async_session_factory(engine)
    async with session_factory() as session:
        # 2. Seed Services & Workflows
        print("[2/5] Seeding microservice topology & workflow DAGs...")
        await seed_services_and_workflows(session)

        # 3. Seed Security & Credentials
        print("[3/5] Seeding tenants, users, and fixed demo API keys...")
        await seed_security_and_users(session)

        # 4. Bootstrap ML & Anomaly Models
        print("[4/5] Training in-process ML predictors & anomaly baselines...")
        await seed_ml_and_anomaly_models()

        # 5. Seed Showcase Scenarios
        print("[5/5] Generating 4 deterministic showcase scenarios...")
        scenarios = await seed_showcase_scenarios(session)

    elapsed = time.perf_counter() - t0
    print("\n" + "=" * 80)
    print(f"   >>> TRACEMIND DEMO BOOTSTRAP COMPLETE IN {elapsed:.2f} SECONDS <<<   ")
    print("=" * 80)
    print("\n SHOWCASE ACCESS CREDENTIALS:")
    print("  • Web Dashboard URL : http://localhost (or Codespaces forwarded port 80)")
    print("  • System Admin User : admin@tracemind.io / TraceMind#Admin2026!")
    print("  • Public Viewer User: viewer@tracemind.io / Viewer#Demo2026!")
    print("  • Fixed Demo API Key: tm_live_demo_0123456789abcdef0123456789abcdef")
    print("  • OpenAPI Swagger   : http://localhost/docs")

    print("\n SEEDED SHOWCASE SCENARIOS FOR LIVE PRESENTATION:")
    for key, data in scenarios.items():
        print(f"  [{key.upper()}] {data['name']}")
        for k, v in data.items():
            if k != "name":
                print(f"      • {k}: {v}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
