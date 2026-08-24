"""Multidimensional workflow outlier detection using Isolation Forest."""

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from apps.ml.features import FEATURE_NAMES, TraceFeatureExtractor
from packages.domain.events import TraceEvent


class WorkflowIsolationForestDetector:
    """Unsupervised multidimensional anomaly detector using Isolation Forest."""

    def __init__(
        self,
        n_estimators: int = 40,
        contamination: float = 0.05,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.random_state = random_state
        self.feature_extractor = TraceFeatureExtractor()
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=1,
        )
        self.is_fitted = False
        self._score_threshold: float = 0.0

    def fit(self, X: pd.DataFrame | np.ndarray) -> "WorkflowIsolationForestDetector":
        """Fit Isolation Forest on nominal workflow feature vectors."""
        X_arr = X[FEATURE_NAMES].to_numpy() if isinstance(X, pd.DataFrame) else np.asarray(X)
        self.model.fit(X_arr)
        # Compute baseline decision function scores on training data
        raw_train_scores = -self.model.decision_function(X_arr)
        self._score_threshold = float(np.percentile(raw_train_scores, 98.0))
        self.is_fitted = True
        return self

    def score_features(self, feature_dict: dict[str, float]) -> tuple[float, bool]:
        """Score an extracted feature dictionary.

        Returns
        -------
        tuple[float, bool]
            (normalized_score [0.0 - 1.0], is_anomaly [bool])
        """
        if not self.is_fitted:
            # Fallback for uncalibrated detector
            return 0.0, False

        feat_vector = np.array(
            [[feature_dict.get(k, 0.0) for k in FEATURE_NAMES]], dtype=np.float32
        )
        raw_score = float(-self.model.decision_function(feat_vector)[0])
        is_anomaly = raw_score >= self._score_threshold

        # Calibrate raw score into [0.0, 1.0] using sigmoid centering at threshold
        normalized_score = float(1.0 / (1.0 + np.exp(-12.0 * (raw_score - self._score_threshold))))
        normalized_score = max(0.0, min(1.0, normalized_score))

        return normalized_score, is_anomaly

    def score_events(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        as_of_step: int | None = None,
    ) -> tuple[float, bool, dict[str, float]]:
        """Extract features and score a sequence of trace events."""
        features = self.feature_extractor.extract_features_from_events(
            events, as_of_step=as_of_step
        )
        score, is_anomaly = self.score_features(features)
        return score, is_anomaly, features
