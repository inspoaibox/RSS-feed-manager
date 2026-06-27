"""Add trigram indexes for keyword count searches.

Revision ID: 033
Revises: 032
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRIGRAM_INDEXES = (
    ("ix_articles_title_trgm", "articles", "title"),
    ("ix_articles_content_trgm", "articles", "content"),
    ("ix_articles_full_content_trgm", "articles", "full_content"),
    ("ix_articles_summary_trgm", "articles", "summary"),
    ("ix_articles_translation_trgm", "articles", "translation"),
    ("ix_articles_author_trgm", "articles", "author"),
    ("ix_feeds_title_trgm", "feeds", "title"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in TRIGRAM_INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} USING gin ({column_name} gin_trgm_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for index_name, _table_name, _column_name in reversed(TRIGRAM_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
