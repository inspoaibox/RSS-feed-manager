"""Article link nullable and add rule_type

Revision ID: 006
Revises: 005
Create Date: 2025-12-08
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make article link nullable
    op.alter_column('articles', 'link',
                    existing_type=sa.String(2048),
                    nullable=True)
    
    # Add rule_type to custom_rules (default 'general')
    op.add_column('custom_rules', sa.Column('rule_type', sa.String(20), nullable=False, server_default='general'))


def downgrade() -> None:
    op.drop_column('custom_rules', 'rule_type')
    op.alter_column('articles', 'link',
                    existing_type=sa.String(2048),
                    nullable=False)
