export interface HypothesisItem {
  id: string;
  culprit_service: string;
  incident_category: string;
  confidence: number;
  causal_path: string[];
  supporting_evidence: string[];
  score_breakdown?: {
    temporal_score?: number;
    depth_score?: number;
    severity_score?: number;
    shap_score?: number;
  };
}

export interface RootCauseReport {
  id: string;
  execution_id: string;
  workflow_definition_id: string;
  culprit_service: string;
  incident_category: string;
  confidence: number;
  causal_path: string[];
  supporting_evidence: string[];
  primary_hypothesis: HypothesisItem;
  alternative_hypotheses: HypothesisItem[];
  analyzed_at: string;
}

export interface RootCauseStats {
  total_diagnoses: number;
  by_category: Record<string, number>;
  by_culprit_service: Record<string, number>;
  mean_confidence: number;
}

export interface RootCauseFilter {
  workflow_definition_id?: string;
  culprit_service?: string;
  incident_category?: string;
  min_confidence?: number;
}
