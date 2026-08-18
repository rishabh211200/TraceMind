/**
 * Execution search, chronological span stream, and hierarchical trace tree API client.
 */

import { buildQueryString, request } from './client';
import {
  ExecutionListResponse,
  ExecutionSummary,
  TraceEvent,
  TraceTreeNode,
} from '../types/execution';

export interface ExecutionFilterParams {
  page?: number;
  limit?: number;
  workflow_id?: string;
  status?: string;
  incident_id?: string;
  is_incident_affected?: boolean;
  min_duration_ms?: number;
  max_duration_ms?: number;
  start_time?: string;
  end_time?: string;
}

export const executionsApi = {
  /** Search and list executions with multi-column filtering and pagination */
  listExecutions: (params?: ExecutionFilterParams) =>
    request<ExecutionListResponse>(
      `/api/v1/executions${buildQueryString(
        (params as unknown as Record<string, unknown>) || {}
      )}`
    ),

  /** Get details of a single execution */
  getExecution: (id: string) =>
    request<ExecutionSummary>(`/api/v1/executions/${encodeURIComponent(id)}`),

  /** Get chronological trace spans/events for an execution */
  getExecutionEvents: (id: string) =>
    request<TraceEvent[]>(`/api/v1/executions/${encodeURIComponent(id)}/events`),

  /** Get reconstructed hierarchical parent-child DAG trace tree */
  getExecutionTree: (id: string) =>
    request<TraceTreeNode>(`/api/v1/executions/${encodeURIComponent(id)}/tree`),
};
