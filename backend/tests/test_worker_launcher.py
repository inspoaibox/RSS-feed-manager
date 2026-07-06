from app.tasks import worker_launcher


def test_browser_worker_launcher_prefers_database_runtime_settings(monkeypatch):
    monkeypatch.setattr(
        worker_launcher,
        "_load_system_settings",
        lambda keys: {
            "browser_worker_concurrency": "2",
            "browser_worker_max_tasks_per_child": "5",
        },
    )
    monkeypatch.setenv("BROWSER_WORKER_CONCURRENCY", "8")
    monkeypatch.setenv("BROWSER_WORKER_MAX_TASKS_PER_CHILD", "50")

    command = worker_launcher._build_worker_args("browser")

    assert "--concurrency=2" in command
    assert "--max-tasks-per-child=5" in command
    assert command[-1] == "browser"


def test_worker_launcher_uses_environment_when_database_settings_missing(monkeypatch):
    monkeypatch.setattr(worker_launcher, "_load_system_settings", lambda keys: {})
    monkeypatch.setenv("WORKER_CONCURRENCY", "4")
    monkeypatch.setenv("WORKER_MAX_TASKS_PER_CHILD", "30")

    command = worker_launcher._build_worker_args("worker")

    assert "--concurrency=4" in command
    assert "--max-tasks-per-child=30" in command
    assert command[-1] == "feed,translation,celery"
