"""Integration tests for FastAPI Conversational AI Analyst REST & Streaming endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_analyst_chat_and_persistence(async_client: AsyncClient):
    """Test POST /api/v1/analyst/chat and conversation session creation."""
    payload = {
        "query": "What caused the failure in order_fulfillment execution exec_4a9b?",
        "workflow_definition_id": "order_fulfillment",
        "execution_id": "exec_4a9b",
        "provider": "mock",
        "persist": True,
    }

    resp = await async_client.post("/api/v1/analyst/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert "message_id" in data
    assert len(data["tool_calls"]) >= 1
    assert data["tool_calls"][0]["name"] == "get_root_cause_diagnosis"
    assert len(data["tool_results"]) >= 1
    assert "grounding_report" in data
    assert data["grounding_report"]["is_grounded"]
    assert data["grounding_report"]["grounding_score"] >= 0.80
    assert len(data["grounding_report"]["citations"]) >= 1

    conv_id = data["conversation_id"]

    # 2. Fetch full conversation transcript
    get_resp = await async_client.get(f"/api/v1/analyst/conversations/{conv_id}")
    assert get_resp.status_code == 200
    conv_data = get_resp.json()
    assert conv_data["id"] == conv_id
    assert len(conv_data["messages"]) >= 2  # user + assistant


@pytest.mark.asyncio
async def test_api_analyst_chat_stream(async_client: AsyncClient):
    """Test POST /api/v1/analyst/chat/stream Server-Sent Events output."""
    payload = {
        "query": "What is the recommended detour path around inventory-db?",
        "provider": "mock",
    }

    resp = await async_client.post("/api/v1/analyst/chat/stream", json=payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    content = resp.text
    assert "data: " in content
    assert "tool_call" in content or "token" in content
    assert "done" in content


@pytest.mark.asyncio
async def test_api_analyst_conversations_crud(async_client: AsyncClient):
    """Test listing and deleting conversation sessions."""
    # 1. Create a turn
    chat_resp = await async_client.post(
        "/api/v1/analyst/chat",
        json={"query": "Show system topology", "provider": "mock", "persist": True},
    )
    assert chat_resp.status_code == 200
    conv_id = chat_resp.json()["conversation_id"]

    # 2. List conversations
    list_resp = await async_client.get("/api/v1/analyst/conversations")
    assert list_resp.status_code == 200
    convs = list_resp.json()
    assert any(c["id"] == conv_id for c in convs)

    # 3. Delete conversation
    del_resp = await async_client.delete(f"/api/v1/analyst/conversations/{conv_id}")
    assert del_resp.status_code == 204

    # 4. Verify 404 on deleted conversation
    get_del = await async_client.get(f"/api/v1/analyst/conversations/{conv_id}")
    assert get_del.status_code == 404


@pytest.mark.asyncio
async def test_api_analyst_tools_catalog_and_stats(async_client: AsyncClient):
    """Test GET /api/v1/analyst/tools and GET /api/v1/analyst/stats."""
    # 1. Tools catalog
    tools_resp = await async_client.get("/api/v1/analyst/tools")
    assert tools_resp.status_code == 200
    tools = tools_resp.json()
    assert len(tools) >= 6
    names = [t["name"] for t in tools]
    assert "get_system_topology" in names
    assert "get_root_cause_diagnosis" in names
    assert "get_workflow_optimization" in names

    # 2. Stats
    stats_resp = await async_client.get("/api/v1/analyst/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_conversations" in stats
    assert "total_messages" in stats
    assert "average_grounding_score" in stats
