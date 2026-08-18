/**
 * Ground-truth incident and affected trace models.
 */

export interface Incident {
  id: string;
  scenario_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  affected_services: string[];
  ground_truth_root_cause: string;
  description: string;
  parameters: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface IncidentTrace {
  id: string;
  workflow_definition_id: string;
  started_at: string;
  completed_at?: string | null;
  duration_ms: number;
  status: string;
  retry_count: number;
  error_count: number;
  failure_reason?: string | null;
  incident_id?: string | null;
  is_incident_affected: boolean;
  metadata?: Record<string, unknown>;
}
