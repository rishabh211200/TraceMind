"""Machine learning model wrappers for workflow failure classification and latency regression."""

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from apps.ml.features import FEATURE_NAMES


class WorkflowFailureClassifier:
    """XGBoost gradient-boosted binary classifier predicting workflow failure probability."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.08,
        subsample: float = 0.8,
        scale_pos_weight: float = 1.0,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.scale_pos_weight = scale_pos_weight
        self.random_state = random_state
        self.feature_names = FEATURE_NAMES
        self.is_fitted = False

        self.model = XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            scale_pos_weight=self.scale_pos_weight,
            eval_metric="logloss",
            random_state=self.random_state,
            n_jobs=-1,
        )

    def fit(
        self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray
    ) -> "WorkflowFailureClassifier":
        """Train the classifier on the provided feature matrix X and binary failure labels y."""
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Return array of shape (n_samples, 2) containing failure probabilities."""
        if not self.is_fitted:
            # Fallback default probability if model is uncalibrated
            n_samples = len(X) if hasattr(X, "__len__") else 1
            return np.array([[0.95, 0.05]] * n_samples, dtype=np.float32)
        res = self.model.predict_proba(X)
        return np.asarray(res, dtype=np.float32)

    def predict(self, X: pd.DataFrame | np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Predict binary outcome (0: SUCCESS, 1: FAILURE) given classification threshold."""
        proba = self.predict_proba(X)
        return (proba[:, 1] >= threshold).astype(int)

    def predict_single(self, features: dict[str, float] | np.ndarray) -> tuple[float, str]:
        """Infer failure probability and categorical risk level for a single feature vector.

        Returns
        -------
        tuple[float, str]
            (probability: 0.0..1.0, risk_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL")
        """
        if isinstance(features, dict):
            vec = np.array([[features.get(k, 0.0) for k in self.feature_names]], dtype=np.float32)
        elif isinstance(features, np.ndarray):
            vec = features.reshape(1, -1)
        else:
            raise ValueError(f"Unsupported feature type: {type(features)}")

        proba = self.predict_proba(vec)[0, 1]
        prob_val = float(np.clip(proba, 0.0, 1.0))

        if prob_val < 0.25:
            risk_level = "LOW"
        elif prob_val < 0.55:
            risk_level = "MEDIUM"
        elif prob_val < 0.85:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return prob_val, risk_level


class WorkflowLatencyRegressor:
    """XGBoost gradient-boosted regression model predicting total workflow execution latency."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.08,
        subsample: float = 0.8,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.random_state = random_state
        self.feature_names = FEATURE_NAMES
        self.is_fitted = False

        self.model = XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            random_state=self.random_state,
            n_jobs=-1,
        )

    def fit(
        self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray
    ) -> "WorkflowLatencyRegressor":
        """Train the regressor on the provided feature matrix X and continuous latency targets y."""
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Predict total workflow latency in milliseconds."""
        if not self.is_fitted:
            n_samples = len(X) if hasattr(X, "__len__") else 1
            return np.array([450.0] * n_samples, dtype=np.float32)
        preds = self.model.predict(X)
        return np.asarray(np.maximum(preds, 0.0), dtype=np.float32)

    def predict_single(self, features: dict[str, float] | np.ndarray) -> float:
        """Infer expected total workflow duration in milliseconds for a single feature vector."""
        if isinstance(features, dict):
            vec = np.array([[features.get(k, 0.0) for k in self.feature_names]], dtype=np.float32)
        elif isinstance(features, np.ndarray):
            vec = features.reshape(1, -1)
        else:
            raise ValueError(f"Unsupported feature type: {type(features)}")

        pred = self.predict(vec)[0]
        return float(max(0.0, pred))
