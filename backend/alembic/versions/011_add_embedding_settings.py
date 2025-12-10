"""Add embedding model settings to users table.

Revision ID: 011
Revises: 010
Create Date: 2024-12-10 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add embedding settings columns to users table
    op.add_column('users', sa.Column('embedding_provider_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('embedding_model', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'embedding_model')
    op.drop_column('users', 'embedding_provider_id')
