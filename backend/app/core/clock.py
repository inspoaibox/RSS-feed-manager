"""UTC clock for the existing SQLAlchemy/SQLite timestamp convention."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return naive UTC, preserving the database's existing timestamp semantics."""
    return datetime.now(UTC).replace(tzinfo=None)
