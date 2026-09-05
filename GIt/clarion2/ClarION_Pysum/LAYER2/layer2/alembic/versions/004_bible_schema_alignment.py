"""
Migration 004 — Align schema with The Clarion Bible §7.

Adds columns required by the Bible's canonical SQL schema that were
missing from the original implementation:

rfi table:
  - rfi_type      TEXT   ('validation' | 'assessment')
  - status        TEXT   (full workflow status enum)
  - source_document_ref TEXT  (Evidence Integrity "Original" dimension)

consideration table:
  - cluster_id    INTEGER  (Louvain cluster fed back from Neo4j §8.6)
  - is_hub_article BOOLEAN (hub-article flag fed back from Neo4j §8.6)

workflow_state table:
  - approved_by   TEXT      (human who approved — GATE-001 enforcement)
  - approved_at   TIMESTAMPTZ (when approval happened)

Run with:
    cd layer2
    alembic upgrade head
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── rfi table additions ──────────────────────────────────────────────────
    op.add_column(
        "rfi",
        sa.Column(
            "rfi_type",
            sa.String(20),
            nullable=True,
            comment="'validation' or 'assessment' — Bible §7",
        ),
    )
    op.add_column(
        "rfi",
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="received",
            comment="Workflow status — Bible §7 status enum",
        ),
    )
    op.add_column(
        "rfi",
        sa.Column(
            "source_document_ref",
            sa.Text,
            nullable=True,
            comment="Evidence Integrity 'Original' dimension — Bible §6.3",
        ),
    )
    op.create_index("ix_rfi_owner_team", "rfi", ["owner_team"])
    op.create_index("ix_rfi_status", "rfi", ["status"])

    # ── consideration table additions ────────────────────────────────────────
    op.add_column(
        "consideration",
        sa.Column(
            "cluster_id",
            sa.Integer,
            nullable=True,
            comment="Louvain cluster fed back from Neo4j — Bible §8.6",
        ),
    )
    op.add_column(
        "consideration",
        sa.Column(
            "is_hub_article",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
            comment="Hub-article flag from Neo4j — Bible §8.6",
        ),
    )

    # ── workflow_state table additions ────────────────────────────────────────
    op.add_column(
        "workflow_state",
        sa.Column(
            "approved_by",
            sa.String(100),
            nullable=True,
            comment="Human who approved — GATE-001 enforcement",
        ),
    )
    op.add_column(
        "workflow_state",
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When approval happened",
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow_state", "approved_at")
    op.drop_column("workflow_state", "approved_by")
    op.drop_column("consideration", "is_hub_article")
    op.drop_column("consideration", "cluster_id")
    op.drop_index("ix_rfi_status", table_name="rfi")
    op.drop_index("ix_rfi_owner_team", table_name="rfi")
    op.drop_column("rfi", "source_document_ref")
    op.drop_column("rfi", "status")
    op.drop_column("rfi", "rfi_type")
