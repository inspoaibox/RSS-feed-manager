"""Add user prompt settings

Revision ID: 002
Revises: 001
Create Date: 2024-12-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add prompt columns to users table
    op.add_column('users', sa.Column('translate_prompt', sa.String(2000), nullable=True))
    op.add_column('users', sa.Column('summarize_prompt', sa.String(2000), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'translate_prompt')
    op.drop_column('users', 'summarize_prompt')
