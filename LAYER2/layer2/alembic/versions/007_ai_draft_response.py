"""add ai_draft_response

Revision ID: 007
Revises: 006
Create Date: 2026-09-06 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('ai_draft_response',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('consideration_id', sa.UUID(), nullable=False),
    sa.Column('draft_text', sa.Text(), nullable=False),
    sa.Column('risk_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['consideration_id'], ['consideration.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_draft_response_consideration_id'), 'ai_draft_response', ['consideration_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_ai_draft_response_consideration_id'), table_name='ai_draft_response')
    op.drop_table('ai_draft_response')
