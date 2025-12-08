"""Add feed_id to custom_rules

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('custom_rules', sa.Column('feed_id', sa.Integer(), nullable=True))
    op.create_index('ix_custom_rules_feed_id', 'custom_rules', ['feed_id'])
    op.create_foreign_key(
        'fk_custom_rules_feed_id',
        'custom_rules',
        'feeds',
        ['feed_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_custom_rules_feed_id', 'custom_rules', type_='foreignkey')
    op.drop_index('ix_custom_rules_feed_id', table_name='custom_rules')
    op.drop_column('custom_rules', 'feed_id')
