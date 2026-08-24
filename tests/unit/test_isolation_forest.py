"""Unit tests for WorkflowIsolationForestDetector."""

import numpy as np
import pandas as pd

from apps.ml.anomalies.isolation_forest import WorkflowIsolationForestDetector
from apps.ml.features import FEATURE_NAMES


def test_isolation_forest_fit_and_score():
    detector = WorkflowIsolationForestDetector(n_estimators=30, random_state=42)
    assert not detector.is_fitted

    # Generate synthetic nominal features
    np.random.seed(42)
    nominal_rows = []
    for _ in range(80):
        row = {k: float(np.random.uniform(5.0, 30.0)) for k in FEATURE_NAMES}
        row["cumulative_errors"] = 0.0
        row["cumulative_retries"] = 0.0
        row["step_count"] = 10.0
        nominal_rows.append(row)

    df_nominal = pd.DataFrame(nominal_rows)
    detector.fit(df_nominal)
    assert detector.is_fitted

    # Score nominal sample
    nom_sample = dict.fromkeys(FEATURE_NAMES, 15.0)
    nom_sample["cumulative_errors"] = 0.0
    nom_sample["cumulative_retries"] = 0.0
    score_nom, is_anom_nom = detector.score_features(nom_sample)
    assert 0.0 <= score_nom <= 1.0

    # Score severe anomaly sample (5000ms latency, 10 errors)
    anom_sample = dict.fromkeys(FEATURE_NAMES, 500.0)
    anom_sample["cumulative_errors"] = 10.0
    anom_sample["cumulative_retries"] = 8.0
    anom_sample["elapsed_time_ms"] = 8000.0
    score_anom, is_anom_high = detector.score_features(anom_sample)

    assert score_anom > score_nom
    assert score_anom >= 0.50
