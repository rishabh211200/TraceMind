import { request } from './client';
import {
  OptimizationHistoryResponse,
  OptimizationRecommendRequest,
  OptimizationReport,
  OptimizerStats,
  ParetoPoint,
  PathMetrics,
} from '../types/optimizer';

export const recommendOptimalPath = async (
  payload: OptimizationRecommendRequest = {}
): Promise<OptimizationReport> => {
  return request<OptimizationReport>('/api/v1/optimizer/recommend', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
};

export const listCandidatePaths = async (
  workflowDefinitionId: string = 'order_fulfillment'
): Promise<PathMetrics[]> => {
  return request<PathMetrics[]>(`/api/v1/optimizer/paths/${workflowDefinitionId}`);
};

export const getParetoFrontier = async (
  workflowDefinitionId: string = 'order_fulfillment',
  weights?: { latency: number; cost: number; reliability: number }
): Promise<ParetoPoint[]> => {
  const query = new URLSearchParams();
  if (weights) {
    query.set('weight_latency', String(weights.latency));
    query.set('weight_cost', String(weights.cost));
    query.set('weight_reliability', String(weights.reliability));
  }
  const qs = query.toString();
  return request<ParetoPoint[]>(
    `/api/v1/optimizer/pareto/${workflowDefinitionId}${qs ? `?${qs}` : ''}`
  );
};

export const listOptimizationHistory = async (params: {
  workflow_definition_id?: string;
  optimization_type?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<OptimizationHistoryResponse> => {
  const query = new URLSearchParams();
  if (params.workflow_definition_id) query.set('workflow_definition_id', params.workflow_definition_id);
  if (params.optimization_type) query.set('optimization_type', params.optimization_type);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  const qs = query.toString();
  return request<OptimizationHistoryResponse>(`/api/v1/optimizer/history${qs ? `?${qs}` : ''}`);
};

export const getOptimizerStats = async (): Promise<OptimizerStats> => {
  return request<OptimizerStats>('/api/v1/optimizer/stats');
};

export const getOptimizationById = async (id: string): Promise<OptimizationReport> => {
  return request<OptimizationReport>(`/api/v1/optimizer/${id}`);
};
