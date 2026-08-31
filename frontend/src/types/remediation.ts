export type ActionType =
  | 'CIRCUIT_BREAK'
  | 'TRAFFIC_DIVERT'
  | 'CONCURRENCY_THROTTLE'
  | 'RETRY_BACKOFF_ADAPT'
  | 'CACHE_FALLBACK_ACTUATE';

export type ExecutionMode = 'AUTONOMOUS' | 'SUPERVISED' | 'ADVISORY';

export type ActionPlanStatus =
  | 'STAGED'
  | 'EXECUTING'
  | 'ACTIVE_VERIFYING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'ROLLED_BACK';

export interface StateSnapshot {
  routing_weights: Record<string, number>;
  circuit_states: Record<string, string>;
  concurrency_limits: Record<string, number>;
  retry_multipliers: Record<string, number>;
  captured_at: string;
}

export interface SafetyCheckReport {
  is_safe: boolean;
  blast_radius_passed: boolean;
  anti_flapping_passed: boolean;
  acyclicity_passed: boolean;
  capacity_headroom_passed: boolean;
  checks_details: Record<string, string>;
  rejection_reasons: string[];
  recommended_mode: ExecutionMode;
}

export interface RemediationPlan {
  id: string;
  policy_id: string | null;
  workflow_definition_id: string;
  incident_id: string | null;
  trigger_rca_id: string | null;
  action_type: ActionType;
  execution_mode: ExecutionMode;
  status: ActionPlanStatus;
  target_service: string;
  target_parameters: Record<string, any>;
  blast_radius_pct: number;
  idempotency_key: string;
  expected_savings: {
    latency_reduction_pct?: number;
    cost_reduction_pct?: number;
    reliability_gain_pct?: number;
    [key: string]: number | undefined;
  };
  pre_actuation_state_snapshot: StateSnapshot;
  post_actuation_state_snapshot: StateSnapshot | null;
  health_baseline: Record<string, number>;
  post_health_metrics: Record<string, number> | null;
  safety_report: SafetyCheckReport | null;
  execution_error: string | null;
  created_at: string;
  executed_at: string | null;
  completed_at: string | null;
}

export interface RemediationPolicy {
  id: string;
  name: string;
  workflow_definition_id: string;
  incident_category: string;
  action_type: ActionType;
  execution_mode: ExecutionMode;
  max_blast_radius: number;
  cooldown_seconds: number;
  verification_timeout_seconds: number;
  is_active: boolean;
  created_at: string;
}

export interface AuditLedgerEntry {
  entry_id: string;
  plan_id: string;
  event_type: string;
  actor: string;
  payload: Record<string, any>;
  timestamp: string;
  previous_hash: string;
  entry_hash: string;
}

export interface AuditLedgerVerification {
  is_valid: boolean;
  message: string;
  total_entries: number;
}
