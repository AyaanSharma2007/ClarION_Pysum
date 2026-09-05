"""
Migration 002 — Add concern_text to consideration table.

Adds the `concern_text` column to store the reviewer's verbatim
concern/question, as introduced in rfi_extraction_schema (2).json.

This field enables semantic search to match against the underlying
concern, not just the sponsor's response.  Existing rows will have
NULL for this column until re-processed from the source PDF.

Run with:
    cd layer2
    alembic upgrade head
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # nullable=True so existing rows are unaffected
    op.add_column(
        "consideration",
        sa.Column("concern_text", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consideration", "concern_text")
