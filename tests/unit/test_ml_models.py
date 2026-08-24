"""Unit tests for XGBoost classifier, regressor, and trainer pipeline."""

import pandas as pd

from apps.ml.features import FEATURE_NAMES
from apps.ml.models import WorkflowFailureClassifier, WorkflowLatencyRegressor
from apps.ml.trainer import ModelTrainer


def test_failure_classifier_fit_and_predict():
    # Construct distinct healthy and failing samples
    healthy_row = [
        1.0,
        50.0,
        0.0,
        0.0,
        20.0,
        20.0,
        20.0,
        0.0,
        0.0,
        0.0,
        20.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    failing_row = [
        5.0,
        1800.0,
        3.0,
        2.0,
        400.0,
        1200.0,
        1200.0,
        1.0,
        1.0,
        1.0,
        20.0,
        40.0,
        50.0,
        15.0,
        1200.0,
        5.0,
    ]

    X = pd.DataFrame([healthy_row, failing_row] * 20, columns=FEATURE_NAMES)
    y = pd.Series([0, 1] * 20)

    clf = WorkflowFailureClassifier(n_estimators=10, max_depth=3, random_state=42)
    clf.fit(X, y)

    # Test single prediction on healthy sample
    healthy_feats = {k: healthy_row[i] for i, k in enumerate(FEATURE_NAMES)}
    prob_healthy, risk_healthy = clf.predict_single(healthy_feats)
    assert 0.0 <= prob_healthy <= 1.0
    assert risk_healthy in ("LOW", "MEDIUM")

    # Test single prediction on degraded sample
    failing_feats = {k: failing_row[i] for i, k in enumerate(FEATURE_NAMES)}
    prob_failing, risk_failing = clf.predict_single(failing_feats)
    assert prob_failing > prob_healthy
    assert risk_failing in ("HIGH", "CRITICAL", "MEDIUM")


def test_latency_regressor_fit_and_predict():
    healthy_row = [
        1.0,
        50.0,
        0.0,
        0.0,
        20.0,
        20.0,
        20.0,
        0.0,
        0.0,
        0.0,
        20.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    failing_row = [
        5.0,
        1800.0,
        3.0,
        2.0,
        400.0,
        1200.0,
        1200.0,
        1.0,
        1.0,
        1.0,
        20.0,
        40.0,
        50.0,
        15.0,
        1200.0,
        5.0,
    ]

    X = pd.DataFrame([healthy_row, failing_row] * 15, columns=FEATURE_NAMES)
    y = pd.Series([400.0, 1800.0] * 15)

    reg = WorkflowLatencyRegressor(n_estimators=10, max_depth=3, random_state=42)
    reg.fit(X, y)

    pred_healthy = reg.predict_single({k: healthy_row[i] for i, k in enumerate(FEATURE_NAMES)})
    pred_failing = reg.predict_single({k: failing_row[i] for i, k in enumerate(FEATURE_NAMES)})

    assert pred_healthy >= 0.0
    assert pred_failing > pred_healthy


def test_trainer_end_to_end_synthetic_data_generation():
    trainer = ModelTrainer(random_state=42)
    X, y_fail, y_lat = trainer.generate_synthetic_training_data(
        nominal_workflows=40,
        incident_workflows_per_scenario=10,
    )

    assert len(X) > 0
    assert len(y_fail) == len(X)
    assert len(y_lat) == len(X)
    assert set(X.columns) == set(FEATURE_NAMES)

    report = trainer.train_and_evaluate(X, y_fail, y_lat, test_size=0.25)
    assert "metrics" in report
    assert "classification" in report["metrics"]
    assert "regression" in report["metrics"]
    assert report["metrics"]["classification"]["roc_auc"] >= 0.70
