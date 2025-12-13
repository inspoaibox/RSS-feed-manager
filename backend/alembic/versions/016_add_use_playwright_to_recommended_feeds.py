"""Add use_playwright to recommended_feeds

Revision ID: 016
Revises: 015
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'recommended_feeds',
        sa.Column('use_playwright', sa.Boolean(), server_default='0', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('recommended_feeds', 'use_playwright')
