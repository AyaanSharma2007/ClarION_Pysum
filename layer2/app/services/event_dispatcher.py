"""
Cross-Layer Event Dispatcher — Bible §6.4, §10, §14.1.

Centralises all workflow state-change logic into a single service so
that every transition:
  1. Validates the transition against the state machine (§6.4)
  2. Enforces GATE-001 before 'submitted' (§6.4)
  3. Writes a hash-chained AuditLog entry (§10)
  4. Syncs rfi.status with the workflow stage (§7)
  5. Fires any cross-layer side-effects (SLA recalc, etc.)

This replaces ad-hoc stage-change logic scattered across routers with
a single, auditable, testable path.

Design note: this is **not** an event bus or a message queue.  It is a
synchronous, in-process orchestration layer called by the API routers.
Every side-effect happens within the same database transaction — if any
step fails, the whole transition rolls back.  Async event buses are a
Layer 8+ concern and are out of scope for this implementation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.audit import AuditLog, PolicyOverride, WorkflowState
from app.models.rfi import RFI
from app.schemas.rfi import VALID_STAGES
from app.utils.audit import compute_hash

logger = logging.getLogger(__name__)


# ── State machine transitions (Bible §6.4) ────────────────────────────────────
# Maps each stage to the set of stages it can transition TO.
# Any transition not in this map is rejected — no implicit fallbacks.

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "received":            {"ready_for_response"},
    "ready_for_response":  {"awaiting_response"},
    "awaiting_response":   {"drafting"},
    "drafting":            {"pending_approval"},
    "pending_approval":    {"approved", "drafting"},   # reviewer can send back
    "approved":            {"submitted"},
    "submitted":           set(),                       # terminal
}


class EventDispatchError(Exception):
    """Raised when a state transition is invalid or blocked by policy."""


class EventDispatcher:
    """
    Synchronous, in-process workflow orchestrator.

    Usage from a router:
        dispatcher = EventDispatcher()
        result = await dispatcher.advance_stage(db, rfi_uuid, target, actor, notes)
    """

    # ── Core: stage advancement ────────────────────────────────────────────

    async def advance_stage(
        self,
        db: AsyncSession,
        rfi_uuid: str,
        target_stage: str,
        actor: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Advance an RFI through the state machine.

        Raises EventDispatchError on invalid transitions or policy blocks.
        All changes happen within the caller's transaction — no implicit
        commits.

        Returns:
            Dict with transition details for the API response.
        """
        import uuid as _uuid

        # 1. Validate target stage is known
        if target_stage not in VALID_STAGES:
            raise EventDispatchError(
                f"Invalid stage {target_stage!r}. Valid stages: {VALID_STAGES}"
            )

        # 2. Load the RFI with relationships
        result = await db.execute(
            select(RFI)
            .where(RFI.id == _uuid.UUID(str(rfi_uuid)))
            .options(
                selectinload(RFI.workflow_state),
                selectinload(RFI.audit_logs),
            )
        )
        rfi = result.scalar_one_or_none()
        if rfi is None:
            raise EventDispatchError(f"RFI {rfi_uuid} not found.")

        if rfi.workflow_state is None:
            raise EventDispatchError(f"RFI {rfi_uuid} has no workflow state.")

        old_stage = rfi.workflow_state.current_stage

        # 3. Validate transition against state machine
        allowed = ALLOWED_TRANSITIONS.get(old_stage, set())
        if target_stage not in allowed:
            raise EventDispatchError(
                f"Invalid transition: {old_stage!r} → {target_stage!r}. "
                f"Allowed from {old_stage!r}: {sorted(allowed) or '(terminal state)'}."
            )

        # 4. GATE-001 enforcement (Bible §6.4)
        if target_stage == "submitted":
            if not rfi.workflow_state.approved_by:
                raise EventDispatchError(
                    "GATE-001 violation: cannot transition to 'submitted' without "
                    "human approval. Call POST /considerations/{id}/responses/{rid}/approve first."
                )

        # 5. Update WorkflowState
        now = datetime.now(tz=timezone.utc)
        rfi.workflow_state.current_stage = target_stage
        rfi.workflow_state.stage_entered_at = now
        rfi.workflow_state.sla_due_at = now + timedelta(hours=settings.SLA_HOURS_DEFAULT)

        # 6. Sync rfi.status (Bible §7 status enum)
        rfi.status = target_stage

        # 7. Hash-chained audit log (§10)
        last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
        audit_data = {
            "action": "stage_advanced",
            "actor": actor,
            "metadata": {
                "from_stage": old_stage,
                "to_stage": target_stage,
                "notes": notes,
                "dispatched_by": "EventDispatcher",
            },
            "created_at": now.isoformat(),
        }
        curr_hash = compute_hash(last_hash, audit_data)
        audit = AuditLog(
            rfi_id=rfi.id,
            action="stage_advanced",
            actor=actor,
            prev_hash=last_hash,
            curr_hash=curr_hash,
            metadata_=audit_data,
        )
        db.add(audit)

        # 8. Fire side-effects
        await self._on_stage_changed(db, rfi, old_stage, target_stage, actor, now)

        await db.flush()

        logger.info(
            "EventDispatcher: %s transitioned %s → %s (actor=%s)",
            rfi.rfi_id, old_stage, target_stage, actor,
        )

        return {
            "rfi_id": rfi.rfi_id,
            "rfi_uuid": str(rfi.id),
            "from_stage": old_stage,
            "to_stage": target_stage,
            "actor": actor,
            "transitioned_at": now.isoformat(),
        }

    # ── Side-effect hooks ──────────────────────────────────────────────────

    async def _on_stage_changed(
        self,
        db: AsyncSession,
        rfi: RFI,
        from_stage: str,
        to_stage: str,
        actor: str,
        now: datetime,
    ) -> None:
        """
        Fire cross-layer side-effects after a stage transition.

        This is the extension point for future integrations (Layer 4 risk
        prediction trigger, Layer 7 notification push, etc.).
        """
        # Side-effect: entering 'pending_approval' → log a review-requested event
        if to_stage == "pending_approval":
            logger.info(
                "Side-effect: RFI %s entered pending_approval — review requested.",
                rfi.rfi_id,
            )

        # Side-effect: entering 'submitted' → mark terminal, clear SLA
        if to_stage == "submitted":
            rfi.workflow_state.sla_due_at = None  # no SLA on terminal state
            logger.info(
                "Side-effect: RFI %s submitted — SLA cleared, workflow terminal.",
                rfi.rfi_id,
            )

    # ── Policy override recording (Bible §14.1) ───────────────────────────

    async def record_policy_override(
        self,
        db: AsyncSession,
        policy_rule: str,
        record_id: str,
        record_type: str,
        overridden_by: str,
        justification: str,
        rfi_uuid: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Record a justified policy override and append a hash-chained
        audit event.

        The override itself is a permanent row in policy_override.  The
        audit log entry ensures it appears in the tamper-evident chain
        alongside every other state change.

        Args:
            db: Async database session.
            policy_rule: Rule being overridden (e.g. 'RFI-SLA-001').
            record_id: The rfi_id or consideration_id_str being exempted.
            record_type: 'rfi' or 'consideration'.
            overridden_by: Human who authorised the override.
            justification: Required free-text justification (never empty).
            rfi_uuid: Optional parent RFI UUID for chain linkage.

        Returns:
            Dict with override details for the API response.
        """
        import uuid as _uuid

        now = datetime.now(tz=timezone.utc)

        # Parse the optional RFI UUID
        parsed_rfi_uuid = _uuid.UUID(rfi_uuid) if rfi_uuid else None

        # 1. Insert the override row
        override = PolicyOverride(
            policy_rule=policy_rule,
            record_id=record_id,
            record_type=record_type,
            overridden_by=overridden_by,
            justification=justification,
            overridden_at=now,
            rfi_uuid=parsed_rfi_uuid,
        )
        db.add(override)

        # 2. If linked to an RFI, append a hash-chained audit log entry
        if parsed_rfi_uuid:
            result = await db.execute(
                select(RFI)
                .where(RFI.id == parsed_rfi_uuid)
                .options(selectinload(RFI.audit_logs))
            )
            rfi = result.scalar_one_or_none()

            if rfi:
                last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
                audit_data = {
                    "action": "policy_override",
                    "actor": overridden_by,
                    "metadata": {
                        "policy_rule": policy_rule,
                        "record_id": record_id,
                        "record_type": record_type,
                        "justification": justification,
                    },
                    "created_at": now.isoformat(),
                }
                curr_hash = compute_hash(last_hash, audit_data)
                audit = AuditLog(
                    rfi_id=rfi.id,
                    action="policy_override",
                    actor=overridden_by,
                    prev_hash=last_hash,
                    curr_hash=curr_hash,
                    metadata_=audit_data,
                )
                db.add(audit)

        await db.flush()

        logger.info(
            "PolicyOverride recorded: rule=%s record=%s by=%s justification='%s'",
            policy_rule, record_id, overridden_by, justification[:80],
        )

        return {
            "id": str(override.id),
            "policy_rule": policy_rule,
            "record_id": record_id,
            "record_type": record_type,
            "overridden_by": overridden_by,
            "justification": justification,
            "overridden_at": now.isoformat(),
        }

    # ── Query helpers ──────────────────────────────────────────────────────

    async def get_overrides_for_record(
        self,
        db: AsyncSession,
        record_id: str,
    ) -> list[dict[str, Any]]:
        """Return all policy overrides for a given record_id."""
        result = await db.execute(
            select(PolicyOverride)
            .where(PolicyOverride.record_id == record_id)
            .order_by(PolicyOverride.overridden_at)
        )
        overrides = result.scalars().all()
        return [
            {
                "id": str(o.id),
                "policy_rule": o.policy_rule,
                "record_id": o.record_id,
                "record_type": o.record_type,
                "overridden_by": o.overridden_by,
                "justification": o.justification,
                "overridden_at": o.overridden_at.isoformat(),
            }
            for o in overrides
        ]


# Module-level singleton
event_dispatcher = EventDispatcher()
