"""Causal graph builder and upstream topological back-traversal engine."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from packages.domain.events import EventStatus, TraceEvent


@dataclass
class CausalNode:
    """Node representing a microservice operation or database query in the causal DAG."""

    node_id: str
    service: str
    operation: str
    timestamp: datetime
    latency_ms: float
    status: str
    is_failure: bool
    event_id: str
    parent_event_id: str | None = None
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    shap_attribution: float = 0.0


@dataclass
class CausalGraph:
    """Directed acyclic temporal graph representing call relationships and data flow."""

    nodes: dict[str, CausalNode] = field(default_factory=dict)
    service_nodes: dict[str, list[str]] = field(default_factory=dict)
    adj: dict[str, list[str]] = field(default_factory=dict)
    rev_adj: dict[str, list[str]] = field(default_factory=dict)


class CausalGraphBuilder:
    """Constructs a directed temporal causal graph from trace spans and anomalies."""

    def _normalize_events(
        self, events: Sequence[TraceEvent | dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize heterogenous events to dictionaries."""
        normalized: list[dict[str, Any]] = []
        for e in events:
            if isinstance(e, dict):
                t = e.get("timestamp")
                if isinstance(t, str):
                    t = datetime.fromisoformat(t.replace("Z", "+00:00"))
                normalized.append(
                    {
                        "event_id": str(e.get("event_id", "")),
                        "parent_event_id": e.get("parent_event_id"),
                        "service": str(e.get("service", "unknown")),
                        "operation": str(e.get("operation", "operation")),
                        "status": str(e.get("status", "SUCCESS")),
                        "latency_ms": float(e.get("latency_ms", 0.0)),
                        "timestamp": t or datetime.min.replace(tzinfo=UTC),
                    }
                )
            else:
                normalized.append(
                    {
                        "event_id": str(e.event_id),
                        "parent_event_id": getattr(e, "parent_event_id", None),
                        "service": str(e.service),
                        "operation": str(e.operation),
                        "status": str(e.status.value if hasattr(e.status, "value") else e.status),
                        "latency_ms": float(e.latency_ms),
                        "timestamp": e.timestamp
                        if e.timestamp.tzinfo
                        else e.timestamp.replace(tzinfo=UTC),
                    }
                )
        return sorted(normalized, key=lambda x: x["timestamp"])

    def _map_shap_and_anomalies(
        self,
        shap_contributions: Sequence[dict[str, Any]] | None,
        anomalies: Sequence[dict[str, Any]] | None,
    ) -> tuple[dict[str, float], dict[str, list[dict[str, Any]]]]:
        """Map feature attributions and anomaly records to services."""
        service_shap: dict[str, float] = {}
        if shap_contributions:
            for sc in shap_contributions:
                fname = sc.get("feature_name", "")
                contrib = float(sc.get("contribution", 0.0))
                for svc in (
                    "auth-service",
                    "customer-service",
                    "inventory-service",
                    "pricing-service",
                    "payment-service",
                    "order-service",
                    "notification-service",
                ):
                    if svc.replace("-", "_") in fname or svc in fname:
                        service_shap[svc] = service_shap.get(svc, 0.0) + max(0.0, contrib)

        service_anoms: dict[str, list[dict[str, Any]]] = {}
        if anomalies:
            for anom in anomalies:
                for svc in anom.get("affected_services", []):
                    service_anoms.setdefault(svc, []).append(anom)

        return service_shap, service_anoms

    def build_graph(
        self,
        events: Sequence[TraceEvent | dict[str, Any]],
        anomalies: Sequence[dict[str, Any]] | None = None,
        shap_contributions: Sequence[dict[str, Any]] | None = None,
    ) -> CausalGraph:
        """Build directed causal graph from trace spans."""
        graph = CausalGraph()
        if not events:
            return graph

        sorted_events = self._normalize_events(events)
        service_shap, service_anoms = self._map_shap_and_anomalies(shap_contributions, anomalies)

        for e in sorted_events:
            nid = e["event_id"] or f"{e['service']}:{e['operation']}"
            svc = e["service"]
            is_fail = e["status"] in (
                EventStatus.FAILURE,
                "FAILURE",
                EventStatus.TIMEOUT,
                "TIMEOUT",
            )

            node = CausalNode(
                node_id=nid,
                service=svc,
                operation=e["operation"],
                timestamp=e["timestamp"],
                latency_ms=e["latency_ms"],
                status=e["status"],
                is_failure=is_fail,
                event_id=e["event_id"],
                parent_event_id=e["parent_event_id"],
                anomalies=service_anoms.get(svc, []),
                shap_attribution=service_shap.get(svc, 0.0),
            )
            graph.nodes[nid] = node
            graph.service_nodes.setdefault(svc, []).append(nid)

        for i in range(len(sorted_events) - 1):
            curr_id = (
                sorted_events[i]["event_id"]
                or f"{sorted_events[i]['service']}:{sorted_events[i]['operation']}"
            )
            next_id = (
                sorted_events[i + 1]["event_id"]
                or f"{sorted_events[i + 1]['service']}:{sorted_events[i + 1]['operation']}"
            )
            graph.adj.setdefault(curr_id, []).append(next_id)
            graph.rev_adj.setdefault(next_id, []).append(curr_id)

        return graph


class CausalGraphTraverser:
    """Traverses causal graphs backwards from symptom nodes to isolate root culprit services."""

    def find_symptom_nodes(self, graph: CausalGraph) -> list[CausalNode]:
        """Identify initial failure or severe degradation symptom nodes."""
        symptoms: list[CausalNode] = []
        for node in graph.nodes.values():
            if (
                node.is_failure
                or node.latency_ms >= 1000.0
                or any(a.get("score", 0.0) >= 0.70 for a in node.anomalies)
            ):
                symptoms.append(node)

        # If no severe failure found, pick the highest latency node
        if not symptoms and graph.nodes:
            highest = max(graph.nodes.values(), key=lambda n: n.latency_ms)
            symptoms.append(highest)

        return symptoms

    def backward_traverse(
        self, graph: CausalGraph, symptom_nodes: list[CausalNode]
    ) -> list[list[str]]:
        """Traverse backwards from symptoms along caller paths to find causal propagation chains."""
        if not symptom_nodes:
            return []

        paths: list[list[str]] = []

        for symp in symptom_nodes:
            visited: set[str] = set()
            chain: list[str] = []

            curr_node_id: str | None = symp.node_id
            while curr_node_id and curr_node_id not in visited:
                visited.add(curr_node_id)
                node = graph.nodes.get(curr_node_id)
                if node:
                    chain.append(node.service)

                # Get upstream callers
                callers = graph.rev_adj.get(curr_node_id, [])
                curr_node_id = callers[0] if callers else None

            # Reverse to form root -> symptom order
            chain.reverse()
            # Deduplicate adjacent services in path
            dedup_chain: list[str] = []
            for s in chain:
                if not dedup_chain or dedup_chain[-1] != s:
                    dedup_chain.append(s)

            if dedup_chain:
                paths.append(dedup_chain)

        return paths
