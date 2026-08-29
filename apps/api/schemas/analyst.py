"""Pydantic v2 schemas for Conversational AI Analyst REST & Streaming endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload for conversational diagnostic chat query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language diagnostic question or prompt",
        examples=["What caused the failure in execution exec_4a9b?"],
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional existing conversation session ID for multi-turn context",
        examples=["conv_8a2b3c4d"],
    )
    workflow_definition_id: str | None = Field(
        default=None,
        description="Optional associated workflow DAG definition ID context",
        examples=["order_fulfillment"],
    )
    execution_id: str | None = Field(
        default=None,
        description="Optional target workflow execution ID context",
        examples=["exec_4a9b"],
    )
    provider: str = Field(
        default="mock",
        description="LLM provider: 'mock', 'openai', 'anthropic', 'gemini'",
    )
    persist: bool = Field(
        default=True,
        description="Whether to persist the conversation turn to PostgreSQL",
    )


class ToolCallSchema(BaseModel):
    """Schema for a tool call invocation."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultSchema(BaseModel):
    """Schema for a tool execution result."""

    call_id: str
    name: str
    result: Any
    execution_time_ms: float
    is_error: bool = False


class CitationSchema(BaseModel):
    """Schema for an atomic verified citation."""

    citation_id: int
    tool_name: str
    entity_id: str
    field_name: str
    verified_value: Any
    snippet: str = ""


class GroundingReportSchema(BaseModel):
    """Schema for the grounding verification report."""

    is_grounded: bool
    grounding_score: float
    total_claims: int
    verified_claims: int
    unverified_claims: list[str] = Field(default_factory=list)
    citations: list[CitationSchema] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Synchronous JSON response for AI Analyst query."""

    conversation_id: str
    message_id: str
    content: str
    tool_calls: list[ToolCallSchema] = Field(default_factory=list)
    tool_results: list[ToolResultSchema] = Field(default_factory=list)
    grounding_report: GroundingReportSchema
    execution_latency_ms: float


class ConversationItemResponse(BaseModel):
    """Summary item for conversation history listing."""

    id: str
    title: str
    workflow_definition_id: str | None = None
    execution_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0


class MessageDetailSchema(BaseModel):
    """Detailed message entity schema."""

    id: str
    conversation_id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    grounding_score: float = 1.0
    created_at: str | None = None


class ConversationDetailResponse(BaseModel):
    """Detailed conversation transcript response."""

    id: str
    title: str
    workflow_definition_id: str | None = None
    execution_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[MessageDetailSchema] = Field(default_factory=list)


class ToolDefinitionSchema(BaseModel):
    """Schema describing an invocable platform tool."""

    name: str
    description: str
    parameters: dict[str, Any]


class AnalystStatsResponse(BaseModel):
    """Aggregate statistics for AI Analyst usage."""

    total_conversations: int
    total_messages: int
    average_grounding_score: float
