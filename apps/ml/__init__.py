"""TraceMind Machine Learning Engine for Failure & Latency Prediction with TreeSHAP Explainability."""

from apps.ml.explainability import TreeSHAPExplainer
from apps.ml.features import FEATURE_NAMES, TraceFeatureExtractor
from apps.ml.models import WorkflowFailureClassifier, WorkflowLatencyRegressor
from apps.ml.registry import ModelRegistry
from apps.ml.trainer import ModelTrainer

__all__ = [
    "FEATURE_NAMES",
    "TraceFeatureExtractor",
    "WorkflowFailureClassifier",
    "WorkflowLatencyRegressor",
    "TreeSHAPExplainer",
    "ModelTrainer",
    "ModelRegistry",
]

__version__ = "0.6.0"
