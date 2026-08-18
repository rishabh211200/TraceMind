/**
 * Execution records, trace events, and hierarchical trace tree models.
 */

import { PaginatedResponse } from './api';

export type ExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'TIMEOUT';

export interface ExecutionSummary {
  id: string;
  workflow_definition_id: string;
  started_at: string;
  completed_at?: string | null;
  duration_ms: number;
  status: ExecutionStatus;
  retry_count: number;
  error_count: number;
  failure_reason?: string | null;
  incident_id?: string | null;
  is_incident_affected: boolean;
  metadata?: Record<string, unknown>;
}

export type ExecutionListResponse = PaginatedResponse<ExecutionSummary>;

export type EventType =
  | 'WORKFLOW_START'
  | 'WORKFLOW_COMPLETE'
  | 'WORKFLOW_FAIL'
  | 'SPAN_START'
  | 'SPAN_COMPLETE'
  | 'SPAN_ERROR'
  | 'SPAN_TIMEOUT'
  | 'RETRY_ATTEMPT';

export interface TraceEvent {
  event_id: string;
  timestamp: string;
  execution_id: string;
  workflow_id: string;
  service: string;
  operation: string;
  event_type: EventType;
  status: string;
  latency_ms: number;
  parent_event_id?: string | null;
  correlation_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TraceTreeNode {
  event_id: string;
  timestamp: string;
  execution_id: string;
  workflow_id: string;
  service: string;
  operation: string;
  event_type: EventType;
  status: string;
  latency_ms: number;
  parent_event_id?: string | null;
  correlation_id?: string | null;
  metadata?: Record<string, unknown>;
  children: TraceTreeNode[];
}
