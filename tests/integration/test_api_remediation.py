"""Integration tests for FastAPI Remediation API routes and AI Analyst execution tools."""

import pytest
from httpx import AsyncClient

from apps.ml.analyst.tools import ToolRegistry


@pytest.mark.asyncio
async def test_api_remediation_lifecycle(async_client: AsyncClient):
    """Tests end-to-end plan synthesis, execution, health verification, and exact rollback."""
    # 1. Synthesize Plan
    synth_req = {
        "workflow_definition_id": "order_fulfillment",
        "incident_category": "DATABASE_IOPS_SATURATION",
        "root_cause_service": "customer-db",
        "diagnostic_confidence": 0.98,
    }
    resp = await async_client.post("/api/v1/remediations/plans/synthesize", json=synth_req)
    assert resp.status_code == 201
    plan_data = resp.json()
    assert "id" in plan_data
    assert plan_data["workflow_definition_id"] == "order_fulfillment"
    assert plan_data["action_type"] == "TRAFFIC_DIVERT"
    assert plan_data["target_service"] == "customer-db"
    assert plan_data["blast_radius_pct"] == 0.25
    assert plan_data["status"] in ("ACTIVE_VERIFYING", "SUCCEEDED", "STAGED")

    plan_id = plan_data["id"]

    # 2. Get Plan by ID
    get_resp = await async_client.get(f"/api/v1/remediations/plans/{plan_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == plan_id

    # 3. List Plans
    list_resp = await async_client.get("/api/v1/remediations/plans")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 4. Emergency Rollback
    rb_resp = await async_client.post(f"/api/v1/remediations/plans/{plan_id}/rollback")
    assert rb_resp.status_code == 200
    assert rb_resp.json()["status"] == "ROLLED_BACK"

    # 5. Verify Cryptographic Audit Ledger
    audit_resp = await async_client.get("/api/v1/remediations/audit-ledger")
    assert audit_resp.status_code == 200
    assert len(audit_resp.json()) >= 1

    verify_resp = await async_client.get("/api/v1/remediations/audit-ledger/verify")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_valid"] is True


@pytest.mark.asyncio
async def test_api_remediation_policies(async_client: AsyncClient):
    """Tests policy listing, registration, and deletion."""
    # 1. List default seeded policies
    list_resp = await async_client.get("/api/v1/remediations/policies")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 5

    # 2. Create custom policy
    new_policy = {
        "name": "Custom Cache Diversion Policy",
        "workflow_definition_id": "order_fulfillment",
        "incident_category": "DATABASE_IOPS_SATURATION",
        "action_type": "CACHE_FALLBACK_ACTUATE",
        "execution_mode": "SUPERVISED",
        "max_blast_radius": 0.20,
        "cooldown_seconds": 120,
        "verification_timeout_seconds": 30,
    }
    create_resp = await async_client.post("/api/v1/remediations/policies", json=new_policy)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == new_policy["name"]

    # 3. Delete policy
    del_resp = await async_client.delete(f"/api/v1/remediations/policies/{created['id']}")
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_api_mesh_state(async_client: AsyncClient):
    """Tests retrieval of active runtime mesh state."""
    resp = await async_client.get("/api/v1/remediations/mesh-state")
    assert resp.status_code == 200
    data = resp.json()
    assert "routing_weights" in data
    assert "circuit_states" in data
    assert "concurrency_limits" in data
    assert "retry_multipliers" in data


@pytest.mark.asyncio
async def test_ai_analyst_remediation_tools():
    """Tests invocation of remediation tools directly from AI Analyst ToolRegistry."""
    registry = ToolRegistry()

    # 1. Simulate Remediation
    sim_res = await registry.execute_tool(
        "simulate_remediation",
        {
            "workflow_definition_id": "order_fulfillment",
            "incident_category": "DATABASE_IOPS_SATURATION",
            "root_cause_service": "customer-db",
        },
    )
    assert not sim_res.is_error
    assert isinstance(sim_res.result, dict)
    assert sim_res.result["action_type"] == "TRAFFIC_DIVERT"
    assert sim_res.result["is_safe"] is True
    plan_id = str(sim_res.result["plan_id"])

    # 2. Actuate Mitigation
    act_res = await registry.execute_tool(
        "actuate_mitigation",
        {
            "workflow_definition_id": "order_fulfillment",
            "incident_category": "DATABASE_IOPS_SATURATION",
            "root_cause_service": "customer-db",
            "operator_confirmation": True,
        },
    )
    assert not act_res.is_error
    assert isinstance(act_res.result, dict)
    assert act_res.result["actuation_status"] == "COMMITTED"
    assert act_res.result["is_health_recovered"] is True

    # 3. Rollback Mitigation
    rb_res = await registry.execute_tool(
        "rollback_mitigation",
        {"plan_id": plan_id},
    )
    assert not rb_res.is_error
    assert isinstance(rb_res.result, dict)
    assert rb_res.result["status"] == "ROLLED_BACK"

    # 4. Get Mesh State
    state_res = await registry.execute_tool("get_remediation_mesh_state", {})
    assert not state_res.is_error
    assert isinstance(state_res.result, dict)
    assert "routing_weights" in state_res.result
