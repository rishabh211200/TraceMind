/**
 * Typed API client for Deterministic Root Cause Analysis.
 */

import { request } from './client';
import {
  RootCauseReport,
  RootCauseStats,
} from '../types/rootCause';
import { PaginatedResponse } from '../types/api';

export const rootCauseApi = {
  /** Run on-demand root cause diagnosis */
  analyze: (payload: {
    execution_id: string;
    workflow_definition_id?: string;
    events?: unknown[];
    anomalies?: unknown[];
    shap_contributions?: unknown[];
    persist_to_db?: boolean;
  }) =>
    request<RootCauseReport>('/api/v1/root-cause/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** List recorded root cause diagnoses with pagination and filters */
  listReports: (params?: {
    workflow_definition_id?: string;
    culprit_service?: string;
    incident_category?: string;
    min_confidence?: number;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.workflow_definition_id) query.set('workflow_definition_id', params.workflow_definition_id);
    if (params?.culprit_service) query.set('culprit_service', params.culprit_service);
    if (params?.incident_category) query.set('incident_category', params.incident_category);
    if (params?.min_confidence !== undefined) query.set('min_confidence', String(params.min_confidence));
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));

    const qs = query.toString();
    return request<PaginatedResponse<RootCauseReport>>(`/api/v1/root-cause${qs ? `?${qs}` : ''}`);
  },

  /** Get single root cause report details */
  getReport: (reportId: string) =>
    request<RootCauseReport>(`/api/v1/root-cause/${encodeURIComponent(reportId)}`),

  /** Get all root cause reports for an execution */
  getExecutionReports: (executionId: string) =>
    request<RootCauseReport[]>(`/api/v1/root-cause/executions/${encodeURIComponent(executionId)}`),

  /** Get aggregate root cause statistics */
  getStats: () =>
    request<RootCauseStats>('/api/v1/root-cause/stats'),
};
