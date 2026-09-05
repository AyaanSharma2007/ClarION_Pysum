"""
Policy Engine client — Bible §6.1.

Posts payloads to the OPA sidecar (localhost:8181) for declarative rule
evaluation before every write to rfi/response/consideration tables.

Enforcement model (from user direction, not a dev-mode toggle):
  - All mounted rules are fail-closed, always, everywhere.
  - Rules actively being iterated on are excluded by ID via
    DISABLED_RULES config (with a startup warning).
  - Per-case human overrides go through the policy_override mechanism
    (Bible §14.1), not a systemic weakening of enforcement.

If OPA is unreachable, the write is REJECTED (not silently allowed).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from LAYER2.layer2.app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PolicyResult:
    """Result of an OPA policy evaluation."""
    allowed: bool
    violations: list[dict] = field(default_factory=list)


class PolicyEngine:
    """
    Async client for the OPA sidecar.

    Usage:
        result = await policy_engine.check_compliance(payload)
        if not result.allowed:
            raise HTTPException(403, detail=result.violations)
    """

    def __init__(self) -> None:
        self._base_url = settings.OPA_URL
        self._disabled_rules: set[str] = set(settings.DISABLED_RULES)
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Log disabled rules at startup — visible warning every boot."""
        if self._disabled_rules:
            logger.warning(
                "⚠️  Policy Engine: DISABLED_RULES is non-empty: %s  "
                "These rules will NOT be enforced. Remove them before demo.",
                self._disabled_rules,
            )
        self._client = httpx.AsyncClient(timeout=5.0)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def check_compliance(self, payload: dict[str, Any]) -> PolicyResult:
        """
        Evaluate compliance rules (RFI-SLA-001/002, FIELDS-001).

        Args:
            payload: Dict with 'rfis' and/or 'considerations' lists.

        Returns:
            PolicyResult with allowed=True if no active violations.
        """
        return await self._evaluate("clarion/compliance/violation", payload)

    async def check_governance(self, payload: dict[str, Any]) -> PolicyResult:
        """
        Evaluate governance rules (GATE-001, ACCESS-001).

        Args:
            payload: Dict with 'responses' and/or 'rfis' + 'request' context.

        Returns:
            PolicyResult with allowed=True if no active denials.
        """
        return await self._evaluate("clarion/governance/deny", payload)

    async def _evaluate(
        self, rule_path: str, payload: dict[str, Any]
    ) -> PolicyResult:
        """
        Post payload to OPA and filter out disabled rules.

        If OPA is unreachable, returns NOT allowed (fail-closed).
        """
        url = f"{self._base_url}/v1/data/{rule_path}"
        try:
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=5.0)
            resp = await self._client.post(url, json={"input": payload})
            resp.raise_for_status()
            result = resp.json().get("result", [])
        except httpx.HTTPError as exc:
            logger.error("OPA unreachable at %s: %s — REJECTING write (fail-closed).", url, exc)
            return PolicyResult(
                allowed=False,
                violations=[{"rule": "OPA_UNREACHABLE", "detail": str(exc)}],
            )

        # Filter out disabled rules (explicit, named, logged exclusion)
        active_violations = [
            v for v in result
            if v.get("rule") not in self._disabled_rules
        ]

        return PolicyResult(
            allowed=len(active_violations) == 0,
            violations=active_violations,
        )


# Module-level singleton
policy_engine = PolicyEngine()
