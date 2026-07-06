"""Launch Celery workers using runtime settings stored in the database."""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.system_settings import SystemSettings
from app.services.browser_fetch_settings import (
    browser_worker_runtime_settings,
    worker_runtime_settings,
)
from app.tasks.feed_tasks import get_sync_database_url


def _coerce_int(value: str | None, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else fallback
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def _load_system_settings(keys: list[str]) -> dict[str, str]:
    engine = create_engine(get_sync_database_url())
    SessionLocal = sessionmaker(bind=engine)
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(SystemSettings).where(SystemSettings.key.in_(keys))
            ).scalars().all()
            return {row.key: row.value for row in rows if row.value is not None}
    finally:
        engine.dispose()


def _runtime_value(
    values: dict[str, str],
    key: str,
    env_fallback: int,
    minimum: int,
    maximum: int,
) -> int:
    return _coerce_int(values.get(key), env_fallback, minimum, maximum)


def _build_worker_args(kind: str) -> list[str]:
    if kind == "browser":
        env_defaults = browser_worker_runtime_settings()
        values = _load_system_settings(
            ["browser_worker_concurrency", "browser_worker_max_tasks_per_child"]
        )
        concurrency = _runtime_value(
            values,
            "browser_worker_concurrency",
            env_defaults["browser_worker_concurrency"],
            1,
            20,
        )
        max_tasks = _runtime_value(
            values,
            "browser_worker_max_tasks_per_child",
            env_defaults["browser_worker_max_tasks_per_child"],
            1,
            500,
        )
        queues = "browser"
    else:
        env_defaults = worker_runtime_settings()
        values = _load_system_settings(["worker_concurrency", "worker_max_tasks_per_child"])
        concurrency = _runtime_value(
            values,
            "worker_concurrency",
            env_defaults["worker_concurrency"],
            1,
            64,
        )
        max_tasks = _runtime_value(
            values,
            "worker_max_tasks_per_child",
            env_defaults["worker_max_tasks_per_child"],
            1,
            500,
        )
        queues = "feed,translation,celery"

    return [
        "celery",
        "-A",
        "app.tasks.celery_app",
        "worker",
        "--loglevel=info",
        f"--concurrency={concurrency}",
        f"--max-tasks-per-child={max_tasks}",
        "-Q",
        queues,
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch a configured Celery worker.")
    parser.add_argument("--kind", choices=["worker", "browser"], required=True)
    args = parser.parse_args()

    command = _build_worker_args(args.kind)
    print(f"[WorkerLauncher] Starting {' '.join(command)}", flush=True)
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
