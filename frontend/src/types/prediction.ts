/**
 * Machine learning prediction and TreeSHAP feature attribution types.
 */

export interface FeatureContribution {
  feature_name: string;
  value: number;
  contribution: number;
  description?: string | null;
}

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Prediction {
  id: string;
  execution_id: string;
  workflow_definition_id: string;
  step_index: number;
  failure_probability: number;
  predicted_risk_level: RiskLevel;
  predicted_latency_ms: number;
  confidence: number;
  top_contributions: FeatureContribution[];
  feature_vector: Record<string, number>;
  model_name: string;
  model_version: string;
  created_at: string;
}

export interface PredictionRequest {
  execution_id: string;
  workflow_definition_id?: string;
  events?: Record<string, unknown>[];
  as_of_step?: number;
  persist_to_db?: boolean;
}

export interface TrainRequest {
  nominal_workflows?: number;
  incident_workflows_per_scenario?: number;
  random_state?: number;
  version?: string;
}

export interface TrainResponse {
  status: string;
  version: string;
  training_samples: number;
  test_samples: number;
  metrics: {
    classification?: {
      roc_auc?: number;
      f1_score?: number;
      precision?: number;
      recall?: number;
    };
    regression?: {
      mean_absolute_error_ms?: number;
      root_mean_squared_error_ms?: number;
      r2_score?: number;
    };
  };
}

export interface ModelMetadataResponse {
  version: string;
  model_name: string;
  status: string;
  features: string[];
  metrics: Record<string, unknown>;
}
