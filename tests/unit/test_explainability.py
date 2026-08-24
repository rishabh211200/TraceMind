"""Unit tests for TreeSHAP explainability engine and feature attributions."""

import pandas as pd

from apps.ml.explainability import TreeSHAPExplainer
from apps.ml.features import FEATURE_NAMES
from apps.ml.models import WorkflowFailureClassifier


def test_treeshap_explainer_computes_ranked_attributions():
    # Construct a synthetic training matrix
    X = pd.DataFrame(
        [
            [1.0, 50.0, 0.0, 0.0, 20.0, 20.0, 20.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            [
                5.0,
                1500.0,
                3.0,
                2.0,
                400.0,
                900.0,
                900.0,
                1.0,
                1.0,
                1.0,
                20.0,
                40.0,
                50.0,
                15.0,
                900.0,
                4.5,
            ],
        ]
        * 15,
        columns=FEATURE_NAMES,
    )
    y = pd.Series([0, 1] * 15)

    clf = WorkflowFailureClassifier(n_estimators=10, max_depth=3, random_state=42)
    clf.fit(X, y)

    explainer = TreeSHAPExplainer(classifier=clf)

    # Test explanation on failing instance with severe payment latency
    failing_feats = dict.fromkeys(FEATURE_NAMES, 0.0)
    failing_feats["payment_service_latency_ms"] = 1200.0
    failing_feats["cumulative_retries"] = 3.0
    failing_feats["cumulative_errors"] = 1.0
    failing_feats["step_count"] = 5.0

    contributions = explainer.explain_instance(failing_feats, top_k=5)

    assert len(contributions) > 0
    assert len(contributions) <= 5

    # Verify contributions are ranked by absolute magnitude
    magnitudes = [abs(c.contribution) for c in contributions]
    assert magnitudes == sorted(magnitudes, reverse=True)

    # Verify diagnostic text exists
    for c in contributions:
        assert c.feature_name in FEATURE_NAMES
        assert c.description is not None
        assert len(c.description) > 0
