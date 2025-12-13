"""Add recommended_feeds table

Revision ID: 015
Revises: 014
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'recommended_feeds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon_url', sa.String(2048), nullable=True),
        sa.Column('categories', sa.String(500), server_default='', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('subscriber_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('url')
    )
    op.create_index('ix_recommended_feeds_is_active', 'recommended_feeds', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_recommended_feeds_is_active', 'recommended_feeds')
    op.drop_table('recommended_feeds')
