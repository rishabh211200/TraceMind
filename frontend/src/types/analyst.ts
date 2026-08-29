/**
 * TypeScript definitions for Tool-Grounded Conversational AI Analyst.
 */

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
}

export interface ToolResult {
  call_id: string;
  name: string;
  result: any;
  execution_time_ms: number;
  is_error?: boolean;
}

export interface Citation {
  citation_id: number;
  tool_name: string;
  entity_id: string;
  field_name: string;
  verified_value: any;
  snippet?: string;
}

export interface GroundingReport {
  is_grounded: boolean;
  grounding_score: number;
  total_claims: number;
  verified_claims: number;
  unverified_claims: string[];
  citations: Citation[];
}

export interface ChatRequest {
  query: string;
  conversation_id?: string;
  workflow_definition_id?: string;
  execution_id?: string;
  provider?: 'mock' | 'openai' | 'anthropic' | 'gemini';
  persist?: boolean;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  content: string;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  grounding_report: GroundingReport;
  execution_latency_ms: number;
}

export interface MessageDetail {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  citations: Citation[];
  grounding_score: number;
  created_at: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  workflow_definition_id?: string | null;
  execution_id?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  title: string;
  workflow_definition_id?: string | null;
  execution_id?: string | null;
  created_at: string;
  updated_at: string;
  messages: MessageDetail[];
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, any>;
}

export interface AnalystStats {
  total_conversations: number;
  total_messages: number;
  average_grounding_score: number;
}
