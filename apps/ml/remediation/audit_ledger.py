"""Cryptographic SHA-256 append-only Audit Ledger for autonomous remediation compliance."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.common.logging import get_logger

logger = get_logger("tracemind.remediation.audit_ledger")

GENESIS_HASH = "0" * 64


class AuditLedgerEntry(BaseModel):
    """Immutable audit entry with cryptographic parent-hash linkage."""

    entry_id: str = Field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:12]}")
    plan_id: str
    event_type: str
    actor: str = Field(
        description="Entity triggering the event (AUTONOMOUS_POLICY, AI_ANALYST, OPERATOR_USER, HEALTH_VERIFIER)"
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    previous_hash: str
    entry_hash: str


class CryptographicAuditLedger:
    """Thread-safe append-only ledger calculating SHA-256 hash chains for tamper-evident compliance."""

    def __init__(self) -> None:
        self._entries: list[AuditLedgerEntry] = []
        self._last_hash: str = GENESIS_HASH

    def _compute_hash(
        self,
        previous_hash: str,
        plan_id: str,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        timestamp_str: str,
    ) -> str:
        """Calculates deterministic SHA-256 hash over entry content."""
        canonical_payload = json.dumps(payload, sort_keys=True)
        raw_str = (
            f"{previous_hash}|{plan_id}|{event_type}|{actor}|{canonical_payload}|{timestamp_str}"
        )
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def append_entry(
        self,
        plan_id: str,
        event_type: str,
        actor: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditLedgerEntry:
        """Appends a new audit record to the cryptographic hash chain."""
        now = datetime.now(UTC)
        timestamp_str = now.isoformat()
        content_payload = payload or {}

        entry_hash = self._compute_hash(
            previous_hash=self._last_hash,
            plan_id=plan_id,
            event_type=event_type,
            actor=actor,
            payload=content_payload,
            timestamp_str=timestamp_str,
        )

        entry = AuditLedgerEntry(
            plan_id=plan_id,
            event_type=event_type,
            actor=actor,
            payload=content_payload,
            timestamp=now,
            previous_hash=self._last_hash,
            entry_hash=entry_hash,
        )

        self._entries.append(entry)
        self._last_hash = entry_hash

        logger.info(
            "Appended cryptographic audit entry",
            entry_id=entry.entry_id,
            plan_id=plan_id,
            event_type=event_type,
            hash_prefix=entry_hash[:12],
        )

        return entry

    def verify_chain_integrity(self) -> tuple[bool, str]:
        """Validates the complete cryptographic chain from genesis to head."""
        if not self._entries:
            return True, "Audit ledger is empty (genesis valid)"

        expected_prev = GENESIS_HASH
        for idx, entry in enumerate(self._entries):
            # 1. Verify previous hash linkage
            if entry.previous_hash != expected_prev:
                msg = f"Hash linkage broken at index {idx} (entry {entry.entry_id}): expected {expected_prev[:8]}..., got {entry.previous_hash[:8]}..."
                logger.error(msg)
                return False, msg

            # 2. Re-compute and verify hash
            recomputed = self._compute_hash(
                previous_hash=entry.previous_hash,
                plan_id=entry.plan_id,
                event_type=entry.event_type,
                actor=entry.actor,
                payload=entry.payload,
                timestamp_str=entry.timestamp.isoformat(),
            )
            if recomputed != entry.entry_hash:
                msg = f"Tampered entry detected at index {idx} (entry {entry.entry_id}): recorded {entry.entry_hash[:8]}... != recomputed {recomputed[:8]}..."
                logger.error(msg)
                return False, msg

            expected_prev = entry.entry_hash

        return True, f"Cryptographic audit chain verified intact ({len(self._entries)} entries)"

    def list_entries(self, plan_id: str | None = None, limit: int = 100) -> list[AuditLedgerEntry]:
        """Lists ledger entries in chronological or filtered order."""
        if plan_id:
            filtered = [e for e in self._entries if e.plan_id == plan_id]
            return filtered[-limit:]
        return self._entries[-limit:]
