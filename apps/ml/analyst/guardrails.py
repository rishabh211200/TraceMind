"""Safety guardrails and citation-level grounding verification engine for AI Analyst."""

import re
from typing import Any

from apps.ml.analyst.models import Citation, GroundingReport, ToolResult
from packages.common.logging import get_logger

logger = get_logger("tracemind.analyst.guardrails")

MAX_TOOL_CALLS_PER_TURN = 5
KNOWN_SERVICES = {
    "api-gateway",
    "auth-service",
    "customer-service",
    "customer-db",
    "customer-cache",
    "inventory-service",
    "inventory-db",
    "inventory-cache",
    "pricing-service",
    "payment-service",
    "payment-gateway",
    "order-service",
    "notification-service",
}


class SafetyLimitExceededError(Exception):
    """Raised when an agent turn exceeds hard safety limits."""


class SafetyGuardrail:
    """Enforces strict agent safety limits (max calls, read-only enforcement)."""

    def __init__(self, max_calls_per_turn: int = MAX_TOOL_CALLS_PER_TURN) -> None:
        self.max_calls_per_turn = max_calls_per_turn

    def validate_tool_call_count(self, current_count: int) -> None:
        """Ensure turn does not exceed maximum allowable tool invocations."""
        if current_count >= self.max_calls_per_turn:
            raise SafetyLimitExceededError(
                f"Turn exceeded maximum safety limit of {self.max_calls_per_turn} tool calls."
            )

    def validate_read_only(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Verify that the tool is strictly read-only and contains no mutating operations."""
        prohibited_keywords = [
            "delete",
            "drop",
            "truncate",
            "insert",
            "update",
            "inject",
            "mutate",
            "restart",
        ]
        for key, val in arguments.items():
            str_val = str(val).lower()
            if any(kw in str_val for kw in prohibited_keywords):
                logger.warning("mutating_action_blocked", tool=tool_name, argument=key)
                return False
        return True


class CitationGroundingEngine:
    """Verifies factual claims in LLM output against tool outputs and injects structured citations."""

    def __init__(self, known_services: set[str] | None = None) -> None:
        self.known_services = known_services or KNOWN_SERVICES

    def _verify_services(
        self,
        content: str,
        evidence_store: list[tuple[str, str, str, Any]],
        citations: list[Citation],
        unverified_claims: list[str],
        start_counter: int,
    ) -> tuple[int, int]:
        """Verify mentioned microservice names against evidence store."""
        verified = 0
        counter = start_counter
        for svc in self.known_services:
            if svc in content.lower():
                matching = next(
                    (
                        e
                        for e in evidence_store
                        if svc in str(e[3]).lower() or svc in str(e[1]).lower()
                    ),
                    None,
                )
                if matching:
                    verified += 1
                    citations.append(
                        Citation(
                            citation_id=counter,
                            tool_name=matching[0],
                            entity_id=matching[1],
                            field_name=matching[2],
                            verified_value=matching[3],
                            snippet=f"Verified microservice: '{svc}'",
                        )
                    )
                    counter += 1
                else:
                    unverified_claims.append(f"Unverified service: '{svc}'")
        return verified, counter

    def _verify_metrics(
        self,
        content: str,
        evidence_store: list[tuple[str, str, str, Any]],
        citations: list[Citation],
        unverified_claims: list[str],
        start_counter: int,
    ) -> tuple[int, int]:
        """Verify mentioned numeric latencies, costs, and percentages."""
        verified = 0
        counter = start_counter
        numeric_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*(?:ms|%|u\b|units\b)", content, re.IGNORECASE
        )
        for num_str in numeric_matches:
            try:
                val = float(num_str)
                matching = next(
                    (
                        e
                        for e in evidence_store
                        if isinstance(e[3], (int, float)) and abs(float(e[3]) - val) < 0.5
                    ),
                    None,
                )
                if matching:
                    verified += 1
                    citations.append(
                        Citation(
                            citation_id=counter,
                            tool_name=matching[0],
                            entity_id=matching[1],
                            field_name=matching[2],
                            verified_value=matching[3],
                            snippet=f"Verified metric: {val} in {matching[0]}",
                        )
                    )
                    counter += 1
                else:
                    unverified_claims.append(f"Unverified metric: {val}")
            except ValueError:
                continue
        return verified, counter

    def _verify_culprits_and_paths(
        self,
        content: str,
        tool_results: list[ToolResult],
        citations: list[Citation],
        start_counter: int,
    ) -> tuple[int, int]:
        """Verify primary culprit attribution and recommended optimal paths."""
        verified = 0
        counter = start_counter
        for tr in tool_results:
            if tr.name == "get_root_cause_diagnosis" and isinstance(tr.result, dict):
                culprit = tr.result.get("primary_culprit")
                if culprit and culprit in content:
                    verified += 1
                    citations.append(
                        Citation(
                            citation_id=counter,
                            tool_name=tr.name,
                            entity_id=tr.result.get("execution_id", "execution"),
                            field_name="primary_culprit",
                            verified_value=culprit,
                            snippet=f"Root culprit: {culprit} ({tr.result.get('fault_pattern')})",
                        )
                    )
                    counter += 1

            if tr.name == "get_workflow_optimization" and isinstance(tr.result, dict):
                rec_path = tr.result.get("recommended_path_id")
                if rec_path and rec_path in content:
                    verified += 1
                    citations.append(
                        Citation(
                            citation_id=counter,
                            tool_name=tr.name,
                            entity_id=tr.result.get("workflow_definition_id", "order_fulfillment"),
                            field_name="recommended_path_id",
                            verified_value=rec_path,
                            snippet=f"Recommended optimal path: {rec_path}",
                        )
                    )
                    counter += 1
        return verified, counter

    def verify_and_cite(
        self,
        content: str,
        tool_results: list[ToolResult],
    ) -> tuple[str, GroundingReport]:
        """Cross-reference claims in content against tool results and generate grounding report."""
        if not tool_results:
            mentioned = [s for s in self.known_services if s in content.lower()]
            score = 0.85 if mentioned else 1.0
            return content, GroundingReport(
                is_grounded=True,
                grounding_score=score,
                total_claims=len(mentioned),
                verified_claims=len(mentioned),
                unverified_claims=[],
                citations=[],
            )

        citations: list[Citation] = []
        unverified_claims: list[str] = []
        evidence_store: list[tuple[str, str, str, Any]] = []

        for tr in tool_results:
            if not tr.is_error:
                self._extract_evidence(tr.name, tr.result, evidence_store)

        v_svc, counter = self._verify_services(
            content, evidence_store, citations, unverified_claims, 1
        )
        v_met, counter = self._verify_metrics(
            content, evidence_store, citations, unverified_claims, counter
        )
        v_cul, counter = self._verify_culprits_and_paths(content, tool_results, citations, counter)

        verified_claims = v_svc + v_met + v_cul
        total_claims = verified_claims + len(unverified_claims)
        grounding_score = round(verified_claims / total_claims, 3) if total_claims > 0 else 1.0

        report = GroundingReport(
            is_grounded=grounding_score >= 0.80,
            grounding_score=grounding_score,
            total_claims=total_claims,
            verified_claims=verified_claims,
            unverified_claims=unverified_claims,
            citations=citations,
        )

        return content, report

    def _extract_evidence(
        self,
        tool_name: str,
        data: Any,
        store: list[tuple[str, str, str, Any]],
        prefix: str = "",
        entity_id: str = "root",
    ) -> None:
        """Recursively extract atomic values into evidence store."""
        if isinstance(data, dict):
            curr_entity = str(
                data.get("execution_id") or data.get("name") or data.get("workflow_id") or entity_id
            )
            for k, v in data.items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (int, float, str, bool)):
                    store.append((tool_name, curr_entity, new_prefix, v))
                    if isinstance(v, float) and 0.0 <= v <= 1.0:
                        store.append(
                            (tool_name, curr_entity, f"{new_prefix}_pct", round(v * 100.0, 1))
                        )
                elif isinstance(v, (dict, list)):
                    self._extract_evidence(tool_name, v, store, new_prefix, curr_entity)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                self._extract_evidence(tool_name, item, store, f"{prefix}[{idx}]", entity_id)
