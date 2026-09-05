"""
ORM models for RFI, Consideration, NCA, TherapeuticArea, CTRArticle,
ResponseComponent, and ResponseComponentVersion.

Field names and table names map 1-to-1 with:
  - rfi_extraction_schema.json (the contract Layer 1 sends)
  - The Neo4j graph model (Layer 3 reads from these tables)
  - The ERD in §4.6 of the implementation guide
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
<<<<<<< HEAD
    Boolean,
=======
>>>>>>> main
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
<<<<<<< HEAD
    text,
=======
>>>>>>> main
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

<<<<<<< HEAD
from LAYER2.layer2.app.database import Base
=======
from app.database import Base
>>>>>>> main


# ─── Lookup / dimension tables ─────────────────────────────────────────────────


class NCA(Base):
    """
    National Competent Authority / Member State Concerned (MSC).
    The extraction schema uses 'msc.country' as the merge key —
    that maps to NCA.country here.
    Layer 3 reads this as the MSC node.
    """

    __tablename__ = "nca"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    country: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(200))

    rfis: Mapped[list["RFI"]] = relationship("RFI", back_populates="nca")


class TherapeuticArea(Base):
    """
    Therapeutic indication / disease area.
    The extraction schema uses 'indication.name' as the merge key —
    that maps to TherapeuticArea.name here.
    Layer 3 reads this as the Indication node.
    """

    __tablename__ = "therapeutic_area"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(300), unique=True, nullable=False, index=True
    )

    rfis: Mapped[list["RFI"]] = relationship(
        "RFI", back_populates="therapeutic_area"
    )


class CTRArticle(Base):
    """
    CTR regulation article / annex section.
    The extraction schema uses 'ctr_article.name' as the merge key.
    Layer 3 reads this as the CTRArticle node.
    """

    __tablename__ = "ctr_article"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # e.g. "Annex I, Section 63" or "Article 6"
    name: Mapped[str] = mapped_column(
        String(300), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

    considerations: Mapped[list["Consideration"]] = relationship(
        "Consideration", back_populates="ctr_article"
    )


# ─── Core RFI table ────────────────────────────────────────────────────────────


class RFI(Base):
    """
    Central record — one row per RFI document.

    `rfi_id` is the human-readable identifier from the PDF
    (e.g. 'CT-2024-123456-12-00-SM01-001'). It is the merge key
    Layer 1 uses, and the key Layer 3 uses to create the RFI node.

    `embedding` stores the 384-dim vector of `rfi_text` for semantic
    search. Dimension matches all-MiniLM-L6-v2 (default).
    When switched to Voyage AI (1536 dims), update EMBEDDING_DIMENSION
    and re-run the migration.

    `rfi_text` is constructed at ingest time by concatenating all
    consideration concern_text + response texts — it is the text we
    embed and expose to Layer 5 (recommender).
    """

    __tablename__ = "rfi"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rfi_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

<<<<<<< HEAD
    # ── Bible §7 — RFI type and status ──────────────────────────────────────
    rfi_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="'validation' or 'assessment' — Bible §7",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="received",
        comment="Workflow status — Bible §7 status enum",
    )
    source_document_ref: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Evidence Integrity 'Original' dimension — Bible §6.3",
    )

=======
>>>>>>> main
    # ── Dates from extraction schema ────────────────────────────────────────
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    response_date: Mapped[Optional[date]] = mapped_column(Date)
    submit_date: Mapped[Optional[date]] = mapped_column(Date)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Classification (filled by extraction service or Layer 3 backfill) ───
    category: Mapped[Optional[str]] = mapped_column(String(100))

    # ── Ownership tag (passed through from Layer 1) ─────────────────────────
    owner_team: Mapped[Optional[str]] = mapped_column(String(100))

    # ── Foreign keys ────────────────────────────────────────────────────────
    nca_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nca.id"), index=True
    )
    therapeutic_area_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("therapeutic_area.id"), index=True
    )

    # ── Semantic search ──────────────────────────────────────────────────────
    # Concatenated response texts — this is what gets embedded.
    rfi_text: Mapped[Optional[str]] = mapped_column(Text)
    # Vector column — dimension must match EMBEDDING_DIMENSION in config.
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))

    # ── Relationships ────────────────────────────────────────────────────────
    nca: Mapped[Optional["NCA"]] = relationship("NCA", back_populates="rfis")
    therapeutic_area: Mapped[Optional["TherapeuticArea"]] = relationship(
        "TherapeuticArea", back_populates="rfis"
    )
    considerations: Mapped[list["Consideration"]] = relationship(
        "Consideration",
        back_populates="rfi",
        cascade="all, delete-orphan",
        order_by="Consideration.number",
    )
    workflow_state: Mapped[Optional["WorkflowState"]] = relationship(
        "WorkflowState",
        back_populates="rfi",
        uselist=False,
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="rfi",
        cascade="all, delete-orphan",
        order_by="AuditLog.created_at",
    )
<<<<<<< HEAD
    policy_overrides: Mapped[list["PolicyOverride"]] = relationship(
        "PolicyOverride",
        back_populates="rfi",
        cascade="all, delete-orphan",
        order_by="PolicyOverride.overridden_at",
    )
=======
>>>>>>> main


# ─── Consideration ─────────────────────────────────────────────────────────────


class Consideration(Base):
    """
    One consideration block inside an RFI document.
    Maps to the (RFI)-[:HAS_CONSIDERATION]->(Consideration) graph edge.
    """

    __tablename__ = "consideration"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Neo4j merge key — format: ``{rfi_id}-C{number}``
    # e.g. "CT-2024-123456-12-00-SM01-001-C1"
    # This is the bridge ID that lets a pgvector hit jump into the graph:
    #   pgvector returns consideration_id_str → Neo4j MATCH on this value.
    # Populated at ingest time; null on rows ingested before migration 003.
    consideration_id_str: Mapped[Optional[str]] = mapped_column(
        String(150), unique=True, nullable=True, index=True,
        comment="Neo4j merge key: {rfi_id}-C{number}",
    )

    # Reviewer's concern/question text (verbatim from extraction schema)
    # Maps to Consideration.concern_text — added in schema v2
    concern_text: Mapped[Optional[str]] = mapped_column(Text)

    # Sponsor's response text (verbatim from extraction schema)
    response_text: Mapped[Optional[str]] = mapped_column(Text)

    # Per-consideration embedding of concern_text + response_text.
    # Used by POST /search/hybrid to return consideration-level hits
    # rather than whole-RFI hits — each hit maps 1-to-1 to a Neo4j node.
    # Dimension matches EMBEDDING_DIMENSION in config (default 384).
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))

    # Outcome — null at extraction time, backfilled from follow-up documents
    # Maps to (Consideration)-[:STATUS]->(Outcome)
    outcome_status: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # accepted | follow-up-required | rejected

    ctr_article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ctr_article.id"), index=True
    )

<<<<<<< HEAD
    # ── Bible §8.6 — Graph analytics fed back from Neo4j ────────────────────
    cluster_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Louvain cluster fed back from Neo4j — Bible §8.6",
    )
    is_hub_article: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, server_default=text("false"),
        comment="Hub-article flag from Neo4j — Bible §8.6",
    )

=======
>>>>>>> main
    rfi: Mapped["RFI"] = relationship("RFI", back_populates="considerations")
    ctr_article: Mapped[Optional["CTRArticle"]] = relationship(
        "CTRArticle", back_populates="considerations"
    )
    response_components: Mapped[list["ResponseComponent"]] = relationship(
        "ResponseComponent",
        back_populates="consideration",
        cascade="all, delete-orphan",
    )


# ─── Response components (for the Layer 5 recommender) ────────────────────────


class ResponseComponent(Base):
    """
    A reusable, success-scored response snippet.
    Layer 5 (recommender) promotes high-quality consideration responses
    here and maintains a success_score based on NCA acceptance.
    Versioned for audit purposes.
    """

    __tablename__ = "response_component"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    consideration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consideration.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    success_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    consideration: Mapped["Consideration"] = relationship(
        "Consideration", back_populates="response_components"
    )
    versions: Mapped[list["ResponseComponentVersion"]] = relationship(
        "ResponseComponentVersion",
        back_populates="response_component",
        cascade="all, delete-orphan",
    )


class ResponseComponentVersion(Base):
    """Immutable version history for ResponseComponent edits."""

    __tablename__ = "response_component_version"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    response_component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("response_component.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    response_component: Mapped["ResponseComponent"] = relationship(
        "ResponseComponent", back_populates="versions"
    )


# ─── Audit + Workflow (imported here to satisfy SQLAlchemy mapper) ─────────────
# Defined in audit.py, imported so Base.metadata sees all tables.
<<<<<<< HEAD
from LAYER2.layer2.app.models.audit import AuditLog, WorkflowState  # noqa: E402, F401
=======
from app.models.audit import AuditLog, WorkflowState  # noqa: E402, F401
>>>>>>> main
