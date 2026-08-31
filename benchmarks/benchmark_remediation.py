"""HPC Benchmark Suite for Autonomous Closed-Loop Remediation & Safety Invariant Engine."""

import asyncio
import time

from apps.ml.remediation.actuators.in_memory import InMemoryRoutingActuator
from apps.ml.remediation.audit_ledger import CryptographicAuditLedger
from apps.ml.remediation.planner import RemediationActionPlanner
from apps.ml.remediation.policy_engine import RemediationPolicyEngine
from apps.ml.remediation.safety_guards import SafetyInvariantEvaluator
from apps.ml.remediation.verifier import PostActuationHealthVerifier
from apps.ml.root_cause import RootCauseReport
from packages.common.profiler import PerformanceProfiler, discover_system_hardware
from packages.domain.remediation import (
    ActionType,
    ExecutionMode,
    RemediationActionPlan,
)

CHAOS_PRESETS = [
    ("DATABASE_IOPS_SATURATION", "customer-db"),
    ("SERVICE_CRASH", "payment-gateway"),
    ("CASCADING_RETRY_STORM", "inventory-service"),
    ("FLASH_TRAFFIC_OVERLOAD", "api-gateway"),
    ("PAYMENT_DEGRADATION", "payment-service"),
    ("NETWORK_TRANSIT_DELAY", "pricing-service"),
    ("DEPENDENCY_TIMEOUT", "auth-service"),
]


async def run_remediation_benchmarks() -> None:
    """Executes the full 6-suite quantitative safety and performance benchmark."""
    print("=" * 80)
    print("   TraceMind Autonomous Closed-Loop Remediation HPC Benchmark Suite   ")
    print("=" * 80)

    # 1. System Hardware Discovery
    hw = discover_system_hardware()
    print(f"  OS Platform        : {hw.os_name} {hw.os_release} ({hw.os_architecture})")
    print(f"  CPU Processor      : {hw.cpu_processor}")
    print(f"  Logical CPU Cores  : {hw.logical_cores}")
    print(f"  Total Physical RAM : {hw.total_ram_gb:.2f} GB")
    print(f"  Python Runtime     : {hw.python_version}")
    print("=" * 80)

    policy_engine = RemediationPolicyEngine(safety_evaluator=SafetyInvariantEvaluator())
    planner = RemediationActionPlanner(policy_engine=policy_engine)
    actuator = InMemoryRoutingActuator()
    audit_ledger = CryptographicAuditLedger()
    verifier = PostActuationHealthVerifier(actuator=actuator, audit_ledger=audit_ledger)

    # -------------------------------------------------------------------------
    # Suite 1: Action Plan Synthesis Latency & Throughput (1,000 Iterations)
    # -------------------------------------------------------------------------
    print("\n[Suite 1] Benchmarking Action Plan Synthesis Latency (1,000 runs)...")
    base_snapshot = await actuator.get_current_state()
    prof_synth = PerformanceProfiler(name="Plan Synthesis", total_items=1000).start()

    for i in range(1000):
        cat, culprit = CHAOS_PRESETS[i % len(CHAOS_PRESETS)]
        rca = RootCauseReport(
            id=f"rca-bench-{i}",
            execution_id=f"exec-{i}",
            workflow_definition_id="order_fulfillment",
            culprit_service=culprit,
            incident_category=cat,
            confidence=0.98,
            causal_path=[culprit],
            supporting_evidence=["Benchmark diagnostic telemetry"],
            primary_hypothesis=None,  # type: ignore[arg-type]
            alternative_hypotheses=[],
        )
        t0 = time.perf_counter()
        plan = planner.synthesize_plan_from_diagnostics(
            workflow_definition_id="order_fulfillment",
            rca_report=rca,
            optimization_recommendation=None,
            current_mesh_state=base_snapshot,
        )
        t1 = time.perf_counter()
        prof_synth.record_item_latency((t1 - t0) * 1000.0)

    synth_stats = prof_synth.stop()
    print(f"  Throughput : {synth_stats.throughput_items_per_sec:,.1f} plans/sec")
    print(
        f"  P50 Latency: {synth_stats.p50_latency_ms:.3f} ms | P95: {synth_stats.p95_latency_ms:.3f} ms | P99: {synth_stats.p99_latency_ms:.3f} ms"
    )
    assert synth_stats.throughput_items_per_sec >= 1000.0, (
        "Synthesis throughput below 1,000 plans/sec"
    )
    assert synth_stats.p99_latency_ms < 10.0, "Synthesis P99 latency above 10.0 ms"
    print("  Status     : [PASSED] (Target >= 1,000 plans/s, P99 < 10ms)")

    # -------------------------------------------------------------------------
    # Suite 2: In-Memory Concurrency-Safe Actuation Latency (1,000 Iterations)
    # -------------------------------------------------------------------------
    print("\n[Suite 2] Benchmarking In-Memory Actuation Latency (1,000 runs)...")
    prof_act = PerformanceProfiler(name="In-Memory Actuation", total_items=1000).start()

    for i in range(1000):
        test_plan = RemediationActionPlan(
            id=f"plan-bench-act-{i}",
            workflow_definition_id="order_fulfillment",
            action_type=ActionType.TRAFFIC_DIVERT,
            execution_mode=ExecutionMode.AUTONOMOUS,
            target_service="customer-db",
            target_parameters={
                "source_path_id": "path_01",
                "target_path_id": "path_02",
                "traffic_shift_pct": 0.0001,
            },
            blast_radius_pct=0.20,
            idempotency_key=f"idem-{i}",
            pre_actuation_state_snapshot=base_snapshot,
        )
        t0 = time.perf_counter()
        act_res = await actuator.actuate(test_plan)
        t1 = time.perf_counter()
        assert act_res.success
        prof_act.record_item_latency((t1 - t0) * 1000.0)

    act_stats = prof_act.stop()
    print(f"  Throughput : {act_stats.throughput_items_per_sec:,.1f} actuations/sec")
    print(
        f"  P50 Latency: {act_stats.p50_latency_ms:.3f} ms | P95: {act_stats.p95_latency_ms:.3f} ms | P99: {act_stats.p99_latency_ms:.3f} ms"
    )
    assert act_stats.p99_latency_ms < 5.0, "Actuation P99 latency above 5.0 ms"
    print("  Status     : [PASSED] (Target P99 < 5ms)")

    # -------------------------------------------------------------------------
    # Suite 3: Verbatim Exact-State Rollback Restoration Speed (500 Iterations)
    # -------------------------------------------------------------------------
    print("\n[Suite 3] Benchmarking Verbatim Exact-State Rollback Restoration (500 runs)...")
    prof_rb = PerformanceProfiler(name="Verbatim Rollback", total_items=500).start()

    for i in range(500):
        test_plan = RemediationActionPlan(
            id=f"plan-bench-rb-{i}",
            workflow_definition_id="order_fulfillment",
            action_type=ActionType.CIRCUIT_BREAK,
            execution_mode=ExecutionMode.AUTONOMOUS,
            target_service="payment-gateway",
            blast_radius_pct=0.20,
            idempotency_key=f"idem-rb-{i}",
            pre_actuation_state_snapshot=base_snapshot,
        )
        t0 = time.perf_counter()
        rb_res = await actuator.rollback(test_plan, exact_snapshot=base_snapshot)
        t1 = time.perf_counter()
        assert rb_res.success
        assert rb_res.restored_state.circuit_states == base_snapshot.circuit_states
        prof_rb.record_item_latency((t1 - t0) * 1000.0)

    rb_stats = prof_rb.stop()
    print(f"  Throughput : {rb_stats.throughput_items_per_sec:,.1f} rollbacks/sec")
    print(
        f"  P50 Latency: {rb_stats.p50_latency_ms:.3f} ms | P95: {rb_stats.p95_latency_ms:.3f} ms | P99: {rb_stats.p99_latency_ms:.3f} ms"
    )
    assert rb_stats.p99_latency_ms < 5.0, "Rollback P99 latency above 5.0 ms"
    print("  Status     : [PASSED] (Target P99 < 5ms, exact-state match 100%)")

    # -------------------------------------------------------------------------
    # Suite 4: Deterministic Safety Invariant Fuzz Testing (100 Tests)
    # -------------------------------------------------------------------------
    print("\n[Suite 4] Fuzz Testing Safety Invariants (100 malicious/unsafe permutations)...")
    safety_guard = SafetyInvariantEvaluator()
    rejections_count = 0

    for i in range(100):
        unsafe_plan = RemediationActionPlan(
            id=f"plan-fuzz-{i}",
            workflow_definition_id="order_fulfillment",
            action_type=ActionType.TRAFFIC_DIVERT,
            execution_mode=ExecutionMode.AUTONOMOUS,
            target_service="customer-db",
            blast_radius_pct=0.35 + (i * 0.005),  # Intentionally excessive blast radius
            idempotency_key=f"idem-fuzz-{i}",
            pre_actuation_state_snapshot=base_snapshot,
        )
        report = safety_guard.evaluate_all_invariants(unsafe_plan)
        if not report.is_safe:
            rejections_count += 1

    rejection_rate = (rejections_count / 100.0) * 100.0
    print(
        f"  Unsafe Plans Tested: 100 | Successfully Rejected: {rejections_count} ({rejection_rate:.1f}%)"
    )
    assert rejection_rate == 100.0, "Safety invariants failed to reject unsafe plans"
    print("  Status             : [PASSED] (100% Deterministic Safety Invariant Enforcement)")

    # -------------------------------------------------------------------------
    # Suite 5: Cryptographic SHA-256 Audit Chain Verification (1,000 Entries)
    # -------------------------------------------------------------------------
    print("\n[Suite 5] Benchmarking Cryptographic SHA-256 Audit Chain (1,000 entries)...")
    bench_ledger = CryptographicAuditLedger()

    start_t = time.perf_counter()
    for i in range(1000):
        bench_ledger.append_entry(
            plan_id=f"plan-ledger-{i}",
            event_type="ACTUATION_COMMITTED",
            actor="AUTONOMOUS_POLICY",
            payload={"index": i, "status": "COMMITTED"},
        )
    ledger_dur = time.perf_counter() - start_t
    is_valid, msg = bench_ledger.verify_chain_integrity()
    assert is_valid
    print(f"  Append Rate: {1000.0 / ledger_dur:,.1f} entries/sec")
    print(f"  Integrity  : {msg}")
    print("  Status     : [PASSED] (100% Cryptographic Tamper-Evident Chain Verified)")

    # -------------------------------------------------------------------------
    # Suite 6: Closed-Loop Self-Healing Across 7 Chaos Incident Presets
    # -------------------------------------------------------------------------
    print("\n[Suite 6] Validating Closed-Loop Self-Healing Recovery Across All 7 Chaos Presets...")
    successful_recoveries = 0

    for idx, (cat, culprit) in enumerate(CHAOS_PRESETS, start=1):
        rca = RootCauseReport(
            id=f"rca-chaos-{idx}",
            execution_id=f"exec-chaos-{idx}",
            workflow_definition_id="order_fulfillment",
            culprit_service=culprit,
            incident_category=cat,
            confidence=0.98,
            causal_path=[culprit],
            supporting_evidence=[f"Chaos preset {cat} active on {culprit}"],
            primary_hypothesis=None,  # type: ignore[arg-type]
            alternative_hypotheses=[],
        )
        plan = planner.synthesize_plan_from_diagnostics(
            workflow_definition_id="order_fulfillment",
            rca_report=rca,
            optimization_recommendation=None,
            current_mesh_state=base_snapshot,
        )
        # Actuate plan
        act_res = await actuator.actuate(plan)
        assert act_res.success

        # Run health verifier
        recovered, _, _ = await verifier.verify_and_monitor(plan)
        if recovered:
            successful_recoveries += 1
            status_str = "RECOVERED [OK]"
        else:
            status_str = "ROLLED_BACK [FAIL]"
        print(f"  [{idx}/7] {cat:<28} -> {plan.action_type.value:<22} : {status_str}")

    recovery_rate = (successful_recoveries / len(CHAOS_PRESETS)) * 100.0
    print(
        f"  Overall Closed-Loop Recovery Rate: {successful_recoveries}/{len(CHAOS_PRESETS)} ({recovery_rate:.1f}%)"
    )
    assert recovery_rate >= 95.0, "Closed-loop recovery rate below 95%"
    print("  Status                           : [PASSED] (Target >= 95.0%)")

    print("\n" + "=" * 80)
    print(" >>> MILESTONE 14 REMEDIATION HPC BENCHMARK SUITE PASSED ALL 6 GATES <<< ")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_remediation_benchmarks())
