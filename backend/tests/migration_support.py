"""Disposable PostgreSQL databases for migration tests, never the application's database."""

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url


@contextmanager
def postgres_migration_database():
    value = os.environ.get("MIGRATION_TEST_DATABASE_URL")
    if not value:
        if os.environ.get("MIGRATION_TEST_FULL_CHAIN") == "1":
            pytest.fail("PostgreSQL migration CI requires MIGRATION_TEST_DATABASE_URL")
        pytest.skip("Set MIGRATION_TEST_DATABASE_URL to a dedicated PostgreSQL test server")
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("MIGRATION_TEST_DATABASE_URL must point to PostgreSQL")
    url = url.set(drivername="postgresql+psycopg2")
    database = f"rss_migration_test_{uuid4().hex}"
    admin = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    engine = None
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{database}"'))
            created = True
        engine = sa.create_engine(url.set(database=database))
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as connection:
                connection.execute(sa.text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()
