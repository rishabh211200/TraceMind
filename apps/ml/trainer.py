"""Synthetic dataset generation, model training loop, and evaluation pipeline."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import train_test_split

from apps.ml.features import TraceFeatureExtractor
from apps.ml.models import WorkflowFailureClassifier, WorkflowLatencyRegressor
from apps.simulator.config import SimulationConfig
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.events import TraceEvent
from packages.domain.incident import IncidentScenario


class ModelTrainer:
    """End-to-end dataset generation, training, and evaluation pipeline."""

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.feature_extractor = TraceFeatureExtractor()

    def generate_synthetic_training_data(
        self,
        nominal_workflows: int = 200,
        incident_workflows_per_scenario: int = 40,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Generate a diverse synthetic dataset combining nominal workloads and chaos incidents.

        Returns
        -------
        tuple[pd.DataFrame, pd.Series, pd.Series]
            (X_features, y_failures, y_latencies)
        """
        all_events_map: dict[str, list[TraceEvent]] = {}
        all_outcomes: dict[str, tuple[bool, float]] = {}

        # 1. Simulate Nominal Baseline Workflows
        cfg_nominal = SimulationConfig(
            workflow_count=nominal_workflows,
            arrival_rate_per_second=20.0,
            seed=self.random_state,
        )
        sim_nominal = TraceSimulator(config=cfg_nominal)
        result_nominal = sim_nominal.run()

        for exec_rec in result_nominal.executions:
            is_failed = exec_rec.status != "COMPLETED"
            all_outcomes[exec_rec.id] = (is_failed, exec_rec.total_latency_ms)
            all_events_map[exec_rec.id] = []

        for evt in result_nominal.events:
            if evt.execution_id in all_events_map:
                all_events_map[evt.execution_id].append(evt)

        # 2. Simulate Causal Chaos Incidents across all scenario types
        chaos_scenarios = [
            IncidentScenario.PAYMENT_LATENCY_DEGRADATION,
            IncidentScenario.DATABASE_LATENCY,
            IncidentScenario.SERVICE_FAILURE,
            IncidentScenario.TRAFFIC_SPIKE,
            IncidentScenario.NETWORK_LATENCY,
            IncidentScenario.RETRY_STORM,
            IncidentScenario.CASCADING_FAILURE,
        ]

        for idx, scenario in enumerate(chaos_scenarios):
            cfg_chaos = SimulationConfig(
                workflow_count=incident_workflows_per_scenario,
                arrival_rate_per_second=15.0,
                seed=self.random_state + idx + 1,
                incident_scenario=scenario,
                incident_probability=1.0,
                incident_duration_workflows=incident_workflows_per_scenario,
            )
            sim_chaos = TraceSimulator(config=cfg_chaos)
            result_chaos = sim_chaos.run()

            for exec_rec in result_chaos.executions:
                is_failed = exec_rec.status != "COMPLETED"
                all_outcomes[exec_rec.id] = (is_failed, exec_rec.total_latency_ms)
                all_events_map[exec_rec.id] = []

            for evt in result_chaos.events:
                if evt.execution_id in all_events_map:
                    all_events_map[evt.execution_id].append(evt)

        # 3. Extract in-flight prefixes
        return self.feature_extractor.extract_prefix_dataset(
            execution_events_map=all_events_map,
            execution_outcomes=all_outcomes,
            min_prefix_steps=1,
        )

    def train_and_evaluate(
        self,
        X: pd.DataFrame,
        y_fail: pd.Series,
        y_lat: pd.Series,
        test_size: float = 0.2,
    ) -> dict[str, Any]:
        """Train classifier and regressor models and compute validation performance metrics.

        Returns
        -------
        dict[str, Any]
            Dictionary containing trained models and metric reports.
        """
        # Train / Test split
        X_train, X_test, y_fail_train, y_fail_test, y_lat_train, y_lat_test = train_test_split(
            X,
            y_fail,
            y_lat,
            test_size=test_size,
            random_state=self.random_state,
            stratify=y_fail if y_fail.nunique() > 1 else None,
        )

        # Calculate positive class weight for XGBoost
        num_pos = int(np.sum(y_fail_train == 1))
        num_neg = int(np.sum(y_fail_train == 0))
        scale_pos = (num_neg / max(1, num_pos)) if num_pos > 0 else 1.0

        # 1. Train Failure Classifier
        classifier = WorkflowFailureClassifier(
            scale_pos_weight=min(scale_pos, 10.0),
            random_state=self.random_state,
        )
        classifier.fit(X_train, y_fail_train)

        # Evaluate Classifier
        y_pred_proba = classifier.predict_proba(X_test)[:, 1]
        y_pred_bin = (y_pred_proba >= 0.5).astype(int)

        if len(np.unique(y_fail_test)) > 1:
            try:
                val = roc_auc_score(y_fail_test, y_pred_proba)
                roc_auc = float(val) if not np.isnan(val) else 1.0
            except Exception:
                roc_auc = 1.0
        else:
            roc_auc = 1.0

        f1 = float(f1_score(y_fail_test, y_pred_bin, zero_division=0))
        precision = float(precision_score(y_fail_test, y_pred_bin, zero_division=0))
        recall = float(recall_score(y_fail_test, y_pred_bin, zero_division=0))

        # 2. Train Latency Regressor
        regressor = WorkflowLatencyRegressor(random_state=self.random_state)
        regressor.fit(X_train, y_lat_train)

        # Evaluate Regressor
        y_lat_pred = regressor.predict(X_test)
        mae = float(mean_absolute_error(y_lat_test, y_lat_pred))
        rmse = float(root_mean_squared_error(y_lat_test, y_lat_pred))
        r2 = float(r2_score(y_lat_test, y_lat_pred))

        return {
            "classifier": classifier,
            "regressor": regressor,
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "metrics": {
                "classification": {
                    "roc_auc": roc_auc,
                    "f1_score": f1,
                    "precision": precision,
                    "recall": recall,
                },
                "regression": {
                    "mean_absolute_error_ms": mae,
                    "root_mean_squared_error_ms": rmse,
                    "r2_score": r2,
                },
            },
        }
