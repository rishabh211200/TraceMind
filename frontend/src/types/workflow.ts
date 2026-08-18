/**
 * Workflow definition, DAG graph, and execution statistics types.
 */

export interface WorkflowNode {
  id: string;
  service: string;
  operation?: string | null;
  metadata?: Record<string, unknown>;
}

export interface WorkflowEdge {
  from: string;
  to: string;
  weight?: number;
  condition?: string | null;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  version: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at?: string;
}

export interface WorkflowStats {
  workflow_id: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  timeout_executions: number;
  success_rate_percent: number;
  error_rate_percent: number;
  mean_duration_ms: number;
  median_duration_ms: number;
  p95_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
}
