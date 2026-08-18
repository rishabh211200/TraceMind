/**
 * Service domain and telemetry types matching backend Pydantic schemas.
 */

export interface ServiceProfile {
  name: string;
  service_type: string;
  capacity: number;
  baseline_latency_ms: number;
  baseline_failure_rate: number;
  timeout_ms: number;
  max_retries: number;
  retry_backoff_ms: number;
  dependencies: (string | { to: string; type?: string; weight?: number })[];
  metadata: Record<string, unknown>;
}

export interface ServiceUpdatePayload {
  capacity?: number;
  baseline_latency_ms?: number;
  baseline_failure_rate?: number;
  timeout_ms?: number;
  max_retries?: number;
  retry_backoff_ms?: number;
}

export interface ServiceLatencyStats {
  service: string;
  count: number;
  min_latency_ms: number;
  max_latency_ms: number;
  mean_latency_ms: number;
  median_p50_latency_ms: number;
  p90_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  start_time?: string | null;
  end_time?: string | null;
}

export interface ServiceHealth {
  service: string;
  total_events: number;
  successful_events: number;
  failed_events: number;
  timeout_events: number;
  retry_events: number;
  failure_rate_percent: number;
  timeout_rate_percent: number;
  retry_rate_percent: number;
  avg_latency_ms: number;
  start_time?: string | null;
  end_time?: string | null;
}

export interface TopologyNode {
  id: string;
  name: string;
  type: string;
  capacity: number;
  baseline_latency_ms: number;
}

export interface TopologyEdge {
  from_service: string;
  to_service: string;
  relationship_type: string;
  call_weight: number;
  metadata: Record<string, unknown>;
}

export interface ServiceTopology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  total_services: number;
  total_dependencies: number;
}

export interface ServiceHealthSummary {
  service: string;
  total_events: number;
  error_count: number;
  error_rate_percent: number;
  retry_count: number;
  retry_rate_percent: number;
  timeout_count: number;
  timeout_rate_percent: number;
  mean_latency_ms: number;
  p95_latency_ms: number;
}
