"""FastAPI REST & Streaming routes for Tool-Grounded Conversational AI Analyst."""

import json
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas.analyst import (
    AnalystStatsResponse,
    ChatRequest,
    ChatResponse,
    CitationSchema,
    ConversationDetailResponse,
    ConversationItemResponse,
    GroundingReportSchema,
    MessageDetailSchema,
    ToolCallSchema,
    ToolDefinitionSchema,
    ToolResultSchema,
)
from apps.ml.analyst.engine import AIAnalystEngine
from apps.ml.analyst.llm_client import MockLLMClient, OpenAILLMClient
from apps.ml.analyst.models import ChatMessage, LLMConfig
from packages.common.logging import get_logger
from packages.database.repositories.analyst_repository import AnalystRepository
from packages.database.session import get_db_session

logger = get_logger("tracemind.api.analyst")

router = APIRouter(prefix="/api/v1/analyst", tags=["AI Analyst"])

_engine: AIAnalystEngine | None = None


def get_analyst_engine() -> AIAnalystEngine:
    """Singleton provider for AIAnalystEngine."""
    global _engine
    if _engine is None:
        _engine = AIAnalystEngine()
    return _engine


def _resolve_provider(
    provider_name: str,
) -> Literal["mock", "openai", "anthropic", "gemini"]:
    """Safely narrow string to supported provider literal."""
    if provider_name in ("mock", "openai", "anthropic", "gemini"):
        return provider_name  # type: ignore[return-value]
    return "mock"


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Conversational diagnostic chat (synchronous)",
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
    engine: AIAnalystEngine = Depends(get_analyst_engine),
) -> ChatResponse:
    """Process a natural language diagnostic query, execute agentic tools, and return a grounded response."""
    repo = AnalystRepository(db)
    conv_id = payload.conversation_id

    # 1. Retrieve or initialize conversation session
    history_messages: list[ChatMessage] = []
    if conv_id and payload.persist:
        conv = await repo.get_conversation(conv_id)
        if conv:
            for m in conv.messages:
                history_messages.append(
                    ChatMessage(
                        id=m.id,
                        role=m.role,  # type: ignore[arg-type]
                        content=m.content,
                    )
                )
        else:
            conv = await repo.create_conversation(
                title=payload.query[:60],
                workflow_definition_id=payload.workflow_definition_id,
                execution_id=payload.execution_id,
                conversation_id=conv_id,
            )
    elif payload.persist:
        conv = await repo.create_conversation(
            title=payload.query[:60],
            workflow_definition_id=payload.workflow_definition_id,
            execution_id=payload.execution_id,
        )
        conv_id = conv.id

    # 2. Select LLM Client based on requested provider
    provider_str = _resolve_provider(payload.provider)
    cfg = LLMConfig(provider=provider_str)
    if payload.provider == "openai":
        engine.llm_client = OpenAILLMClient()
    else:
        engine.llm_client = MockLLMClient()

    # 3. Execute agentic chat
    response = await engine.chat(
        query=payload.query,
        history=history_messages,
        conversation_id=conv_id,
        config=cfg,
    )

    # 4. Record Prometheus Metrics & Persist user & assistant turns if enabled
    from packages.observability.metrics import record_analyst_query

    record_analyst_query(
        provider=provider_str,
        status="success",
        grounding_score=response.grounding_report.grounding_score,
    )

    if payload.persist and conv_id:
        await repo.add_message(
            conversation_id=conv_id,
            role="user",
            content=payload.query,
        )
        await repo.add_message(
            conversation_id=conv_id,
            role="assistant",
            content=response.content,
            tool_calls=[
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in response.tool_calls
            ],
            tool_results=[
                {
                    "call_id": tr.call_id,
                    "name": tr.name,
                    "result": tr.result,
                    "execution_time_ms": tr.execution_time_ms,
                    "is_error": tr.is_error,
                }
                for tr in response.tool_results
            ],
            citations=[c.to_dict() for c in response.grounding_report.citations],
            grounding_score=response.grounding_report.grounding_score,
        )

    return ChatResponse(
        conversation_id=response.conversation_id,
        message_id=response.message_id,
        content=response.content,
        tool_calls=[
            ToolCallSchema(id=tc.id, name=tc.name, arguments=tc.arguments)
            for tc in response.tool_calls
        ],
        tool_results=[
            ToolResultSchema(
                call_id=tr.call_id,
                name=tr.name,
                result=tr.result,
                execution_time_ms=tr.execution_time_ms,
                is_error=tr.is_error,
            )
            for tr in response.tool_results
        ],
        grounding_report=GroundingReportSchema(
            is_grounded=response.grounding_report.is_grounded,
            grounding_score=response.grounding_report.grounding_score,
            total_claims=response.grounding_report.total_claims,
            verified_claims=response.grounding_report.verified_claims,
            unverified_claims=response.grounding_report.unverified_claims,
            citations=[
                CitationSchema(
                    citation_id=c.citation_id,
                    tool_name=c.tool_name,
                    entity_id=c.entity_id,
                    field_name=c.field_name,
                    verified_value=c.verified_value,
                    snippet=c.snippet,
                )
                for c in response.grounding_report.citations
            ],
        ),
        execution_latency_ms=response.execution_latency_ms,
    )


@router.post(
    "/chat/stream",
    summary="Conversational diagnostic chat (Server-Sent Events streaming)",
)
async def chat_stream(
    payload: ChatRequest,
    engine: AIAnalystEngine = Depends(get_analyst_engine),
) -> StreamingResponse:
    """Stream AI Analyst generation tokens, tool executions, and grounding reports via SSE."""
    provider_str = _resolve_provider(payload.provider)
    cfg = LLMConfig(provider=provider_str)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for chunk in engine.stream_chat(
            query=payload.query,
            conversation_id=payload.conversation_id,
            config=cfg,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/conversations",
    response_model=list[ConversationItemResponse],
    summary="List historical diagnostic conversation sessions",
)
async def list_conversations(
    workflow_definition_id: str | None = Query(default=None),
    execution_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[ConversationItemResponse]:
    """Retrieve historical conversation sessions with message counts."""
    repo = AnalystRepository(db)
    records, _ = await repo.list_conversations(
        workflow_definition_id=workflow_definition_id,
        execution_id=execution_id,
        limit=limit,
        offset=offset,
    )
    return [
        ConversationItemResponse(
            id=c.id,
            title=c.title,
            workflow_definition_id=c.workflow_definition_id,
            execution_id=c.execution_id,
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
            message_count=len(c.messages) if c.messages else 0,
        )
        for c in records
    ]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get full conversation transcript and tool logs",
)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ConversationDetailResponse:
    """Retrieve full conversation transcript with messages, tool calls, and citations."""
    repo = AnalystRepository(db)
    conv = await repo.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{conversation_id}' not found",
        )

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        workflow_definition_id=conv.workflow_definition_id,
        execution_id=conv.execution_id,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        messages=[
            MessageDetailSchema(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls or [],
                tool_results=m.tool_results or [],
                citations=m.citations or [],
                grounding_score=m.grounding_score,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in conv.messages
        ],
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation session",
)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a conversation session and all its message history."""
    repo = AnalystRepository(db)
    deleted = await repo.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{conversation_id}' not found",
        )


@router.get(
    "/tools",
    response_model=list[ToolDefinitionSchema],
    summary="List available platform tool definitions and schemas",
)
async def list_tools(
    engine: AIAnalystEngine = Depends(get_analyst_engine),
) -> list[ToolDefinitionSchema]:
    """Retrieve JSON schema definitions for all invocable platform tools."""
    tools = engine.tool_registry.get_definitions()
    return [
        ToolDefinitionSchema(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in tools
    ]


@router.get(
    "/stats",
    response_model=AnalystStatsResponse,
    summary="Get aggregate usage statistics for AI Analyst",
)
async def get_stats(
    db: AsyncSession = Depends(get_db_session),
) -> AnalystStatsResponse:
    """Retrieve conversation and message counts with average grounding score."""
    repo = AnalystRepository(db)
    stats_data = await repo.get_stats()
    return AnalystStatsResponse(
        total_conversations=stats_data["total_conversations"],
        total_messages=stats_data["total_messages"],
        average_grounding_score=stats_data["average_grounding_score"],
    )
