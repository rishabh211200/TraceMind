/**
 * Workflow definitions, DAG topologies, execution listing, and statistics API client.
 */

import { buildQueryString, request } from './client';
import { ExecutionListResponse } from '../types/execution';
import {
  WorkflowDefinition,
  WorkflowStats,
} from '../types/workflow';

export const workflowsApi = {
  /** List all registered workflow definitions */
  listWorkflows: () => request<WorkflowDefinition[]>('/api/v1/workflows'),

  /** Register a new workflow definition with DAG validation */
  createWorkflow: (workflow: WorkflowDefinition) =>
    request<WorkflowDefinition>('/api/v1/workflows', {
      method: 'POST',
      body: JSON.stringify(workflow),
    }),

  /** Get a single workflow definition by ID */
  getWorkflow: (id: string) =>
    request<WorkflowDefinition>(`/api/v1/workflows/${encodeURIComponent(id)}`),

  /** Update an existing workflow definition */
  updateWorkflow: (id: string, updates: Partial<WorkflowDefinition>) =>
    request<WorkflowDefinition>(`/api/v1/workflows/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  /** Delete a workflow definition */
  deleteWorkflow: (id: string) =>
    request<{ message: string }>(`/api/v1/workflows/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),

  /** List executions for a specific workflow */
  listWorkflowExecutions: (
    id: string,
    params?: {
      page?: number;
      limit?: number;
      status?: string;
      incident_id?: string;
      is_incident_affected?: boolean;
    }
  ) =>
    request<ExecutionListResponse>(
      `/api/v1/workflows/${encodeURIComponent(id)}/executions${buildQueryString(
        params || {}
      )}`
    ),

  /** Get aggregate duration and reliability statistics for a workflow */
  getWorkflowStats: (id: string) =>
    request<WorkflowStats>(`/api/v1/workflows/${encodeURIComponent(id)}/stats`),
};
