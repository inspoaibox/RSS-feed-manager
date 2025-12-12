"""Increase author field length from 255 to 500.

Revision ID: 013
Revises: 012
Create Date: 2025-12-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Increase author field length to 500
    op.alter_column('articles', 'author',
                    existing_type=sa.String(255),
                    type_=sa.String(500),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert to 255 (may truncate data)
    op.alter_column('articles', 'author',
                    existing_type=sa.String(500),
                    type_=sa.String(255),
                    existing_nullable=True)
