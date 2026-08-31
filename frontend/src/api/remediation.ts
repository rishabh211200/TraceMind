import { request } from './client';
import {
  AuditLedgerEntry,
  AuditLedgerVerification,
  RemediationPlan,
  RemediationPolicy,
  StateSnapshot,
} from '../types/remediation';

export interface SynthesizePlanRequest {
  workflow_definition_id: string;
  incident_id?: string;
  incident_category?: string;
  root_cause_service?: string;
  preferred_action?: string;
  diagnostic_confidence?: number;
}

export const synthesizeRemediationPlan = async (
  payload: SynthesizePlanRequest
): Promise<RemediationPlan> => {
  return request<RemediationPlan>('/api/v1/remediations/plans/synthesize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
};

export const listRemediationPlans = async (
  params?: { workflow_definition_id?: string; status?: string; mode?: string }
): Promise<RemediationPlan[]> => {
  const query = new URLSearchParams();
  if (params?.workflow_definition_id) query.set('workflow_definition_id', params.workflow_definition_id);
  if (params?.status) query.set('status', params.status);
  if (params?.mode) query.set('mode', params.mode);
  const qs = query.toString();
  return request<RemediationPlan[]>(`/api/v1/remediations/plans${qs ? `?${qs}` : ''}`);
};

export const getRemediationPlan = async (planId: string): Promise<RemediationPlan> => {
  return request<RemediationPlan>(`/api/v1/remediations/plans/${planId}`);
};

export const executeRemediationPlan = async (
  planId: string,
  operatorNotes?: string,
  simulatedPostTelemetry?: Record<string, number>
): Promise<RemediationPlan> => {
  return request<RemediationPlan>(`/api/v1/remediations/plans/${planId}/execute`, {
    method: 'POST',
    body: JSON.stringify({
      operator_notes: operatorNotes,
      simulated_post_telemetry: simulatedPostTelemetry,
    }),
  });
};

export const rollbackRemediationPlan = async (planId: string): Promise<RemediationPlan> => {
  return request<RemediationPlan>(`/api/v1/remediations/plans/${planId}/rollback`, {
    method: 'POST',
  });
};

export const listRemediationPolicies = async (): Promise<RemediationPolicy[]> => {
  return request<RemediationPolicy[]>('/api/v1/remediations/policies');
};

export const getAuditLedger = async (planId?: string): Promise<AuditLedgerEntry[]> => {
  const qs = planId ? `?plan_id=${planId}` : '';
  return request<AuditLedgerEntry[]>(`/api/v1/remediations/audit-ledger${qs}`);
};

export const verifyAuditLedgerIntegrity = async (): Promise<AuditLedgerVerification> => {
  return request<AuditLedgerVerification>('/api/v1/remediations/audit-ledger/verify');
};

export const getLiveMeshState = async (): Promise<StateSnapshot> => {
  return request<StateSnapshot>('/api/v1/remediations/mesh-state');
};
