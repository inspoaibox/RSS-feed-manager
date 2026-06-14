"""Add proxy configuration to custom rules.

Revision ID: 028
Revises: 027
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("custom_rules")}

    if "proxy_enabled" not in columns:
        op.add_column(
            "custom_rules",
            sa.Column("proxy_enabled", sa.Boolean(), nullable=False, server_default="0"),
        )
    if "proxy_url" not in columns:
        op.add_column("custom_rules", sa.Column("proxy_url", sa.String(length=2048), nullable=True))
    if "proxy_mode" not in columns:
        op.add_column(
            "custom_rules",
            sa.Column("proxy_mode", sa.String(length=20), nullable=False, server_default="none"),
        )
    if "proxy_pool_country" not in columns:
        op.add_column(
            "custom_rules",
            sa.Column("proxy_pool_country", sa.String(length=20), nullable=True),
        )
    if "proxy_pool_protocol" not in columns:
        op.add_column(
            "custom_rules",
            sa.Column("proxy_pool_protocol", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("custom_rules")}
    if "proxy_pool_protocol" in columns:
        op.drop_column("custom_rules", "proxy_pool_protocol")
    if "proxy_pool_country" in columns:
        op.drop_column("custom_rules", "proxy_pool_country")
    if "proxy_mode" in columns:
        op.drop_column("custom_rules", "proxy_mode")
    if "proxy_url" in columns:
        op.drop_column("custom_rules", "proxy_url")
    if "proxy_enabled" in columns:
        op.drop_column("custom_rules", "proxy_enabled")
