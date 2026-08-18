# TraceMind — Telemetry Persistence & Querying Architecture

This document specifies the persistence, time-series storage, ingestion, and querying architecture implemented in **Milestone 2** of TraceMind.

---

## 1. Overview & Architectural Role

TraceMind captures high-throughput telemetry generated across microservices in distributed workflows. To support real-time operational querying, historical analytics, and machine learning model training without sacrificing analytical performance, the persistence layer uses a hybrid relational / time-series architecture combining **PostgreSQL** and **TimescaleDB**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                          TraceMind Application                         │
│   (TraceSim Generator / Live Trace Ingestor / FastAPI Backend / ML)    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                    Async SQLAlchemy 2.0 + asyncpg
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     PostgreSQL 16 + TimescaleDB                        │
│                                                                        │
│   ┌────────────────────────────────┐  ┌────────────────────────────┐   │
│   │     Relational Metadata        │  │   TimescaleDB Hypertable   │   │
│   │────────────────────────────────│  │────────────────────────────│   │
│   │ • services                     │  │ • trace_events             │   │
│   │ • workflow_definitions         │  │   - Partitioned: timestamp │   │
│   │ • workflow_executions          │  │   - Chunk: 1 day           │   │
│   │ • incidents                    │  │   - DB-side percentiles    │   │
│   └────────────────────────────────┘  └────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.1 PostgreSQL Role
* **Relational Integrity & Metadata**: Manages service registries (`services`), static workflow definitions (`workflow_definitions`), execution lifecycle records (`workflow_executions`), and ground-truth incident annotations (`incidents`).
* **ACID Transactions**: Guarantees deterministic state tracking, foreign key constraints, and relational consistency.
* **JSONB Capabilities**: Accommodates flexible metadata payloads, service dependencies, and dynamic chaos parameters without schema drift.

### 1.2 TimescaleDB Role
* **High-Volume Telemetry (`trace_events`)**: Converts standard PostgreSQL tables into partitioned **hypertables** across the `timestamp` dimension.
* **Automated Chunk Management**: Partitions incoming spans into discrete time chunks (configured to 1 day for production volumes), preventing large B-tree index degradation.
* **Database-Side Analytical Aggregations**: Computes statistical latency distributions (`percentile_cont(0.50)`, `percentile_cont(0.95)`, `percentile_cont(0.99)`, `AVG`, `MIN`, `MAX`) directly within the database engine rather than transmitting millions of raw event rows across the network to Python.
* **Future Compression & Retention (Milestone 13)**: Native columnar compression reduces storage footprint by up to $90\%$ for aged trace chunks.

---

## 2. Domain-to-Persistence Mapping

The persistence schema maps directly to TraceSim output models:

```text
TraceSim Domain Model                Persistence Table
─────────────────────                ─────────────────
ServiceModel                  ───►   services
WorkflowDefinition            ───►   workflow_definitions
WorkflowExecution             ───►   workflow_executions
TraceEvent                    ───►   trace_events (Hypertable)
Incident                      ───►   incidents
```

### 2.1 Detailed Schema Mapping

| TraceSim Domain Field | Persistence Column | SQL Type | Description / Constraints |
|---|---|---|---|
| **`WorkflowExecution.id`** | `workflow_executions.id` | `VARCHAR(64)` | Primary Key (e.g. `exec_42_000001`) |
| `workflow_definition_id` | `workflow_definition_id` | `VARCHAR(64)` | Foreign Key $\rightarrow$ `workflow_definitions.id` |
| `started_at` | `started_at` | `TIMESTAMPTZ` | Indexed start timestamp |
| `completed_at` | `completed_at` | `TIMESTAMPTZ` | Indexed completion timestamp |
| `total_latency_ms` | `duration_ms` | `FLOAT` | Aggregate execution wall time (ms) |
| `status` | `status` | `VARCHAR(32)` | Status enum (`COMPLETED`, `FAILED`, `TIMEOUT`) |
| `retry_count` | `retry_count` | `INTEGER` | Total retry attempts across all hops |
| `error_count` | `error_count` | `INTEGER` | Total service errors encountered |
| `failure_reason` | `failure_reason` | `TEXT` | Nullable error explanation |
| `metadata["incident_id"]` | `incident_id` | `VARCHAR(64)` | Ground-truth incident ID reference |
| `metadata["is_incident_affected"]`| `is_incident_affected` | `BOOLEAN` | Boolean flag indicating incident impact |
| `metadata` | `metadata` | `JSONB` | Flexible correlation & telemetry metadata |
| **`TraceEvent.event_id`** | `trace_events.event_id` | `VARCHAR(64)` | Composite Primary Key with `timestamp` |
| **`TraceEvent.timestamp`** | `trace_events.timestamp` | `TIMESTAMPTZ` | Partitioning Key (TimescaleDB hypertable) |
| `execution_id` | `execution_id` | `VARCHAR(64)` | Trace ID reference (Indexed with `timestamp`) |
| `service` | `service` | `VARCHAR(64)` | Emitting service (Indexed with `timestamp`) |
| `operation` | `operation` | `VARCHAR(64)` | Operation name |
| `event_type` | `event_type` | `VARCHAR(32)` | Event type enum (`SERVICE_COMPLETED`, etc.) |
| `status` | `status` | `VARCHAR(32)` | Status enum (`SUCCESS`, `FAILURE`, `RETRY`, `TIMEOUT`) |
| `latency_ms` | `latency_ms` | `FLOAT` | Span latency duration (ms) |
| `parent_event_id` | `parent_event_id` | `VARCHAR(64)` | Parent span ID for DAG tree reconstruction |
| `correlation_id` | `correlation_id` | `VARCHAR(64)` | Distributed correlation ID |
| `metadata` | `metadata` | `JSONB` | In-flight concurrency load, errors, retry attempt |
| **`Incident.id`** | `incidents.id` | `VARCHAR(64)` | Primary Key (e.g. `inc_000100_database`) |
| `scenario_type` | `scenario_type` | `VARCHAR(64)` | Chaos scenario identifier |
| `severity` | `severity` | `VARCHAR(32)` | Severity level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `started_at` / `ended_at` | `started_at` / `ended_at` | `TIMESTAMPTZ` | Incident active time window |
| `affected_services` | `affected_services` | `JSONB` | List of degraded services |
| `ground_truth_root_cause` | `ground_truth_root_cause` | `TEXT` | Ground-truth root cause description |
| `description` | `description` | `TEXT` | Human-readable incident summary |
| `parameters` | `parameters` | `JSONB` | Degradation multipliers & chaos parameters |

---

## 3. TimescaleDB Hypertable & Primary Key Design Decision

### 3.1 TimescaleDB Unique Index Requirement
TimescaleDB enforces an essential architectural constraint: **any unique or primary key constraint on a hypertable MUST include the partitioning column (`timestamp`)**. Defining `PRIMARY KEY (event_id)` alone causes TimescaleDB's `create_hypertable` to fail with:
```text
ERROR: cannot create a unique index without the partitioning column
```

### 3.2 Implemented Key & Index Strategy
1. **Composite Primary Key**:
   `PRIMARY KEY (event_id, timestamp)` guarantees event uniqueness across distributed emitters while satisfying TimescaleDB chunk routing requirements.
2. **Composite Indexes**:
   * `ix_trace_events_exec_ts`: `(execution_id, timestamp)` $\rightarrow$ allows sub-millisecond retrieval of all spans for a specific trace in chronological order.
   * `ix_trace_events_svc_ts`: `(service, timestamp)` $\rightarrow$ optimizes time-window queries filtering by service (e.g. 1-hour service latency percentiles).
   * `ix_trace_events_type_ts`: `(event_type, timestamp)` $\rightarrow$ accelerates event type breakdowns (`RETRY_STARTED`, `DATABASE_QUERY`).
   * `ix_trace_events_status_ts`: `(status, timestamp)` $\rightarrow$ optimizes error and timeout rate aggregations.
   * `ix_trace_events_parent`: `(parent_event_id)` $\rightarrow$ optimizes parent-child span traversal.

---

## 4. Bulk Ingestion Architecture

The ingestion pipeline (`packages/database/ingestion.py`) handles high-throughput loading from Parquet and JSONL datasets:

```text
   executions.parquet / events.parquet / incidents.parquet
                             │
                             ▼
                   PyArrow / Pandas Reader
                             │
                     Chunking (5,000 / batch)
                             │
                             ▼
              SQLAlchemy AsyncSession (Merge / Batch)
                             │
                             ▼
                PostgreSQL / TimescaleDB
                 (Idempotent Ingestion)
```

### 4.1 Ingestion Characteristics
* **Chunked Batching**: Events are streamed in chunks of 5,000 records to maintain constant memory footprint regardless of dataset size.
* **Idempotency**: All ingestion operations use primary-key merges or conflict-handling (`ON CONFLICT DO NOTHING`), allowing re-ingestion of the same dataset without generating duplicate rows or primary key collisions.
* **CLI Interface**:
  ```bash
  python -m packages.database.ingestion --input-dir data/generated --batch-size 5000
  ```

---

## 5. Query Architecture & Database-Side Analytics

### 5.1 Hierarchical Trace Tree Reconstruction
Spans maintain explicit lineage via `parent_event_id`. The repository reconstructs the complete directed acyclic graph (DAG) in linear time $\mathcal{O}(N)$ without expensive recursive SQL CTEs:

```python
# TraceEventRepository.get_trace_tree(execution_id)
1. Fetch all spans for execution_id ordered by timestamp ASC
2. Build span dictionary and adjacency map: parent_id -> [child_ids]
3. Identify root span (parent_event_id IS NULL)
4. Recursively assemble nested JSON tree structure
```

### 5.2 Database-Side Latency Percentiles
Instead of transferring all raw latency measurements to Python memory, the repository executes native SQL percentile functions on PostgreSQL/TimescaleDB:

```sql
SELECT
    COUNT(event_id) AS event_count,
    AVG(latency_ms) AS mean,
    MIN(latency_ms) AS min,
    MAX(latency_ms) AS max,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) AS p90,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
FROM trace_events
WHERE service = :service
  AND latency_ms > 0.0
  AND timestamp >= :start_time
  AND timestamp <= :end_time;
```

### 5.3 System-Wide Telemetry Summary (Single Database Pass)
Rather than executing $N$ sequential round-trip queries per service, `get_service_telemetry_summary()` computes system-wide call volumes, failures, timeouts, retries, and latency distributions in a single `GROUP BY service` database pass:

```sql
SELECT
    service,
    COUNT(event_id) AS total_events,
    SUM(CASE WHEN status = 'FAILURE' THEN 1 ELSE 0 END) AS failures,
    SUM(CASE WHEN status = 'TIMEOUT' THEN 1 ELSE 0 END) AS timeouts,
    SUM(CASE WHEN status = 'RETRY' THEN 1 ELSE 0 END) AS retries,
    COUNT(CASE WHEN latency_ms > 0.0 THEN 1 ELSE NULL END) AS lat_count,
    AVG(CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS mean_lat,
    MIN(CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS min_lat,
    MAX(CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS max_lat,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS p50,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS p90,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY CASE WHEN latency_ms > 0.0 THEN latency_ms ELSE NULL END) AS p99
FROM trace_events
WHERE (:start_time IS NULL OR timestamp >= :start_time)
  AND (:end_time IS NULL OR timestamp <= :end_time)
GROUP BY service
ORDER BY service ASC;
```

---

## 6. REST API Query Endpoints

All endpoints are versioned under `/api/v1/`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/traces` | List execution traces with status, incident, and time filters |
| `GET` | `/api/v1/traces/{trace_id}` | Retrieve execution trace summary |
| `GET` | `/api/v1/traces/{trace_id}/events` | Chronological span sequence for a trace |
| `GET` | `/api/v1/traces/{trace_id}/tree` | Reconstructed parent-child DAG trace tree |
| `GET` | `/api/v1/services` | List registered microservices and baselines |
| `GET` | `/api/v1/services/{service}/latency` | Service P50, P90, P95, P99 latency percentiles |
| `GET` | `/api/v1/services/{service}/health` | Service error rates, retry counts, and timeout counts |
| `GET` | `/api/v1/services/telemetry/summary` | System-wide operational health summary across all services |
| `GET` | `/api/v1/incidents` | List ground-truth incidents in time window |
| `GET` | `/api/v1/incidents/{incident_id}` | Retrieve incident details |
| `GET` | `/api/v1/incidents/{incident_id}/traces` | List workflow executions affected by an incident |

---

## 7. Scaling Roadmap (10K $\rightarrow$ 100K $\rightarrow$ 1M Workflows)

* **10,000 Workflows ($\sim 173\text{K}$ events)**: Ingests in $\sim 20$ seconds. Direct indexed lookups take $<1\text{ms}$.
* **100,000 Workflows ($\sim 1.7\text{M}$ events)**: Ingests in $\sim 3$ minutes. TimescaleDB hypertable chunking ensures continuous high ingestion throughput without index fragmentation.
* **1,000,000 Workflows ($\sim 17.4\text{M}$ events)**:
  * Ingestion strategy: Use asyncpg `copy_records_to_table` (`COPY FROM STDIN`) for $>50,000$ events/sec ingestion throughput.
  * Enable TimescaleDB native compression on chunks older than 7 days.
  * Use continuous aggregates (`CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)`) for pre-computed 1-minute and 5-minute latency rollups.
