/**
 * Service catalog, health, latency metrics, and topology API client.
 */

import { buildQueryString, request } from './client';
import {
  ServiceHealth,
  ServiceHealthSummary,
  ServiceLatencyStats,
  ServiceProfile,
  ServiceTopology,
  ServiceUpdatePayload,
} from '../types/service';

export const servicesApi = {
  /** List all registered services */
  listServices: () => request<ServiceProfile[]>('/api/v1/services'),

  /** Get profile of a single service */
  getService: (serviceName: string) =>
    request<ServiceProfile>(`/api/v1/services/${encodeURIComponent(serviceName)}`),

  /** Update service configuration */
  updateService: (serviceName: string, updates: ServiceUpdatePayload) =>
    request<ServiceProfile>(`/api/v1/services/${encodeURIComponent(serviceName)}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  /** Get latency percentiles for a service */
  getLatencyStats: (
    serviceName: string,
    params?: { start_time?: string; end_time?: string }
  ) =>
    request<ServiceLatencyStats>(
      `/api/v1/services/${encodeURIComponent(serviceName)}/latency${buildQueryString(
        params || {}
      )}`
    ),

  /** Get operational health & error metrics for a service */
  getHealth: (
    serviceName: string,
    params?: { start_time?: string; end_time?: string }
  ) =>
    request<ServiceHealth>(
      `/api/v1/services/${encodeURIComponent(serviceName)}/health${buildQueryString(
        params || {}
      )}`
    ),

  /** Get system-wide telemetry summary */
  getTelemetrySummary: (params?: { start_time?: string; end_time?: string }) =>
    request<Record<string, ServiceHealthSummary>>(
      `/api/v1/services/telemetry/summary${buildQueryString(params || {})}`
    ),

  /** Get service dependency topology graph */
  getTopology: () => request<ServiceTopology>('/api/v1/services/topology'),
};
