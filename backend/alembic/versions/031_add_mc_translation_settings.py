"""Add Mc-Translation settings.

Revision ID: 031
Revises: 030_add_push_notifications
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "031"
down_revision: Union[str, None] = "030_add_push_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    if "mc_translation_api_key" not in user_columns:
        op.add_column(
            "users",
            sa.Column("mc_translation_api_key", sa.String(length=500), nullable=True),
        )
    if "mc_translation_base_url" not in user_columns:
        op.add_column(
            "users",
            sa.Column("mc_translation_base_url", sa.String(length=255), nullable=True),
        )
    if "mc_translation_model" not in user_columns:
        op.add_column(
            "users",
            sa.Column("mc_translation_model", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    if "mc_translation_model" in user_columns:
        op.drop_column("users", "mc_translation_model")
    if "mc_translation_base_url" in user_columns:
        op.drop_column("users", "mc_translation_base_url")
    if "mc_translation_api_key" in user_columns:
        op.drop_column("users", "mc_translation_api_key")
