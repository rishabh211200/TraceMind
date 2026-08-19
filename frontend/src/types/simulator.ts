/**
 * Simulator controls, chaos scenario catalog, and injection schemas.
 */

export interface ChaosScenarioInfo {
  scenario_type: string;
  name: string;
  description: string;
  severity: string;
  affected_services: string[];
  ground_truth_root_cause: string;
  default_parameters: Record<string, unknown>;
}

export interface SimulationGenerateRequest {
  workflow_count?: number;
  arrival_rate_rps?: number;
  seed?: number | null;
  incident_scenario?: string | null;
  persist_to_db?: boolean;
  stream_to_kafka?: boolean;
}

export interface SimulationGenerateResponse {
  seed: number;
  workflows_requested: number;
  executions_generated: number;
  events_generated: number;
  incidents_generated: number;
  generation_wall_time_ms: number;
  persisted_to_db: boolean;
  persisted_executions_count: number;
  persisted_events_count: number;
  streamed_to_kafka?: boolean;
  persistence_wall_time_ms?: number | null;
  summary_statistics: {
    completed_count: number;
    failed_count: number;
    timeout_count: number;
    success_rate_percent: number;
    error_rate_percent: number;
    retry_rate_percent: number;
    mean_latency_ms: number;
    p95_latency_ms: number;
    p99_latency_ms: number;
  };
}

export interface ChaosInjectionRequest {
  scenario_type: string;
  workflow_count?: number;
  arrival_rate_rps?: number;
  seed?: number | null;
  persist_to_db?: boolean;
}

export interface ChaosInjectionResponse {
  incident_id: string;
  scenario_type: string;
  affected_services: string[];
  ground_truth_root_cause: string;
  total_executions: number;
  executions_affected: number;
  mean_latency_ms: number;
  error_rate_percent: number;
  retry_rate_percent: number;
  persisted_to_db: boolean;
}
