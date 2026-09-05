"""
Migration 005 — Add policy_override table (Bible §14.1).

A policy override is an auditable, justified bypass of a governance
rule.  Every override becomes a permanent audit artifact — the rule
itself remains enforced, but the specific record is exempted with a
required human justification.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_override",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("policy_rule", sa.String(100), nullable=False, comment="e.g. 'RFI-SLA-001'"),
        sa.Column("record_id", sa.Text, nullable=False, comment="RFI rfi_id or consideration_id_str"),
        sa.Column("record_type", sa.String(50), nullable=False, server_default="rfi", comment="rfi | consideration"),
        sa.Column("overridden_by", sa.String(100), nullable=False, comment="Human who authorised the override"),
        sa.Column("justification", sa.Text, nullable=False, comment="Required — never null"),
        sa.Column(
            "overridden_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Link to parent RFI for chain queries (nullable for non-RFI overrides)
        sa.Column(
            "rfi_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rfi.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_index("ix_policy_override_record_id", "policy_override", ["record_id"])
    op.create_index("ix_policy_override_policy_rule", "policy_override", ["policy_rule"])


def downgrade() -> None:
    op.drop_index("ix_policy_override_policy_rule", table_name="policy_override")
    op.drop_index("ix_policy_override_record_id", table_name="policy_override")
    op.drop_table("policy_override")
