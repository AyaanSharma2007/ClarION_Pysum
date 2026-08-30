import re

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (the )?system prompt",
    r"you are now",
    r"act as (an?|the) (?!regulatory)",  # allow legitimate "act as regulatory reviewer" style prompts
    r"reveal (your|the) (system|hidden) prompt",
]

def screen_untrusted_text(text: str) -> dict:
    """Runs before ANY untrusted text is passed into an LLM prompt.
    Never blocks silently — always returns a flagged result for audit."""
    if not text:
        return {"flagged": False, "matched_patterns": [], "action": "proceed"}
        
    hits = [p for p in INJECTION_PATTERNS if re.search(p, text, re.IGNORECASE)]
    return {
        "flagged": len(hits) > 0,
        "matched_patterns": hits,
        "action": "quarantine_for_review" if hits else "proceed",
    }
