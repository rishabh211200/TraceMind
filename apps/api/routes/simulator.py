"""FastAPI routes for simulation control, scenario catalog, and chaos injection."""

import asyncio
import random
import time

import numpy as np
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.exceptions import ValidationException
from apps.api.schemas.simulator import (
    ChaosInjectionRequest,
    ChaosInjectionResponse,
    ChaosScenarioInfo,
    SimulationGenerateRequest,
    SimulationGenerateResponse,
)
from apps.simulator.config import SimulationConfig
from apps.simulator.incidents import INCIDENT_PRESETS, ChaosScenario
from apps.simulator.workflow_engine import TraceSimulator
from packages.database.ingestion import DatasetIngestor
from packages.database.session import get_db_session
from packages.domain.workflow import ExecutionStatus

router = APIRouter(prefix="/api/v1/simulator", tags=["Simulator & Chaos Controls"])


@router.get(
    "/scenarios",
    response_model=list[ChaosScenarioInfo],
    summary="List Chaos Incident Scenarios",
)
async def list_scenarios() -> list[ChaosScenarioInfo]:
    """Retrieve catalog of all supported causal chaos incident scenarios."""
    scenarios: list[ChaosScenarioInfo] = []
    for scenario_enum, preset in INCIDENT_PRESETS.items():
        scenarios.append(
            ChaosScenarioInfo(
                scenario_type=scenario_enum.value.lower(),
                name=preset["name"],
                description=preset["description"],
                severity=preset["severity"].value,
                affected_services=preset["affected_services"],
                ground_truth_root_cause=preset["ground_truth_root_cause"],
                default_parameters=preset.get("parameters", {}),
            )
        )
    return scenarios


@router.post(
    "/generate",
    response_model=SimulationGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Synthetic Simulation Run",
)
async def generate_simulation(
    payload: SimulationGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SimulationGenerateResponse:
    """Generate synthetic workflow traces with configurable workload, seed, and chaos scenarios."""
    seed = payload.seed if payload.seed is not None else random.randint(1, 1_000_000)

    # Validate chaos scenario if provided
    selected_scenario = None
    if payload.incident_scenario:
        try:
            selected_scenario = ChaosScenario(payload.incident_scenario.upper())
        except ValueError:
            valid = [s.value.lower() for s in ChaosScenario]
            raise ValidationException(
                f"Invalid incident_scenario '{payload.incident_scenario}'. Valid options: {valid}"
            ) from None

    # Run discrete-event simulation in worker thread
    def _run_sim():
        cfg = SimulationConfig(
            seed=seed,
            workflow_count=payload.workflow_count,
            arrival_rate_per_second=payload.arrival_rate_rps,
            incident_scenario=selected_scenario,
        )
        sim = TraceSimulator(cfg)
        t0 = time.perf_counter()
        res = sim.run()
        gen_duration_ms = (time.perf_counter() - t0) * 1000.0
        return res, gen_duration_ms

    result, gen_duration_ms = await asyncio.to_thread(_run_sim)

    persisted_executions = 0
    persisted_events = 0
    persist_duration_ms = None

    if payload.persist_to_db:
        t_persist_start = time.perf_counter()
        ingestor = DatasetIngestor(session)
        report = await ingestor.ingest_simulation_result(result)
        persist_duration_ms = (time.perf_counter() - t_persist_start) * 1000.0
        persisted_executions = report.executions_count
        persisted_events = report.events_count

    total = len(result.executions)
    completed = sum(1 for e in result.executions if e.status == ExecutionStatus.COMPLETED)
    failed = sum(1 for e in result.executions if e.status == ExecutionStatus.FAILED)
    timeout = sum(1 for e in result.executions if e.status == ExecutionStatus.TIMEOUT)
    success_rate = (completed / total * 100.0) if total > 0 else 0.0
    error_rate = ((failed + timeout) / total * 100.0) if total > 0 else 0.0
    total_retries = sum(e.retry_count for e in result.executions)
    retry_rate = (total_retries / total * 100.0) if total > 0 else 0.0

    durations = [e.total_latency_ms for e in result.executions]
    if durations:
        mean_lat = float(np.mean(durations))
        p95_lat = float(np.percentile(durations, 95))
        p99_lat = float(np.percentile(durations, 99))
    else:
        mean_lat = p95_lat = p99_lat = 0.0

    summary = {
        "completed_count": completed,
        "failed_count": failed,
        "timeout_count": timeout,
        "success_rate_percent": round(success_rate, 2),
        "error_rate_percent": round(error_rate, 2),
        "retry_rate_percent": round(retry_rate, 2),
        "mean_latency_ms": round(mean_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "p99_latency_ms": round(p99_lat, 2),
    }

    return SimulationGenerateResponse(
        seed=seed,
        workflows_requested=payload.workflow_count,
        executions_generated=len(result.executions),
        events_generated=len(result.events),
        incidents_generated=len(result.incidents),
        generation_wall_time_ms=round(gen_duration_ms, 2),
        persisted_to_db=payload.persist_to_db,
        persisted_executions_count=persisted_executions,
        persisted_events_count=persisted_events,
        persistence_wall_time_ms=round(persist_duration_ms, 2)
        if persist_duration_ms is not None
        else None,
        summary_statistics=summary,
    )


@router.post(
    "/inject-chaos",
    response_model=ChaosInjectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Inject Chaos Incident Scenario",
)
async def inject_chaos(
    payload: ChaosInjectionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChaosInjectionResponse:
    """Inject a targeted chaos scenario and simulate its downstream cascading effects."""
    try:
        scenario = ChaosScenario(payload.scenario_type.upper())
    except ValueError:
        valid = [s.value.lower() for s in ChaosScenario]
        raise ValidationException(
            f"Invalid chaos scenario_type '{payload.scenario_type}'. Valid options: {valid}"
        ) from None

    seed = payload.seed if payload.seed is not None else random.randint(1, 1_000_000)

    def _run_chaos():
        cfg = SimulationConfig(
            seed=seed,
            workflow_count=payload.workflow_count,
            arrival_rate_per_second=payload.arrival_rate_rps,
            incident_scenario=scenario,
        )
        sim = TraceSimulator(cfg)
        return sim.run()

    result = await asyncio.to_thread(_run_chaos)

    if payload.persist_to_db:
        ingestor = DatasetIngestor(session)
        await ingestor.ingest_simulation_result(result)

    incident = result.incidents[0] if result.incidents else None
    affected_count = sum(
        1 for e in result.executions if e.metadata.get("is_incident_affected", False)
    )

    total = len(result.executions)
    failed = sum(1 for e in result.executions if e.status == ExecutionStatus.FAILED)
    timeout = sum(1 for e in result.executions if e.status == ExecutionStatus.TIMEOUT)
    error_rate = ((failed + timeout) / total * 100.0) if total > 0 else 0.0
    total_retries = sum(e.retry_count for e in result.executions)
    retry_rate = (total_retries / total * 100.0) if total > 0 else 0.0

    durations = [e.total_latency_ms for e in result.executions]
    mean_lat = float(np.mean(durations)) if durations else 0.0

    preset = INCIDENT_PRESETS.get(scenario, {})

    return ChaosInjectionResponse(
        incident_id=incident.id if incident else "inc_manual",
        scenario_type=scenario.value.lower(),
        affected_services=incident.affected_services
        if incident
        else preset.get("affected_services", []),
        ground_truth_root_cause=incident.ground_truth_root_cause
        if incident
        else preset.get("ground_truth_root_cause", ""),
        total_executions=len(result.executions),
        executions_affected=affected_count,
        mean_latency_ms=round(mean_lat, 2),
        error_rate_percent=round(error_rate, 2),
        retry_rate_percent=round(retry_rate, 2),
        persisted_to_db=payload.persist_to_db,
    )
