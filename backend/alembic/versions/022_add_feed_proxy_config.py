"""Add proxy configuration to feeds.

Revision ID: 022
Revises: 021
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '022'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('feeds')}

    if 'proxy_enabled' not in columns:
        op.add_column(
            'feeds',
            sa.Column('proxy_enabled', sa.Boolean(), nullable=False, server_default='0'),
        )
    if 'proxy_url' not in columns:
        op.add_column('feeds', sa.Column('proxy_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('feeds')}
    if 'proxy_url' in columns:
        op.drop_column('feeds', 'proxy_url')
    if 'proxy_enabled' in columns:
        op.drop_column('feeds', 'proxy_enabled')
