# Production Containerization & Cloud Deployment Architecture

## 1. Overview & Topology

Milestone 12 transitions TraceMind into an **enterprise-grade, containerized production platform**. It decouples application services, hardens container security postures, provides production Docker Compose and declarative cloud-ready Kubernetes manifests, and implements automated pre-deployment schema migrations and comprehensive smoke testing.

```
                                  [ INTERNET / INGRESS ]
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │    Edge Nginx Ingress / CDN   │
                             │  - TLS Termination            │
                             │  - SPA Routing & Caching      │
                             │  - Security Headers (CSP/HSTS)│
                             └───────────────┬───────────────┘
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      │ /                                           │ /api/*, /metrics
                      ▼                                             ▼
       ┌───────────────────────────────┐             ┌───────────────────────────────┐
       │     Frontend Web Service      │             │       FastAPI API Gateway     │
       │   (Nginx Alpine / React 18)   │             │   (Python 3.12 / Non-Root)    │
       │   - Replicas: 2+              │             │   - Replicas: 3+ (HPA)        │
       │   - Port: 80                  │             │   - Liveness/Readiness Probes │
       └───────────────────────────────┘             └───────────────┬───────────────┘
                                                                     │
            ┌────────────────────────────────────────────────────────┼────────────────────────────┐
            │                                                        │                            │
            ▼                                                        ▼                            ▼
┌───────────────────────────────┐                        ┌───────────────────────┐    ┌───────────────────────┐
│     Streaming Ingest Worker   │                        │   Prometheus & Grafana│    │   Alembic Migrator    │
│  (aiokafka / Batch Persist)   │                        │ (Port 9090 / Port 3000│    │  (Init Container/Job) │
│  - Micro-batch flush (50ms)   │                        │  - Auto-provisioned)  │    │  - Runs before Gateway│
└───────────────┬───────────────┘                        └───────────────────────┘    └───────────┬───────────┘
                │                                                                                 │
                └────────────────────────────┬────────────────────────────────────────────────────┘
                                             │
                ┌────────────────────────────┴────────────────────────────┐
                ▼                                                         ▼
┌───────────────────────────────┐                         ┌───────────────────────────────┐
│   PostgreSQL / TimescaleDB    │                         │         Apache Kafka          │
│ (Persistent Partitioned Store)│                         │     (Message Broker / KRaft)  │
└───────────────────────────────┘                         └───────────────────────────────┘
```

---

## 2. Hardened Multi-Stage Container Images

All application container images adhere to strict container security standards:

| Image Target | Dockerfile | Base Image | Non-Root User | Key Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **API Gateway** | `infrastructure/docker/Dockerfile.api` | `python:3.12-slim` | `tracemind:10001` | Multi-stage `uv` build, RFC 7807 healthcheck probe. |
| **Streaming Worker** | `infrastructure/docker/Dockerfile.worker` | `python:3.12-slim` | `tracemind:10001` | Dedicated Kafka consumer daemon with graceful SIGTERM drain. |
| **Alembic Migrator** | `infrastructure/docker/Dockerfile.migrator` | `python:3.12-slim` | `tracemind:10001` | Pre-deployment schema execution container. |
| **Frontend Web** | `infrastructure/docker/Dockerfile.frontend` | `nginx:alpine` | `nginx:101` | Vite static bundle compilation + hardened Nginx server. |

### Container Security Baseline
* **No Root Execution**: All application containers run under UID `10001:10001` (`tracemind`).
* **Dropped Capabilities**: In Kubernetes and Compose, containers explicitly drop all Linux capabilities (`cap_drop: [ALL]`) and disallow privilege escalation (`no-new-privileges: true`).
* **Minimal Attack Surface**: Build tools (`build-essential`, compilers, `uv`) are confined to builder stages and never included in runtime layers.
* **Logging Rotation**: Production Compose configures `json-file` log rotation with `max-size: 50m` and `max-file: 5` to prevent disk exhaustion.

---

## 3. Production Deployment Topologies

### 3.1 Single-Node / Multi-Core Server (`docker-compose.prod.yml`)
For self-hosted virtual machines (e.g. AWS EC2, GCP Compute Engine, Bare-Metal):

```bash
# 1. Copy production environment file
cp .env.production.example .env.production

# 2. Launch production stack in background
docker compose -f docker-compose.prod.yml up -d --build
```

**Key Compose Features**:
* `migrator` service runs `alembic upgrade head` and must complete with `service_completed_successfully` before `api` and `worker` launch.
* CPU and Memory reservations and limits enforced across all services.
* Isolated bridge network `tracemind-internal`.
* Named persistent storage volumes (`postgres_prod_data`, `kafka_prod_data`, `prometheus_prod_data`, `grafana_prod_data`).

### 3.2 Declarative Kubernetes Suite (`infrastructure/k8s/`)
Cloud-ready manifests for managed Kubernetes clusters (AWS EKS, GCP GKE, Azure AKS):

* **`namespace.yaml`**: Dedicated `tracemind` namespace.
* **`configmap.yaml`**: Centralized non-sensitive configuration (log levels, topic names, pool sizes).
* **`secrets.yaml`**: Secure template with zero real credentials (intended for population via External Secrets Operator / AWS Secrets Manager / Vault).
* **`job-migration.yaml`**: Pre-deployment schema migration Job.
* **`deployment-api.yaml`**: Scalable API Gateway deployment with Horizontal Pod Autoscaler (HPA, 2–10 replicas) and HTTP Liveness/Readiness probes.
* **`deployment-worker.yaml`**: Dedicated streaming ingestion consumer pods.
* **`deployment-frontend.yaml`**: High-availability Nginx frontend deployment.
* **`ingress.yaml`**: Ingress controller routing `/` to Frontend, `/api/` to API Gateway, and `/metrics` to Prometheus scraper.

---

## 4. Production Validation: 11-Subsystem Smoke Test Suite



```bash
python scripts/smoke_test.py http://localhost:8000
```

### Validated Subsystems
1. **System Health Probe**: `GET /api/v1/health` (all 10 modules operational).
2. **Root Metadata & Version**: `GET /` (service metadata & OpenAPI documentation).
3. **Microservices Topology Graph**: `GET /api/v1/services/topology`.
4. **Workflow DAG Definition Registry**: `GET /api/v1/workflows`.
5. **Deterministic TraceSim Generator**: `POST /api/v1/simulator/generate`.
6. **In-Flight XGBoost & TreeSHAP Inference**: `POST /api/v1/predictions/predict`.
7. **Unsupervised Outlier & Anomaly Detection**: `POST /api/v1/anomalies/detect`.
8. **Causal Graph Root Cause Reasoning**: `POST /api/v1/root-cause/analyze`.
9. **Multi-Objective 3D Pareto Optimizer**: `POST /api/v1/optimizer/recommend`.
10. **Tool-Grounded Conversational AI Analyst**: `POST /api/v1/analyst/chat`.
11. **Prometheus Metrics Exposition**: `GET /metrics`.

---

## 5. Rollback & Disaster Recovery Runbook

1. **Zero-Downtime Schema Evolution**: All database migrations adhere to the expand-contract pattern. New columns are nullable or have defaults; old columns are only dropped in subsequent releases.
2. **Instant Container Rollback**: In Kubernetes, roll back deployments instantly to previous stable revisions:
   ```bash
   kubectl rollout undo deployment/tracemind-api -n tracemind
   ```
3. **Database Point-in-Time Recovery**: TimescaleDB / PostgreSQL automated WAL archiving allows point-in-time recovery without trace event data loss.
