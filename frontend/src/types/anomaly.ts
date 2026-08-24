export type AnomalyType =
  | 'LATENCY_SPIKE'
  | 'UNUSUAL_PATH'
  | 'RETRY_STORM'
  | 'ERROR_CASCADE'
  | 'DEPENDENCY_TIMEOUT';

export type AnomalySeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface Anomaly {
  id: string;
  execution_id: string;
  workflow_definition_id: string;
  anomaly_type: AnomalyType;
  score: number;
  severity: AnomalySeverity;
  affected_services: string[];
  explanation: string;
  evidence: Record<string, any>;
  detected_at: string;
}

export interface AnomalyDetectRequest {
  execution_id: string;
  workflow_definition_id?: string;
  events?: Array<Record<string, any>>;
  as_of_step?: number;
  persist_to_db?: boolean;
}

export interface AnomalyDetectResponse {
  execution_id: string;
  workflow_definition_id: string;
  is_anomalous: boolean;
  max_score: number;
  highest_severity: AnomalySeverity | 'NOMINAL';
  anomaly_count: number;
  anomalies: Anomaly[];
}

export interface AnomalyStats {
  total_anomalies: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
}
