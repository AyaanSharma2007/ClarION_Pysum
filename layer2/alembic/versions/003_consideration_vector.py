"""
Migration 003 — Add consideration_id_str + per-consideration embedding.

consideration_id_str
    The Neo4j merge key for each Consideration node.
    Format: ``{rfi_id}-C{number}``  e.g. ``CT-2024-123456-12-00-SM01-001-C1``

    This is the bridge ID that lets a pgvector similarity hit jump straight
    into the Neo4j graph:  pgvector returns consideration_id_str values →
    Neo4j MATCH (c:Consideration {consideration_id: $id}) …

consideration.embedding  vector(384)
    Per-consideration embedding of ``concern_text + response_text``.
    Stored at ingest time alongside the existing rfi.embedding (whole-RFI).
    Enables the hybrid search pattern that returns consideration-level hits
    rather than RFI-level hits.

    An HNSW index is created for fast approximate nearest-neighbour search
    (same parameters as the rfi.embedding index).

Run with:
    cd layer2
    alembic upgrade head
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── consideration_id_str ──────────────────────────────────────────────────
    # The Neo4j merge key.  nullable=True so existing rows are not broken;
    # new rows will always have it populated by the ingest router.
    op.add_column(
        "consideration",
        sa.Column(
            "consideration_id_str",
            sa.String(150),
            nullable=True,
            unique=True,
            comment="Neo4j merge key: {rfi_id}-C{number}",
        ),
    )
    op.create_index(
        "ix_consideration_id_str",
        "consideration",
        ["consideration_id_str"],
    )

    # ── per-consideration embedding ───────────────────────────────────────────
    # pgvector's vector type is not a native SQLAlchemy type — add via raw SQL.
    op.execute("ALTER TABLE consideration ADD COLUMN embedding vector(384)")

    # HNSW index — same parameters as ix_rfi_embedding_hnsw.
    op.execute(
        """
        CREATE INDEX ix_consideration_embedding_hnsw
        ON consideration
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_consideration_embedding_hnsw")
    op.drop_column("consideration", "embedding")
    op.drop_index("ix_consideration_id_str", table_name="consideration")
    op.drop_column("consideration", "consideration_id_str")
