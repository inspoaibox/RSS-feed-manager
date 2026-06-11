"""Add keyword subscriptions table.

Revision ID: 020
Revises: 019
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '020'
down_revision: Union[str, None] = '019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'keyword_subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('keyword', sa.String(200), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('match_title', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('match_content', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('match_author', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('match_feed_title', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'keyword', name='uq_keyword_subscription_user_keyword'),
    )
    op.create_index('ix_keyword_subscriptions_user_id', 'keyword_subscriptions', ['user_id'])
    op.create_index('ix_keyword_subscriptions_is_active', 'keyword_subscriptions', ['is_active'])


def downgrade() -> None:
    op.drop_table('keyword_subscriptions')
