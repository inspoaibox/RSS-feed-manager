"""Add browser_engine to feeds.

Revision ID: 021
Revises: 020
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'feeds',
        sa.Column('browser_engine', sa.String(length=20), nullable=False, server_default='http'),
    )
    op.execute("UPDATE feeds SET browser_engine = 'playwright' WHERE use_playwright = true")


def downgrade() -> None:
    op.drop_column('feeds', 'browser_engine')
