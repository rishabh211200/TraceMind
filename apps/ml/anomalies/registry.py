"""Thread-safe singleton registry for managing, caching, and persisting anomaly detection models."""

import json
from pathlib import Path
from threading import RLock
from typing import Any

import joblib
import structlog

from apps.ml.anomalies.cascade_detector import ErrorCascadeAnomalyDetector
from apps.ml.anomalies.composite import CompositeAnomalyDetector
from apps.ml.anomalies.isolation_forest import WorkflowIsolationForestDetector
from apps.ml.anomalies.latency_detector import ServiceLatencyAnomalyDetector
from apps.ml.anomalies.sequence_detector import TransitionPathAnomalyDetector
from apps.simulator.config import SimulationConfig
from apps.simulator.workflow_engine import TraceSimulator
from packages.domain.events import TraceEvent

logger = structlog.get_logger(__name__)

DEFAULT_ANOMALY_MODELS_DIR = Path("data/anomalies")


class AnomalyDetectorRegistry:
    """Thread-safe singleton registry for caching and serving anomaly detectors."""

    _instance: "AnomalyDetectorRegistry | None" = None
    _lock: RLock = RLock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "AnomalyDetectorRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, models_dir: Path | str | None = None) -> None:
        if getattr(self, "_initialized", False):
            return

        self.models_dir = Path(models_dir or DEFAULT_ANOMALY_MODELS_DIR)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._composite_detector: CompositeAnomalyDetector | None = None
        self._version: str = "1.0.0"
        self._initialized = True

    def get_detector(self) -> CompositeAnomalyDetector:
        """Retrieve active composite anomaly detector from memory or bootstrap from disk/simulation."""
        with self._lock:
            if self._composite_detector is not None:
                return self._composite_detector

            # Try loading from disk
            loaded = self._load_from_disk()
            if loaded is not None:
                self._composite_detector = loaded
                return self._composite_detector

            # Bootstrap default baselines
            self._bootstrap_default_baselines()
            assert self._composite_detector is not None
            return self._composite_detector

    def save_detector(
        self,
        detector: CompositeAnomalyDetector,
        version: str = "1.0.0",
    ) -> None:
        """Save fitted detector artifacts to disk."""
        with self._lock:
            target_dir = self.models_dir / f"v_{version}"
            target_dir.mkdir(parents=True, exist_ok=True)

            # 1. Isolation Forest
            if detector.isolation_forest.is_fitted:
                joblib.dump(
                    detector.isolation_forest.model,
                    target_dir / "isolation_forest.joblib",
                )

            # 2. Service Latency Stats
            with open(target_dir / "latency_stats.json", "w", encoding="utf-8") as f:
                json.dump(detector.latency_detector.service_stats, f, indent=2)

            # 3. Transition Probabilities
            with open(target_dir / "transition_probs.json", "w", encoding="utf-8") as f:
                json.dump(detector.sequence_detector.transition_probs, f, indent=2)

            self._composite_detector = detector
            self._version = version
            logger.info("anomaly_detector_saved", version=version, path=str(target_dir))

    def _load_from_disk(self) -> CompositeAnomalyDetector | None:
        """Attempt loading persisted anomaly detectors from disk."""
        try:
            versions = sorted(self.models_dir.glob("v_*"), reverse=True)
            if not versions:
                return None

            latest_dir = versions[0]
            if_path = latest_dir / "isolation_forest.joblib"
            lat_path = latest_dir / "latency_stats.json"
            seq_path = latest_dir / "transition_probs.json"

            iso_detector = WorkflowIsolationForestDetector()
            if if_path.exists():
                iso_detector.model = joblib.load(if_path)
                iso_detector.is_fitted = True

            lat_detector = ServiceLatencyAnomalyDetector()
            if lat_path.exists():
                with open(lat_path, encoding="utf-8") as f:
                    lat_detector.service_stats = json.load(f)
                    lat_detector.is_fitted = True

            seq_detector = TransitionPathAnomalyDetector()
            if seq_path.exists():
                with open(seq_path, encoding="utf-8") as f:
                    seq_detector.transition_probs = json.load(f)
                    seq_detector.is_fitted = True

            cascade_detector = ErrorCascadeAnomalyDetector()

            detector = CompositeAnomalyDetector(
                isolation_forest=iso_detector,
                latency_detector=lat_detector,
                sequence_detector=seq_detector,
                cascade_detector=cascade_detector,
            )
            self._version = latest_dir.name.replace("v_", "")
            logger.info("anomaly_detectors_loaded_from_disk", version=self._version)
            return detector
        except Exception as e:
            logger.warning("failed_loading_anomaly_models_from_disk", error=str(e))
            return None

    def _bootstrap_default_baselines(self) -> None:
        """Generate nominal synthetic traces to calibrate baseline detectors."""
        logger.info("bootstrapping_default_anomaly_baselines")
        sim_cfg = SimulationConfig(workflow_count=200, arrival_rate_per_second=20.0, seed=42)
        sim = TraceSimulator(config=sim_cfg)
        result = sim.run()

        # 1. Fit Latency Detector
        lat_detector = ServiceLatencyAnomalyDetector()
        lat_detector.fit_from_events(result.events)

        # 2. Fit Transition Sequence Detector
        seq_events_map: dict[str, list[TraceEvent]] = {}
        for evt in result.events:
            seq_events_map.setdefault(evt.execution_id, []).append(evt)

        seq_detector = TransitionPathAnomalyDetector()
        seq_detector.fit(seq_events_map)

        # 3. Fit Isolation Forest
        from apps.ml.features import TraceFeatureExtractor

        extractor = TraceFeatureExtractor()
        X, _, _, _ = extractor.extract_prefix_dataset(
            seq_events_map,
            {e.id: (e.status != "COMPLETED", e.total_latency_ms) for e in result.executions},
        )
        iso_detector = WorkflowIsolationForestDetector()
        iso_detector.fit(X)

        cascade_detector = ErrorCascadeAnomalyDetector()

        composite = CompositeAnomalyDetector(
            isolation_forest=iso_detector,
            latency_detector=lat_detector,
            sequence_detector=seq_detector,
            cascade_detector=cascade_detector,
        )

        self.save_detector(composite, version="1.0.0")
        self._composite_detector = composite
        logger.info("anomaly_detectors_bootstrapped", version="1.0.0")
