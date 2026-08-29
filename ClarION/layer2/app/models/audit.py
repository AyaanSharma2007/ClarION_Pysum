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

from app.database import Base

if TYPE_CHECKING:
    from app.models.rfi import RFI


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
