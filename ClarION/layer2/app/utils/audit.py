"""
SHA-256 hash-chain utilities for the tamper-evident audit log.

How the chain works
-------------------
Genesis entry:  curr_hash = SHA256("GENESIS" + canonical_json(data))
Each subsequent entry:
  curr_hash = SHA256(prev_entry.curr_hash + canonical_json(data))

If *any* past AuditLog row is modified, every curr_hash after it
stops matching what you'd get by recomputing from the chain —
tampering becomes instantly detectable without a blockchain network.

This is implemented in pure Python (hashlib) and stored in Postgres,
so it survives a database migration without losing chain integrity.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_hash(prev_hash: str | None, data: dict[str, Any]) -> str:
    """
    Compute a SHA-256 hash for one audit log entry.

    Args:
        prev_hash: The curr_hash of the immediately preceding audit entry,
                   or None for the genesis (first) entry.
        data:      Arbitrary dict of action-specific metadata.
                   Must be JSON-serialisable.

    Returns:
        64-character lowercase hex string.
    """
    payload = {
        "prev_hash": prev_hash if prev_hash is not None else "GENESIS",
        "data": data,
    }
    # sort_keys=True + default=str makes serialisation deterministic
    # across Python versions and dict insertion orders.
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(entries: list[dict[str, Any]]) -> bool:
    """
    Verify the integrity of a sequence of audit log entries.

    Args:
        entries: List of dicts with keys: prev_hash, curr_hash, action,
                 actor, metadata, created_at — in ascending created_at order.

    Returns:
        True if every curr_hash matches what compute_hash() would produce
        from the given prev_hash and data; False if any mismatch is found.
    """
    for i, entry in enumerate(entries):
        expected_prev = entries[i - 1]["curr_hash"] if i > 0 else None

        # metadata holds the full audit_data dict that was hashed at write time.
        # Use it directly so the recomputed hash is identical to the stored one.
        data = entry.get("metadata") or {}
        expected_hash = compute_hash(expected_prev, data)

        if entry["curr_hash"] != expected_hash:
            return False

    return True
