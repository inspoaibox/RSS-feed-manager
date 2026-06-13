"""Add proxy pool.

Revision ID: 023
Revises: 022
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '023'
down_revision: Union[str, None] = '022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    created_proxy_pool = False
    if 'proxy_pool_entries' not in tables:
        op.create_table(
            'proxy_pool_entries',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('protocol', sa.String(length=20), nullable=False),
            sa.Column('host', sa.String(length=255), nullable=False),
            sa.Column('port', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(length=512), nullable=True),
            sa.Column('password', sa.String(length=1024), nullable=True),
            sa.Column('country', sa.String(length=20), nullable=True),
            sa.Column('source_format', sa.String(length=80), nullable=False, server_default='unknown'),
            sa.Column('proxy_url', sa.String(length=2048), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_latency_ms', sa.Integer(), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'proxy_url', name='uq_proxy_pool_user_proxy_url'),
        )
        op.create_index('ix_proxy_pool_entries_user_id', 'proxy_pool_entries', ['user_id'])
        op.create_index('ix_proxy_pool_entries_is_active', 'proxy_pool_entries', ['is_active'])
        op.create_index('ix_proxy_pool_entries_country', 'proxy_pool_entries', ['country'])
        op.create_index('ix_proxy_pool_entries_protocol', 'proxy_pool_entries', ['protocol'])
        created_proxy_pool = True

    feed_columns = {column['name'] for column in inspector.get_columns('feeds')}
    if 'proxy_mode' not in feed_columns:
        op.add_column(
            'feeds',
            sa.Column('proxy_mode', sa.String(length=20), nullable=False, server_default='none'),
        )
        op.execute("UPDATE feeds SET proxy_mode = 'single' WHERE proxy_enabled = true")
    if 'proxy_pool_country' not in feed_columns:
        op.add_column('feeds', sa.Column('proxy_pool_country', sa.String(length=20), nullable=True))
    if 'proxy_pool_protocol' not in feed_columns:
        op.add_column('feeds', sa.Column('proxy_pool_protocol', sa.String(length=20), nullable=True))

    proxy_columns = (
        set()
        if created_proxy_pool
        else {column['name'] for column in inspector.get_columns('proxy_pool_entries')}
    )
    if not created_proxy_pool and 'last_used_at' not in proxy_columns:
        op.add_column('proxy_pool_entries', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    feed_columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('feeds')}
    if 'proxy_pool_protocol' in feed_columns:
        op.drop_column('feeds', 'proxy_pool_protocol')
    if 'proxy_pool_country' in feed_columns:
        op.drop_column('feeds', 'proxy_pool_country')
    if 'proxy_mode' in feed_columns:
        op.drop_column('feeds', 'proxy_mode')

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'proxy_pool_entries' in tables:
        op.drop_table('proxy_pool_entries')
