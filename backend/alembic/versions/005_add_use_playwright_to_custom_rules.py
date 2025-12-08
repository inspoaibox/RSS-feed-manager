"""Add use_playwright to custom_rules

Revision ID: 005
Revises: 004
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('custom_rules', sa.Column('use_playwright', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('custom_rules', 'use_playwright')
