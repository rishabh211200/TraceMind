import { request } from './client';
import {
  AnalystStats,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationItem,
  ToolDefinition,
} from '../types/analyst';

export const sendChatMessage = async (
  payload: ChatRequest
): Promise<ChatResponse> => {
  return request<ChatResponse>('/api/v1/analyst/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
};

export const streamChatMessage = async (
  payload: ChatRequest,
  onChunk: (chunk: any) => void
): Promise<void> => {
  const response = await fetch('/api/v1/analyst/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Failed to stream chat: ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const jsonStr = line.replace('data: ', '').trim();
        if (jsonStr) {
          try {
            const parsed = JSON.parse(jsonStr);
            onChunk(parsed);
          } catch {
            // Ignore parse errors on malformed chunks
          }
        }
      }
    }
  }
};

export const listConversations = async (params: {
  workflow_definition_id?: string;
  execution_id?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<ConversationItem[]> => {
  const query = new URLSearchParams();
  if (params.workflow_definition_id) query.set('workflow_definition_id', params.workflow_definition_id);
  if (params.execution_id) query.set('execution_id', params.execution_id);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  const qs = query.toString();
  return request<ConversationItem[]>(`/api/v1/analyst/conversations${qs ? `?${qs}` : ''}`);
};

export const getConversationById = async (
  id: string
): Promise<ConversationDetail> => {
  return request<ConversationDetail>(`/api/v1/analyst/conversations/${id}`);
};

export const deleteConversation = async (id: string): Promise<void> => {
  return request<void>(`/api/v1/analyst/conversations/${id}`, {
    method: 'DELETE',
  });
};

export const listAnalystTools = async (): Promise<ToolDefinition[]> => {
  return request<ToolDefinition[]>('/api/v1/analyst/tools');
};

export const getAnalystStats = async (): Promise<AnalystStats> => {
  return request<AnalystStats>('/api/v1/analyst/stats');
};
