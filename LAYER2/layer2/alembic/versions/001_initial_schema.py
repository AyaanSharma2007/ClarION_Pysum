"""
Migration 001 — Initial schema for RFI Nexus Layer 2.

Creates all core tables from the ERD (§4.6 of the implementation guide)
and enables the pgvector extension. Run with:

    cd layer2
    alembic upgrade head
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable pgvector ───────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── nca ────────────────────────────────────────────────────────────────────
    op.create_table(
        "nca",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("country", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200)),
    )
    op.create_index("ix_nca_country", "nca", ["country"])

    # ── therapeutic_area ───────────────────────────────────────────────────────
    op.create_table(
        "therapeutic_area",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False, unique=True),
    )
    op.create_index("ix_therapeutic_area_name", "therapeutic_area", ["name"])

    # ── ctr_article ────────────────────────────────────────────────────────────
    op.create_table(
        "ctr_article",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False, unique=True),
        sa.Column("description", sa.Text),
    )
    op.create_index("ix_ctr_article_name", "ctr_article", ["name"])

    # ── rfi ────────────────────────────────────────────────────────────────────
    # The embedding column uses pgvector's vector type which Alembic doesn't
    # know natively. We create the table without it, then ADD it via raw SQL.
    # To switch to Voyage AI (1536 dims), create a new migration that runs:
    #   ALTER TABLE rfi ALTER COLUMN embedding TYPE vector(1536)
    op.create_table(
        "rfi",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rfi_id", sa.String(100), nullable=False, unique=True),
        sa.Column("due_date", sa.Date),
        sa.Column("response_date", sa.Date),
        sa.Column("submit_date", sa.Date),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("category", sa.String(100)),
        sa.Column("owner_team", sa.String(100)),
        sa.Column("nca_id", UUID(as_uuid=True), sa.ForeignKey("nca.id")),
        sa.Column(
            "therapeutic_area_id",
            UUID(as_uuid=True),
            sa.ForeignKey("therapeutic_area.id"),
        ),
        sa.Column("rfi_text", sa.Text),
    )
    # Add the vector column separately using raw SQL (pgvector type)
    op.execute("ALTER TABLE rfi ADD COLUMN embedding vector(384)")
    op.create_index("ix_rfi_rfi_id", "rfi", ["rfi_id"])
    op.create_index("ix_rfi_nca_id", "rfi", ["nca_id"])
    op.create_index("ix_rfi_therapeutic_area_id", "rfi", ["therapeutic_area_id"])

    # HNSW index for fast approximate nearest-neighbour search
    op.execute(
        """
        CREATE INDEX ix_rfi_embedding_hnsw
        ON rfi
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # ── consideration ──────────────────────────────────────────────────────────
    op.create_table(
        "consideration",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rfi_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rfi.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("response_text", sa.Text),
        sa.Column("outcome_status", sa.String(50)),
        sa.Column(
            "ctr_article_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ctr_article.id"),
        ),
    )
    op.create_index("ix_consideration_rfi_id", "consideration", ["rfi_id"])
    op.create_index(
        "ix_consideration_ctr_article_id", "consideration", ["ctr_article_id"]
    )

    # ── response_component ────────────────────────────────────────────────────
    op.create_table(
        "response_component",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "consideration_id",
            UUID(as_uuid=True),
            sa.ForeignKey("consideration.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("success_score", sa.Float, default=0.0),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_response_component_consideration_id",
        "response_component",
        ["consideration_id"],
    )

    # ── response_component_version ────────────────────────────────────────────
    op.create_table(
        "response_component_version",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "response_component_id",
            UUID(as_uuid=True),
            sa.ForeignKey("response_component.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── workflow_state ────────────────────────────────────────────────────────
    op.create_table(
        "workflow_state",
        sa.Column(
            "rfi_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rfi.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("current_stage", sa.String(50), nullable=False, default="Received"),
        sa.Column(
            "stage_entered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sla_due_at", sa.DateTime(timezone=True)),
    )

    # ── audit_log ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rfi_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rfi.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(100)),
        sa.Column("prev_hash", sa.String(64)),
        sa.Column("curr_hash", sa.String(64), nullable=False),
        sa.Column("metadata", JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_rfi_id", "audit_log", ["rfi_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("workflow_state")
    op.drop_table("response_component_version")
    op.drop_table("response_component")
    op.drop_table("consideration")
    op.drop_table("rfi")
    op.drop_table("ctr_article")
    op.drop_table("therapeutic_area")
    op.drop_table("nca")
    op.execute("DROP EXTENSION IF EXISTS vector")
