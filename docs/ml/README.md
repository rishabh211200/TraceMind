# TraceMind Machine Learning & Statistical Modeling

This directory documents model architectures, feature engineering pipelines, evaluation protocols, and explainability strategies.

## Models & Objectives

1. **In-Flight Failure Classifier**: Predicts workflow failure likelihood before completion using cumulative step features and latency aggregates. (Evaluated with Precision-Recall AUC, ROC-AUC, Brier Score).
2. **Workflow Latency Regressor**: Forecasts total workflow duration and bottlenecks. (Evaluated with MAE, RMSE, R²).
3. **Unsupervised Outlier Detector**: Identifies behavioral anomalies in paths and execution durations. (Isolation Forest, Gaussian Mixture Models).
4. **SHAP Feature Attribution**: Computes TreeSHAP feature contributions for each prediction to explain why a workflow was flagged.
