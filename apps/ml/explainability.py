"""TreeSHAP explainability engine for failure and latency predictions."""

import numpy as np
import shap

from apps.ml.features import FEATURE_NAMES
from apps.ml.models import WorkflowFailureClassifier
from packages.domain.intelligence import FeatureContribution


class TreeSHAPExplainer:
    """Computes exact TreeSHAP feature attributions and diagnostic explanations."""

    def __init__(
        self,
        classifier: WorkflowFailureClassifier,
        feature_names: list[str] | None = None,
    ) -> None:
        self.classifier = classifier
        self.feature_names = feature_names or FEATURE_NAMES
        self._explainer: shap.TreeExplainer | None = None

        if self.classifier.is_fitted:
            self._init_explainer()

    def _init_explainer(self) -> None:
        """Initialize SHAP TreeExplainer from the underlying XGBoost model."""
        try:
            self._explainer = shap.TreeExplainer(self.classifier.model)
        except Exception:
            self._explainer = None

    def explain_instance(
        self,
        features: dict[str, float] | np.ndarray,
        top_k: int = 5,
    ) -> list[FeatureContribution]:
        """Compute TreeSHAP feature attributions for a single workflow feature vector.

        Parameters
        ----------
        features : dict[str, float] | np.ndarray
            Input feature vector.
        top_k : int
            Number of top contributing features to return.

        Returns
        -------
        list[FeatureContribution]
            Ranked list of feature contributions with diagnostic descriptions.
        """
        if isinstance(features, dict):
            feat_dict = features
            vec = np.array([[features.get(k, 0.0) for k in self.feature_names]], dtype=np.float32)
        elif isinstance(features, np.ndarray):
            vec = features.reshape(1, -1)
            feat_dict = {
                self.feature_names[i]: float(vec[0, i])
                for i in range(min(len(self.feature_names), vec.shape[1]))
            }
        else:
            raise ValueError(f"Unsupported feature type: {type(features)}")

        if not self._explainer and self.classifier.is_fitted:
            self._init_explainer()

        contributions: list[FeatureContribution] = []

        if self._explainer is not None:
            try:
                shap_values = self._explainer.shap_values(vec)
                if isinstance(shap_values, list) and len(shap_values) > 1:
                    raw_shap = shap_values[1][0]
                elif isinstance(shap_values, np.ndarray):
                    raw_shap = shap_values[0] if shap_values.ndim == 2 else shap_values
                else:
                    raw_shap = np.zeros(len(self.feature_names))

                for i, feat_name in enumerate(self.feature_names):
                    if i < len(raw_shap):
                        val = feat_dict.get(feat_name, 0.0)
                        attr = float(raw_shap[i])
                        desc = self._generate_diagnostic_text(feat_name, val, attr)
                        contributions.append(
                            FeatureContribution(
                                feature_name=feat_name,
                                value=val,
                                contribution=attr,
                                description=desc,
                            )
                        )
            except Exception:
                contributions = self._heuristic_fallback_attributions(feat_dict)
        else:
            contributions = self._heuristic_fallback_attributions(feat_dict)

        # Sort by absolute SHAP impact
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        return contributions[:top_k]

    def _generate_diagnostic_text(self, name: str, val: float, attribution: float) -> str:
        """Create human-readable diagnostic messages explaining the feature's influence."""
        sign = "+" if attribution > 0 else "-"
        abs_attr = abs(attribution)

        specific_diag = self._get_specific_diagnostic(name, val, sign, abs_attr)
        if specific_diag:
            return specific_diag

        direction = "increased failure risk" if attribution > 0 else "reduced failure risk"
        return f"{name.replace('_', ' ').title()} ({val:.1f}) {direction} by {abs_attr:.2f}"

    def _get_specific_diagnostic(
        self, name: str, val: float, sign: str, abs_attr: float
    ) -> str | None:
        """Helper to format specific feature diagnostics."""
        if name == "payment_service_latency_ms" and val > 500.0:
            return f"Severe payment gateway latency ({val:.1f}ms) elevated failure risk ({sign}{abs_attr:.2f})"
        if name == "cumulative_retries" and val > 0:
            return f"Multiple retry events ({int(val)} retries) detected during execution ({sign}{abs_attr:.2f})"
        if name == "cumulative_errors" and val > 0:
            return f"Intermediate operational errors ({int(val)} failures) elevated risk ({sign}{abs_attr:.2f})"
        if name == "has_cache_miss" and val > 0:
            return (
                f"Customer profile cache miss caused unbuffered DB queries ({sign}{abs_attr:.2f})"
            )
        if name == "latency_ratio_vs_nominal" and val > 1.5:
            return f"Workflow latency is {val:.1f}x slower than nominal baseline ({sign}{abs_attr:.2f})"
        if name == "last_step_latency_ms" and val > 300.0:
            return f"Recent step had elevated latency ({val:.1f}ms) ({sign}{abs_attr:.2f})"
        return None

    def _heuristic_fallback_attributions(
        self, feat_dict: dict[str, float]
    ) -> list[FeatureContribution]:
        """Fallback attribution calculator when tree explainer is not available."""
        contributions: list[FeatureContribution] = []
        for name, val in feat_dict.items():
            attr = 0.0
            if "latency" in name and val > 200.0:
                attr = (val - 200.0) / 500.0
            elif "retries" in name and val > 0:
                attr = val * 0.4
            elif "errors" in name and val > 0:
                attr = val * 0.8

            desc = self._generate_diagnostic_text(name, val, attr)
            contributions.append(
                FeatureContribution(
                    feature_name=name,
                    value=val,
                    contribution=attr,
                    description=desc,
                )
            )
        return contributions
