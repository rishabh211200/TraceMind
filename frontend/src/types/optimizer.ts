export interface CostBreakdown {
  compute_units: number;
  db_io_units: number;
  retry_penalty_units: number;
  total_modeled_cost: number;
  step_costs: Record<string, number>;
}

export interface PathStep {
  service: string;
  operation: string;
  is_database: boolean;
  is_cache: boolean;
  is_fallback: boolean;
}

export interface PathMetrics {
  path_id: string;
  steps: PathStep[];
  step_signatures: string[];
  observed_latency_ms: number;
  observed_p95_latency_ms: number;
  observed_p99_latency_ms: number;
  observed_reliability: number;
  observed_retry_rate: number;
  observation_count: number;
  statistical_confidence: number;
  cost_breakdown: CostBreakdown;
  modeled_cost_units: number;
}

export interface MultiObjectiveWeightConfig {
  latency: number;
  cost: number;
  reliability: number;
}

export interface ParetoPoint {
  path_id: string;
  step_signatures: string[];
  observed_latency_ms: number;
  modeled_cost_units: number;
  observed_reliability: number;
  utility_score: number;
  statistical_confidence: number;
  is_pareto_optimal: boolean;
}

export interface ExpectedSavings {
  latency_reduction_pct: number;
  cost_reduction_pct: number;
  reliability_gain_pct: number;
  overall_utility_improvement_pct: number;
  absolute_latency_delta_ms: number;
  absolute_cost_delta_units: number;
}

export interface OptimizationReport {
  id: string;
  workflow_definition_id: string;
  optimization_type: string;
  weights: MultiObjectiveWeightConfig;
  current_path: PathMetrics | null;
  recommended_path: PathMetrics;
  pareto_frontier: ParetoPoint[];
  all_evaluated_paths: PathMetrics[];
  expected_savings: ExpectedSavings;
  rationale: string;
  active_incident_culprit: string | null;
  created_at: string;
}

export interface OptimizationHistoryItem {
  id: string;
  workflow_definition_id: string;
  optimization_type: string;
  recommended_path_id: string;
  weight_latency: number;
  weight_cost: number;
  weight_reliability: number;
  expected_latency_reduction_pct: number;
  expected_reliability_gain_pct: number;
  active_incident_culprit: string | null;
  created_at: string;
}

export interface OptimizationHistoryResponse {
  items: OptimizationHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface OptimizerStats {
  total_optimizations: number;
  strategy_breakdown: Record<string, number>;
  avg_weight_latency: number;
  avg_weight_cost: number;
  avg_weight_reliability: number;
  most_recent_optimization: {
    id: string;
    workflow_definition_id: string;
    optimization_type: string;
    created_at: string;
  } | null;
}

export interface OptimizationRecommendRequest {
  workflow_definition_id?: string;
  weight_latency?: number;
  weight_cost?: number;
  weight_reliability?: number;
  current_path_id?: string;
  active_incident_culprit?: string;
  max_latency_constraint_ms?: number;
  min_reliability_constraint?: number;
  persist_to_db?: boolean;
}
