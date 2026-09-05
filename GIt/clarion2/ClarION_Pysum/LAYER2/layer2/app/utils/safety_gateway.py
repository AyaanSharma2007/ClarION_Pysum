"""
Safety Gateway — Adversarial Input Defense (Bible §6.2).

All text originating outside Clarion's own generated output — extracted
RFI PDF text, user search queries, anything pulled from CTIS documents —
is **untrusted content**, never instructions.  This is enforced
deterministically, never by asking an LLM to police itself (mirrors
OWASP LLM01/prompt-injection guidance).

Single implementation, two call sites:
  1. Ingestion  (routers/ingest.py)  — screens extracted RFI text
  2. Search     (routers/search.py)  — screens user query text

If `screen_untrusted_text` flags content, that content is routed to a
human review queue instead of the LLM pipeline, and an audit event is
written (event_type: safety_gateway_flag).  This never silently drops
content and never silently proceeds — both failure directions are logged.
"""
from __future__ import annotations

import re


# ── Injection patterns (Bible §6.2) ─────────────────────────────────────────
# These patterns are matched case-insensitively against any untrusted text
# before it is passed into an LLM prompt or embedding pipeline.

INJECTION_PATTERNS: list[str] = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (the )?system prompt",
    r"you are now",
    r"act as (an?|the) (?!regulatory)",  # allow "act as regulatory reviewer"
    r"reveal (your|the) (system|hidden) prompt",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def screen_untrusted_text(text: str) -> dict:
    """
    Run before ANY untrusted text is passed into an LLM prompt.
    Never blocks silently — always returns a flagged result for audit.

    Args:
        text: The untrusted text to screen.

    Returns:
        {
            "flagged": bool,
            "matched_patterns": [str, ...],  # which patterns matched
            "action": "quarantine_for_review" | "proceed",
        }
    """
    hits = [p.pattern for p in _compiled if p.search(text)]
    return {
        "flagged": len(hits) > 0,
        "matched_patterns": hits,
        "action": "quarantine_for_review" if hits else "proceed",
    }
