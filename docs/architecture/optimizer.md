# Architecture: Workflow Optimizer & Execution Path Routing (Milestone 9)

## 1. Overview & Objectives

In modern distributed microservice systems, complex business workflows often have multiple candidate execution paths, caching branches, and fallback routes (e.g. `customer-cache` vs `customer-db`, `express-lane` vs `standard-batch`, `primary-gateway` vs `secondary-fallback`).

The **Workflow Optimizer Engine** evaluates candidate execution paths across three competing engineering dimensions:
1. **Observed Latency ($L_{\text{obs}}$)**: End-to-end trace duration directly aggregated from historical telemetry.
2. **Observed Reliability ($R_{\text{obs}}$)**: Empirical success rate ($1.0 - \text{failure\_rate}$) and retry intensity.
3. **Modeled Resource Cost ($C_{\text{model}}$)**: Explicit, transparent resource cost units calculated from compute base cost, database I/O units, and retry penalties.

```
 +------------------------------------------------------------------------------------------------+
 |                                  Historical & In-Flight Inputs                                 |
 +------------------------------------------------------------------------------------------------+
     |                                          |                                         |
     v                                          v                                         v
 +----------------------------+    +----------------------------+    +----------------------------+
 | Historical Trace Events    |    | M6 Risk Predictions & SHAP |    | M8 Root Culprits & M7 Anom |
 | (Observed Latency/Errors)  |    | Predicted failure/latency  |    | Active service bottlenecks |
 +----------------------------+    +----------------------------+    +----------------------------+
     |                                          |                                         |
     +------------------------------------------+-----------------------------------------+
                                                |
                                                v
 +------------------------------------------------------------------------------------------------+
 |                           Milestone 9: Workflow Optimizer Engine                               |
 +------------------------------------------------------------------------------------------------+
 |  1. Path Miner: Reconstructs observed DAG execution paths & aggregates (L_obs, R_obs, C_model)|
 |  2. Transparent Cost Model: C(P) = sum(base_unit(s)) + I/O_weight(db) + retry_penalty(r)       |
 |  3. Pareto Frontier: Computes non-dominated 3D frontier (P_i is not strictly worse than P_j)  |
 |  4. Weighted Multi-Objective Utility: U(P) = w_lat * U_lat(P) + w_cost * U_cost(P) + w_rel * R |
 |  5. Advisory Diversion Recommendation: Reroutes around M8 culprits to optimal fallback branch |
 +------------------------------------------------------------------------------------------------+
                                                |
     +------------------------------------------+-----------------------------------------+
     |                                          |                                         |
     v                                          v                                         v
 +----------------------------+    +----------------------------+    +----------------------------+
 | PostgreSQL Persistence     |    | FastAPI REST Gateway       |    | React Optimizer Dashboard  |
 | workflow_optimizations     |    | /api/v1/optimizer          |    | Pareto chart & Path Diffs  |
 +----------------------------+    +----------------------------+    +----------------------------+
```

---

## 2. Mathematical Formulations

### A. Transparent Resource Cost Model
Unlike raw financial billing metrics, TraceMind explicitly models operational cost units:
$$C_{\text{model}}(P_k) = \sum_{i=1}^m \text{ServiceBaseCost}(s_i) + \sum_{db \in P_k} \text{DatabaseIOCost}(db) + \alpha \cdot \text{RetryCount}(P_k)$$

* Base stateless services (`auth`, `pricing`, `notification`): $1.0\text{ unit}$
* Gateway / Business services (`api-gateway`, `order-service`, `payment-service`): $2.0\text{ units}$
* Database queries (`customer-db`, `inventory-db`): $+2.5\text{ I/O units}$
* Cache discounts (`customer-cache`, `inventory-cache`): $-50\%\text{ base compute discount}$
* Retry amplification penalty $\alpha$: $+1.5\text{ units/retry}$

### B. 3D Pareto Dominance
A path $P_a$ dominates $P_b$ ($P_a \succ P_b$) if and only if:
1. $L(P_a) \le L(P_b)$, $C(P_a) \le C(P_b)$, and $R(P_a) \ge R(P_b)$
2. At least one metric is strictly superior ($L(P_a) < L(P_b) \lor C(P_a) < C(P_b) \lor R(P_a) > R(P_b)$)

The **Pareto Optimal Frontier Set** $\mathcal{P}^*$:
$$\mathcal{P}^* = \{ P \in \mathcal{P} \mid \nexists P' \in \mathcal{P} \text{ such that } P' \succ P \}$$

### C. Multi-Objective Utility Function
Given user-defined normalized weights $(w_{\text{lat}}, w_{\text{cost}}, w_{\text{rel}})$ where $\sum w_i = 1.0$:
$$U_{\text{lat}}(P) = 1.0 - \frac{L(P) - L_{\min}}{L_{\max} - L_{\min} + \epsilon}$$
$$U_{\text{cost}}(P) = 1.0 - \frac{C(P) - C_{\min}}{C_{\max} - C_{\min} + \epsilon}$$
$$U_{\text{rel}}(P) = R(P)$$

$$\text{UtilityScore}(P) = \left( w_{\text{lat}} \cdot U_{\text{lat}}(P) + w_{\text{cost}} \cdot U_{\text{cost}}(P) + w_{\text{rel}} \cdot U_{\text{rel}}(P) \right) \times \left(0.5 + 0.5 \cdot \text{Confidence}(P)\right)$$

Where $\text{Confidence}(P) = \min(1.0, N(P) / N_{\text{thresh}})$ discounts paths with low sample count.

---

## 3. Advisory Incident Diversion

When an active bottleneck or M8 root culprit (e.g. `inventory-db` IOPS saturation, `payment-gateway` packet drop) is supplied:
1. Paths traversing the failing component incur latency and reliability penalties ($3.5\times$ latency, $-50\%$ reliability).
2. The optimizer computes the optimal diversion path (e.g. cache-accelerated path or secondary provider).
3. The engine outputs structured engineering rationale and verifiable expected savings ($\Delta \text{Latency} \ge 15.0\%$ or $\Delta \text{Reliability} \ge 15.0\%$) with advisory-only routing semantics.

---

## 4. Benchmark Performance

Evaluating 1,000 iterations in `benchmarks/benchmark_workflow_optimizer.py`:
* **P50 Latency**: `0.133 ms`
* **P95 Latency**: `0.284 ms`
* **P99 Latency**: `0.369 ms` (Quality Gate: $< 10.0\text{ ms}$)
* **Throughput**: `6,045.5 optimizations / sec`
* **Incident Diversion Efficacy**: `100.0% PASS` across all chaos presets with up to `87.8%` latency reduction.
