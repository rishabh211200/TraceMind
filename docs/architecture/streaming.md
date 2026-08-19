# TraceMind — Event Streaming Architecture & Kafka Ingestion Engine

> **Module E — Asynchronous Event Streaming & Distributed Ingestion Pipeline**  
> **Milestone 5 Reference Architecture**

---

## 1. Overview & System Philosophy

To support enterprise workloads, decoupled ingestion, and scalable feature extraction for ML without placing synchronous database bottlenecks on discrete-event simulators or API handlers, **Milestone 5** introduces an asynchronous event streaming architecture built on **Apache Kafka** in **KRaft** mode.

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            TraceMind Streaming Architecture                       │
└──────────────────────────────────────────────────────────────────────────────────┘

   ┌───────────────────────────┐
   │ TraceSim / API Generator  │
   │ (StreamingTraceSimulator) │
   └─────────────┬─────────────┘
                 │
                 │ publish_event() / publish_batch()
                 │ Key = execution_id (Partition Affinity)
                 ▼
   ┌───────────────────────────┐
   │ AsyncTraceEventProducer   │
   │ (KafkaTraceEventProducer) │
   └─────────────┬─────────────┘
                 │
                 ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                  Apache Kafka Event Broker (KRaft Mode)                │
   │                                                                        │
   │   Topic: tracemind.events.raw (3 Partitions)                           │
   │   ┌───────────────────────┬───────────────────────┬────────────────┐   │
   │   │      Partition 0      │      Partition 1      │  Partition 2   │   │
   │   │  (Hash: execution_id) │  (Hash: execution_id) │                │   │
   │   └───────────────────────┴───────────────────────┴────────────────┘   │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       │ Consumer Group: tracemind-ingestor
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                 Streaming Ingestion Worker (apps/worker)               │
   │                                                                        │
   │   ┌────────────────────────────────┐  ┌────────────────────────────┐   │
   │   │    KafkaTraceEventConsumer     │  │    Micro-Batch Buffer      │   │
   │   │  (Manual Offset Management)    │──►  (1,000 events / 50ms)     │   │
   │   └────────────────────────────────┘  └─────────────┬──────────────┘   │
   └─────────────────────────────────────────────────────┼──────────────────┘
                                                         │
                                          Bulk Chunked insert() + commit
                                                         │
                                                         ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                   TimescaleDB Composite Hypertable                     │
   │                     table: trace_events (Pg16)                         │
   └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Canonical Event Contract & Serialization

The streaming pipeline strictly adopts the canonical `TraceEvent` domain model (`packages/domain/events.py`) as the contract across producers and consumers:

```python
class TraceEvent(BaseModel):
    event_id: str
    execution_id: str
    workflow_id: str
    timestamp: datetime
    service: str
    operation: str
    event_type: EventType
    status: EventStatus
    latency_ms: float
    parent_event_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 2.1 Serialization Precision
* **Serializer**: `JsonTraceEventSerializer` (`packages/events/serializers.py`).
* **Timestamp Handling**: Serializes datetimes to ISO 8601 with microsecond precision and explicit `UTC` timezone offsets.
* **Validation**: On consumption, payloads are deserialized directly into validated `TraceEvent` instances via `TraceEvent.model_validate_json()`.

---

## 3. Partitioning & In-Order Causal Delivery

In distributed tracing, preserving the parent-child causal hierarchy of spans within an execution run is critical for trace graph DAG reconstruction.

* **Partition Key**: All events are produced with `key = event.execution_id.encode('utf-8')`.
* **Ordering Guarantee**: Kafka's default murmur2 hashing ensures all events sharing the same `execution_id` are consistently routed to the **same partition**.
* **Result**: Spans within any trace are consumed in exact FIFO causal sequence, preventing child spans from being processed before their execution context is created.

---

## 4. Micro-Batching & Streaming Ingestion Worker

The background ingestion worker (`apps/worker/stream_ingestor.py`) consumes from `tracemind.events.raw` using consumer group `tracemind-ingestor`.

### 4.1 Micro-Batch Flushing Triggers
The worker accumulates records into an in-memory buffer and flushes to the database when either of two triggers fires:
1. **Size-Based Trigger**: Buffer reaches `batch_size` (default: $1,000$ events).
2. **Time-Based Trigger**: Elapsed time since last flush exceeds `flush_interval_ms` (default: $50\text{ms}$).

### 4.2 Offset Commit Invariant
To prevent data loss during container crashes or rebalances:
$$\text{Kafka Offset Commit} \implies \text{Database Persistence Succeeded}$$
The consumer's `enable_auto_commit` is disabled (`enable_auto_commit=False`). The worker executes a multi-row SQLAlchemy `insert(TraceEventModel)` and commits the database transaction **before** invoking `consumer.commit()`.

### 4.3 Idempotency Strategy
If the worker restarts before committing Kafka offsets, unacknowledged spans will be re-delivered (at-least-once semantics). Because `trace_events` is backed by a composite primary key `(timestamp, event_id)`, collisions trigger a safe `merge()` fallback, guaranteeing idempotent persistence without duplicates or errors.

---

## 5. Dual-Mode Event Bus & Test Hermeticity

To ensure that unit tests, integration tests, and CI/CD pipelines can run in offline or isolated container environments without requiring an active external Kafka broker, TraceMind provides a dual-mode event bus architecture:

| Component | Production / Docker Compose Mode | Testing / CI Hermetic Mode |
| :--- | :--- | :--- |
| **Producer** | `KafkaTraceEventProducer` (`aiokafka.AIOKafkaProducer`) | `InMemoryTraceEventProducer` (`asyncio.Queue`) |
| **Consumer** | `KafkaTraceEventConsumer` (`aiokafka.AIOKafkaConsumer`) | `InMemoryTraceEventConsumer` (`asyncio.Queue`) |
| **Broker** | Apache Kafka (KRaft mode on `kafka:9092`) | `InMemoryEventBus` (in-process channel) |

Factory functions `create_producer()` and `create_consumer()` in `packages/events/bus.py` instantiate the appropriate implementation based on configuration or test parameters.

---

## 6. Performance Benchmarks

The streaming pipeline was benchmarked using `benchmarks/benchmark_kafka_streaming.py` across $25,000$ synthetic distributed trace spans:

```text
================================================================================
                TraceMind Milestone 5 Streaming Pipeline Benchmark             
================================================================================
 Total Benchmark Events Processed   : 25,000 spans
 Micro-Batch Buffer Limit           : 1,000 events / batch
--------------------------------------------------------------------------------
 1. Producer Stream Ingestion Rate  : 287,472 events/sec (0.087s)
 2. Consumer & DB Persistence Rate  : 27,563 events/sec (0.907s)
 3. End-to-End Pipeline Throughput  : 25,151 events/sec (0.994s)
 4. Simulator Live Stream Rate      : 83,820 events/sec (3,835 spans in 0.046s)
--------------------------------------------------------------------------------
 Micro-Batch Flush Latencies (per 1,000-event batch):
   • P50 Flush Latency              : 24.00 ms
   • P95 Flush Latency              : 49.02 ms
   • P99 Flush Latency              : 73.81 ms
   • Mean Flush Latency             : 27.67 ms
================================================================================
 Target Throughput Criteria (>5,000 events/sec) : [PASSED] (5.5x margin)
================================================================================
```

---

## 7. Docker Infrastructure (KRaft Mode)

In `docker-compose.yml`, Kafka is deployed in **KRaft** mode (Kafka Raft Metadata mode), eliminating the legacy Zookeeper dependency:

```yaml
  kafka:
    image: apache/kafka:3.7.0
    container_name: tracemind-kafka
    restart: unless-stopped
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_NUM_PARTITIONS: 3
    volumes:
      - kafka_data:/var/lib/kafka/data

  worker:
    build:
      context: .
      dockerfile: infrastructure/docker/Dockerfile.api
    container_name: tracemind-worker
    command: ["python", "-m", "apps.worker.stream_ingestor"]
    environment:
      DATABASE_URL: postgresql+asyncpg://tracemind:tracemind_secret@postgres:5432/tracemind_db
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
```
