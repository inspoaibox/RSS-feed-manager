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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('custom_rules')}
    indexes = {index['name'] for index in inspector.get_indexes('custom_rules')}

    if 'feed_id' not in columns:
        op.add_column('custom_rules', sa.Column('feed_id', sa.Integer(), nullable=True))
    if 'ix_custom_rules_feed_id' not in indexes:
        op.create_index('ix_custom_rules_feed_id', 'custom_rules', ['feed_id'])

    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('custom_rules') as batch_op:
            batch_op.create_foreign_key(
                'fk_custom_rules_feed_id',
                'feeds',
                ['feed_id'],
                ['id'],
                ondelete='SET NULL',
            )
    else:
        op.create_foreign_key(
            'fk_custom_rules_feed_id',
            'custom_rules',
            'feeds',
            ['feed_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('custom_rules') as batch_op:
            batch_op.drop_constraint('fk_custom_rules_feed_id', type_='foreignkey')
    else:
        op.drop_constraint('fk_custom_rules_feed_id', 'custom_rules', type_='foreignkey')
    op.drop_index('ix_custom_rules_feed_id', table_name='custom_rules')
    op.drop_column('custom_rules', 'feed_id')
