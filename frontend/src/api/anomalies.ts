/**
 * Typed API client for Unsupervised Anomaly Detection.
 */

import { request } from './client';
import {
  Anomaly,
  AnomalyDetectRequest,
  AnomalyDetectResponse,
  AnomalyStats,
} from '../types/anomaly';
import { PaginatedResponse } from '../types/api';

export const anomaliesApi = {
  /** Run real-time or post-execution composite anomaly detection */
  detect: (payload: AnomalyDetectRequest) =>
    request<AnomalyDetectResponse>('/api/v1/anomalies/detect', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** List recorded anomalies with pagination and filters */
  listAnomalies: (params?: {
    workflow_definition_id?: string;
    anomaly_type?: string;
    severity?: string;
    min_score?: number;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.workflow_definition_id) query.set('workflow_definition_id', params.workflow_definition_id);
    if (params?.anomaly_type) query.set('anomaly_type', params.anomaly_type);
    if (params?.severity) query.set('severity', params.severity);
    if (params?.min_score !== undefined) query.set('min_score', String(params.min_score));
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));

    const qs = query.toString();
    return request<PaginatedResponse<Anomaly>>(`/api/v1/anomalies${qs ? `?${qs}` : ''}`);
  },

  /** Get single anomaly details */
  getAnomaly: (anomalyId: string) =>
    request<Anomaly>(`/api/v1/anomalies/${encodeURIComponent(anomalyId)}`),

  /** Get all anomalies associated with a given execution */
  getExecutionAnomalies: (executionId: string) =>
    request<Anomaly[]>(`/api/v1/anomalies/executions/${encodeURIComponent(executionId)}`),

  /** Get aggregated anomaly statistics */
  getStats: () =>
    request<AnomalyStats>('/api/v1/anomalies/stats'),

  /** Trigger detector baseline calibration */
  fit: (nominalWorkflows: number = 120) =>
    request<{ status: string; version: string; services_fitted: string[]; transitions_fitted: number }>(
      '/api/v1/anomalies/fit',
      {
        method: 'POST',
        body: JSON.stringify({ nominal_workflows: nominalWorkflows, seed: 42, version: '1.1.0' }),
      }
    ),
};
