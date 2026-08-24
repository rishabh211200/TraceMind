"""Model registry managing versioned serialization, loading, and in-memory caching."""

import json
from pathlib import Path
from typing import Any

import joblib

from apps.ml.explainability import TreeSHAPExplainer
from apps.ml.models import WorkflowFailureClassifier, WorkflowLatencyRegressor
from packages.common.logging import get_logger

logger = get_logger("tracemind.ml.registry")

DEFAULT_MODEL_DIR = Path("data/models")


class ModelRegistry:
    """Thread-safe singleton registry for machine learning model artifacts."""

    _instance: "ModelRegistry | None" = None

    def __new__(cls, model_dir: Path | str | None = None) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_dir: Path | str | None = None) -> None:
        if getattr(self, "_initialized", False):
            return

        self.model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self._classifier: WorkflowFailureClassifier | None = None
        self._regressor: WorkflowLatencyRegressor | None = None
        self._explainer: TreeSHAPExplainer | None = None
        self._metadata: dict[str, Any] = {
            "version": "1.0.0",
            "model_name": "xgboost_workflow_predictor",
            "status": "uninitialized",
            "metrics": {},
        }
        self._initialized = True

    def get_models(
        self,
    ) -> tuple[WorkflowFailureClassifier, WorkflowLatencyRegressor, TreeSHAPExplainer]:
        """Return active cached models, auto-loading from disk or bootstrapping if needed."""
        if self._classifier is None or self._regressor is None:
            loaded = self.load_latest()
            if not loaded:
                self.bootstrap_default_models()

        assert self._classifier is not None
        assert self._regressor is not None
        if self._explainer is None:
            self._explainer = TreeSHAPExplainer(self._classifier)

        return self._classifier, self._regressor, self._explainer

    def get_metadata(self) -> dict[str, Any]:
        """Return active model version, training metrics, and artifact metadata."""
        return self._metadata

    def save_models(
        self,
        classifier: WorkflowFailureClassifier,
        regressor: WorkflowLatencyRegressor,
        metrics: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> str:
        """Persist classifier, regressor, and metadata to disk."""
        target_dir = self.model_dir / f"v_{version}"
        target_dir.mkdir(parents=True, exist_ok=True)

        clf_path = target_dir / "classifier.joblib"
        reg_path = target_dir / "regressor.joblib"
        meta_path = target_dir / "metadata.json"

        joblib.dump(classifier, clf_path)
        joblib.dump(regressor, reg_path)

        metadata = {
            "version": version,
            "model_name": "xgboost_workflow_predictor",
            "status": "trained",
            "metrics": metrics or {},
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Update in-memory cache
        self._classifier = classifier
        self._regressor = regressor
        self._explainer = TreeSHAPExplainer(classifier)
        self._metadata = metadata

        logger.info("ml_models_persisted", version=version, target_dir=str(target_dir))
        return version

    def load_latest(self) -> bool:
        """Attempt to load the newest versioned model directory on disk."""
        versions = sorted(self.model_dir.glob("v_*"))
        if not versions:
            return False

        latest_dir = versions[-1]
        clf_path = latest_dir / "classifier.joblib"
        reg_path = latest_dir / "regressor.joblib"
        meta_path = latest_dir / "metadata.json"

        if not clf_path.exists() or not reg_path.exists():
            return False

        try:
            self._classifier = joblib.load(clf_path)
            self._regressor = joblib.load(reg_path)
            self._explainer = TreeSHAPExplainer(self._classifier)
            if meta_path.exists():
                self._metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            logger.info("ml_models_loaded_from_disk", version=self._metadata.get("version"))
            return True
        except Exception as exc:
            logger.warning("failed_to_load_saved_models", error=str(exc))
            return False

    def bootstrap_default_models(self) -> None:
        """Bootstrap and train default models on synthetic telemetry if none exist."""
        logger.info("bootstrapping_default_ml_models")
        from apps.ml.trainer import ModelTrainer

        trainer = ModelTrainer(random_state=42)
        X, y_fail, y_lat, groups = trainer.generate_synthetic_training_data(
            nominal_workflows=120,
            incident_workflows_per_scenario=25,
        )
        report = trainer.train_and_evaluate(X, y_fail, y_lat, groups=groups)

        self.save_models(
            classifier=report["classifier"],
            regressor=report["regressor"],
            metrics=report["metrics"],
            version="1.0.0",
        )
        logger.info("default_ml_models_bootstrapped", metrics=report["metrics"])
