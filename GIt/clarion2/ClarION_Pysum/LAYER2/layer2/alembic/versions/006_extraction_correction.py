"""
Migration 006 — Add extraction_correction table (Bible §14.1).

Logs human corrections to extracted fields at the Submission Gate,
creating a labeled dataset for future model fine-tuning.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extraction_correction",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("consideration_id", sa.Text, sa.ForeignKey("consideration.consideration_id_str", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.Text, nullable=False, comment="e.g. 'ctr_article_id', 'msc_id'"),
        sa.Column("original_value", sa.Text, nullable=True),
        sa.Column("corrected_value", sa.Text, nullable=False),
        sa.Column("corrected_by", sa.Text, nullable=False),
        sa.Column(
            "corrected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("ix_extraction_correction_consideration_id", "extraction_correction", ["consideration_id"])


def downgrade() -> None:
    op.drop_index("ix_extraction_correction_consideration_id", table_name="extraction_correction")
    op.drop_table("extraction_correction")
