import pytest

from app.tasks import feed_tasks
from app.utils.feed_parser import FeedParserError, is_browser_runtime_error


def test_is_browser_runtime_error_detects_cloakbrowser_thread_failure():
    assert is_browser_runtime_error("CloakBrowser error: can't start new thread")


def test_is_browser_runtime_error_ignores_site_http_failure():
    assert not is_browser_runtime_error("HTTP error 403: https://example.com/feed.xml")


def test_proxy_pool_stops_on_local_browser_runtime_error(monkeypatch):
    class Feed:
        id = 1
        user_id = 1
        url = "https://example.com/feed.xml"
        use_playwright = True
        browser_engine = "cloakbrowser"
        proxy_mode = "pool"
        proxy_pool_country = None
        proxy_pool_protocol = None

    class Proxy:
        def __init__(self, proxy_url):
            self.proxy_url = proxy_url

    recorded_failures = []

    async def fail_with_local_browser_error(*args, **kwargs):
        raise FeedParserError("CloakBrowser error: can't start new thread")

    monkeypatch.setattr(feed_tasks, "load_browser_fetch_settings_sync", lambda db: None)
    monkeypatch.setattr(
        feed_tasks,
        "_get_proxy_candidates_sync",
        lambda db, feed: [Proxy("http://proxy-1"), Proxy("http://proxy-2")],
    )
    monkeypatch.setattr(feed_tasks, "parse_feed", fail_with_local_browser_error)
    monkeypatch.setattr(
        feed_tasks,
        "_record_proxy_failure_sync",
        lambda db, proxy, error: recorded_failures.append((proxy.proxy_url, error)),
    )

    with pytest.raises(FeedParserError, match="浏览器运行环境异常，停止代理轮换"):
        feed_tasks._parse_feed_for_sync_refresh(object(), Feed())

    assert recorded_failures == []
