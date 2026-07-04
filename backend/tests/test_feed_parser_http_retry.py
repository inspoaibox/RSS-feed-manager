import pytest
from httpx import Request, RequestError, Response

from app.utils import feed_parser
from app.utils.feed_parser import FeedParserError, fetch_feed_content


class RetrySuccessAsyncClient:
    instance = None

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.requests = []
        RetrySuccessAsyncClient.instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout, follow_redirects, headers):
        self.requests.append(headers)
        request = Request("GET", url)
        if len(self.requests) == 1:
            return Response(403, request=request)
        return Response(
            200,
            content=b'<?xml version="1.0"?><rss><channel><title>OK</title></channel></rss>',
            headers={"content-type": "application/rss+xml; charset=utf-8"},
            request=request,
        )


class AlwaysFailAsyncClient:
    instance = None

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.requests = []
        AlwaysFailAsyncClient.instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout, follow_redirects, headers):
        self.requests.append(headers)
        raise RequestError("connection failed", request=Request("GET", url))


@pytest.mark.asyncio
async def test_fetch_feed_content_retries_with_next_header_set(monkeypatch):
    monkeypatch.setattr(feed_parser.httpx, "AsyncClient", RetrySuccessAsyncClient)

    content = await fetch_feed_content("https://example.com/feed.xml")

    client = RetrySuccessAsyncClient.instance
    assert content.startswith("<?xml")
    assert client is not None
    assert len(client.requests) == 2
    assert client.requests[0]["User-Agent"] != client.requests[1]["User-Agent"]
    assert "application/rss+xml" in client.requests[1]["Accept"]


@pytest.mark.asyncio
async def test_fetch_feed_content_reports_all_header_attempts(monkeypatch):
    monkeypatch.setattr(feed_parser.httpx, "AsyncClient", AlwaysFailAsyncClient)

    with pytest.raises(FeedParserError, match="after 3 header attempts"):
        await fetch_feed_content("https://example.com/feed.xml")

    client = AlwaysFailAsyncClient.instance
    assert client is not None
    assert len(client.requests) == 3
    assert len({request["User-Agent"] for request in client.requests}) == 3
