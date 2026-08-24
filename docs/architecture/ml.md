# Milestone 6 Architecture: In-Flight Failure & Latency Prediction Engine with TreeSHAP Explainability

## 1. Overview & Objectives

Milestone 6 introduces machine learning workflow intelligence to TraceMind. As distributed microservice workflows execute, the system continuously extracts temporal feature vectors from in-flight trace span prefixes ($t \le t_k$) without future information leakage.

It provides:
1. **Failure Probability & Risk Classification**: Calibrated XGBoost gradient-boosted decision tree classifier categorizing risk into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
2. **Forecasted Latency & Duration Regression**: Gradient-boosted regression predicting remaining and total execution duration in milliseconds.
3. **Exact TreeSHAP Feature Attributions**: Mathematical local feature contributions $\sum \phi_i(x) + \phi_0 = f(x)$ identifying the exact microservices, retry storms, or database cache misses causing failure risk.

---

## 2. In-Flight Feature Extraction Pipeline

The feature extractor (`apps/ml/features.py`) calculates 16 tabular features from partial trace prefixes:

| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `step_count` | `float` | Number of executed spans/steps completed in the prefix |
| `elapsed_time_ms` | `float` | Wall-clock elapsed duration from first span start to last span completion |
| `cumulative_retries` | `float` | Total retry events recorded up to current step |
| `cumulative_errors` | `float` | Total intermediate failure events up to current step |
| `mean_step_latency_ms` | `float` | Arithmetic mean latency of completed spans in prefix |
| `max_step_latency_ms` | `float` | Peak span latency observed so far |
| `last_step_latency_ms` | `float` | Duration of the most recent step |
| `last_step_is_error` | `float` | Binary flag indicating if the most recent step failed |
| `has_cache_miss` | `float` | Binary flag for customer/inventory cache lookup misses |
| `has_database_query` | `float` | Binary flag for unbuffered database IO queries |
| `auth_service_latency_ms` | `float` | Cumulative latency spent in `auth-service` |
| `customer_service_latency_ms` | `float` | Cumulative latency spent in `customer-service` |
| `inventory_service_latency_ms` | `float` | Cumulative latency spent in `inventory-service` |
| `pricing_service_latency_ms` | `float` | Cumulative latency spent in `pricing-service` |
| `payment_service_latency_ms` | `float` | Cumulative latency spent in `payment-service` |
| `latency_ratio_vs_nominal` | `float` | Actual elapsed duration divided by nominal baseline expectations |

### Temporal Integrity Guarantee
During inference at timestamp $t_k$, all spans where $t > t_k$ are strictly pruned, guaranteeing mathematical zero-leakage of future events.

---

## 3. TreeSHAP Feature Attribution Engine

TreeSHAP (`apps/ml/explainability.py`) extracts exact Shapley values directly from decision tree path structures via `shap.TreeExplainer`:
$$\phi_0 + \sum_{i=1}^{M} \phi_i(x) = f(x)$$

Each feature attribution includes:
- **`contribution`**: Positive (+$\phi$) elevates failure risk; negative (-$\phi$) indicates healthy operation.
- **`description`**: Diagnostic natural-language explanation for root-cause diagnosis.

---

## 4. Performance & Latency Benchmarks

From `benchmarks/benchmark_ml_inference.py` (1,000 runs):
* **Feature Extraction Throughput**: **37,414 extractions/sec**
* **End-to-End Inference Throughput**: **356 inferences/sec** (including TreeSHAP path analysis)
* **P50 Latency**: **2.65 ms**
* **P90 Latency**: **3.57 ms**
* **P95 Latency**: **3.92 ms**
* **P99 Latency**: **4.37 ms** (Target: $< 15.0\text{ms}$ — **Passed**)
