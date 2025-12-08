"""Add cookies to custom_rules

Revision ID: 007
Revises: 006
Create Date: 2025-12-08
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('custom_rules', sa.Column('cookies', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('custom_rules', 'cookies')
