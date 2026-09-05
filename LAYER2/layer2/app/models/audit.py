"""
Audit log and workflow state ORM models.
Kept in a separate module to allow rfi.py to import them at the bottom
(resolving the circular relationship reference).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LAYER2.layer2.app.database import Base

if TYPE_CHECKING:
    from LAYER2.layer2.app.models.rfi import RFI


class WorkflowState(Base):
    """
    Current pipeline stage for an RFI.
    One-to-one with RFI. Created at ingest time with stage='Received'.

    Stages (from §4.4 state diagram):
      Received → Categorized → RA_Clinical_Review
      → Affiliate_Review (optional) → CTA_Mgmt_Review
      → EU_Hub_Approval → Submitted
    """

    __tablename__ = "workflow_state"

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_stage: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Received"
    )
    stage_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # ── Bible §6.4 — Submission Gate (GATE-001) ─────────────────────────────
    # A response may not have a submitted_at timestamp without a recorded
    # human approval event. These fields enforce that invariant.
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Human who approved — GATE-001 enforcement",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When approval happened",
    )

    rfi: Mapped["RFI"] = relationship("RFI", back_populates="workflow_state")


class AuditLog(Base):
    """
    Hash-chained audit trail.

    Every state transition (ingest, stage change, edit) appends one row.
    curr_hash = SHA-256(prev_hash || canonical_json(action_data))
    so any tampering with a past row breaks all hashes after it.

    `metadata_` (stored as 'metadata' in DB) holds action-specific
    context as JSONB — e.g. old/new stage, actor notes, diff snippets.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g. "ingested", "stage_advanced", "response_updated"
    actor: Mapped[Optional[str]] = mapped_column(String(100))
    prev_hash: Mapped[Optional[str]] = mapped_column(
        String(64)
    )  # None only on genesis entry
    curr_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB  # column name in DB is 'metadata'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rfi: Mapped["RFI"] = relationship("RFI", back_populates="audit_logs")


class PolicyOverride(Base):
    """
    Auditable, justified bypass of a governance rule — Bible §14.1.

    Every override is a permanent, attributable audit artifact.  The rule
    itself remains enforced for all other records; only the specific
    record named here is exempted.

    An override also appends a hash-chained AuditLog entry (event_type:
    policy_override) so the full provenance is visible in the audit trail.
    """

    __tablename__ = "policy_override"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    policy_rule: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. 'RFI-SLA-001'",
    )
    record_id: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="RFI rfi_id or consideration_id_str",
    )
    record_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="rfi",
        comment="rfi | consideration",
    )
    overridden_by: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Human who authorised the override",
    )
    justification: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Required — never null",
    )
    overridden_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Link to parent RFI for chain queries (nullable for non-RFI overrides)
    rfi_uuid: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi.id", ondelete="SET NULL"),
        nullable=True,
    )

    rfi: Mapped[Optional["RFI"]] = relationship("RFI", back_populates="policy_overrides")


class ExtractionCorrection(Base):
    """
    Bible §14.1 — Extraction Correction Loop.
    Logs human corrections to extracted fields at the Submission Gate,
    creating a labeled dataset for future model fine-tuning.
    """

    __tablename__ = "extraction_correction"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    consideration_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("consideration.consideration_id_str", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment="e.g. 'ctr_article_id', 'msc_id'"
    )
    original_value: Mapped[Optional[str]] = mapped_column(Text)
    corrected_value: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
