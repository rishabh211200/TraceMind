/**
 * Typed API client for ML failure and latency predictions and TreeSHAP explainability.
 */

import { request } from './client';
import {
  ModelMetadataResponse,
  Prediction,
  PredictionRequest,
  TrainRequest,
  TrainResponse,
} from '../types/prediction';

export const predictionsApi = {
  /** Request in-flight failure probability, forecasted latency, and TreeSHAP attributions */
  predict: (payload: PredictionRequest) =>
    request<Prediction>('/api/v1/predictions/predict', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Retrieve persisted or on-demand predictions for a workflow execution */
  getExecutionPredictions: (executionId: string) =>
    request<Prediction[]>(`/api/v1/predictions/executions/${encodeURIComponent(executionId)}`),

  /** Trigger offline model retraining on synthetic trace datasets */
  train: (payload?: TrainRequest) =>
    request<TrainResponse>('/api/v1/predictions/train', {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),

  /** Get active model version and evaluation metrics */
  getModelInfo: () =>
    request<ModelMetadataResponse>('/api/v1/predictions/models'),
};
