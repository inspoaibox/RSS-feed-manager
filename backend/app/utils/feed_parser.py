"""RSS/Atom feed parser utilities."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from typing import List
from urllib.parse import unquote, urlparse, urlunparse

import feedparser
import httpx
from feedparser import FeedParserDict

FeedBrowserEngine = Literal["http", "playwright", "cloakbrowser"]


@dataclass
class ParsedArticle:
    """Parsed article from feed."""
    guid: str
    title: str
    link: str
    content: str | None
    author: str | None
    published_at: datetime | None


@dataclass
class ParsedFeed:
    """Parsed feed information."""
    title: str
    description: str | None
    site_url: str | None
    icon_url: str | None
    articles: List[ParsedArticle]


class FeedParserError(Exception):
    """Exception raised when feed parsing fails."""
    pass


def normalize_browser_engine(
    browser_engine: str | None = None,
    use_playwright: bool = False,
) -> FeedBrowserEngine:
    """Resolve legacy use_playwright into the newer browser engine value."""
    if browser_engine:
        normalized = browser_engine.strip().lower()
        if normalized in {"http", "playwright", "cloakbrowser"}:
            return normalized  # type: ignore[return-value]
        raise FeedParserError(f"Unsupported feed browser engine: {browser_engine}")
    return "playwright" if use_playwright else "http"


def is_browser_engine_enabled(browser_engine: str | None = None, use_playwright: bool = False) -> bool:
    """Return whether the feed should use a browser-backed fetcher."""
    return normalize_browser_engine(browser_engine, use_playwright) != "http"


def _ensure_not_blocked_challenge(content: str, url: str, engine_name: str) -> str:
    """Return content unless it is still a Cloudflare challenge page."""
    if not content:
        raise FeedParserError(f"Failed to get content from: {url}")

    has_feed = any(marker in content.lower() for marker in ['<rss', '<feed', '<?xml', '<atom'])

    if not has_feed:
        blocking_patterns = [
            "Just a moment",
            "challenge-platform",
            "cf-browser-verification",
            "Checking your browser",
            "Enable JavaScript and cookies to continue"
        ]

        if any(pattern in content for pattern in blocking_patterns):
            preview = content[:500].replace('\n', ' ')
            raise FeedParserError(
                f"Cloudflare challenge not bypassed by {engine_name}: {url} "
                f"(Preview: {preview}...)"
            )

    return content


def _detect_encoding(content: bytes, content_type: str | None = None) -> str:
    """Detect encoding from content and headers."""
    import re
    
    # 1. 尝试从 Content-Type header 获取编码
    if content_type:
        match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
        if match:
            return match.group(1).strip('"\'')
    
    # 2. 尝试从 XML 声明获取编码
    # 先用 ascii 解码前 200 字节来查找 encoding 声明
    try:
        header = content[:200].decode('ascii', errors='ignore')
        match = re.search(r'encoding=["\']([^"\']+)["\']', header, re.IGNORECASE)
        if match:
            return match.group(1)
    except:
        pass
    
    # 3. 常见中文网站编码检测
    # 检查是否包含 GBK/GB2312 特征字节
    try:
        content.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        # 尝试 GBK (兼容 GB2312)
        try:
            content.decode('gbk')
            return 'gbk'
        except UnicodeDecodeError:
            pass
    
    # 4. 默认 UTF-8
    return 'utf-8'


def _build_playwright_proxy(proxy_url: str | None) -> dict | None:
    """Convert a proxy URL into Playwright's proxy configuration."""
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    server = urlunparse((parsed.scheme, f"{hostname}{port}", "", "", "", ""))
    proxy_config = {"server": server}

    if parsed.username:
        proxy_config["username"] = unquote(parsed.username)
    if parsed.password:
        proxy_config["password"] = unquote(parsed.password)

    return proxy_config


async def fetch_feed_content(
    url: str,
    timeout: float = 30.0,
    proxy_url: str | None = None,
) -> str:
    """Fetch feed content from URL."""
    # 简化请求头，不请求压缩以避免解压问题
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }
    
    async with httpx.AsyncClient(proxy=proxy_url) as client:
        try:
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            )
            response.raise_for_status()
            
            # 获取原始字节内容
            raw_content = response.content
            content_type = response.headers.get('content-type', '')
            
            # 检测并使用正确的编码
            encoding = _detect_encoding(raw_content, content_type)
            
            try:
                return raw_content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                # 如果检测的编码失败，尝试常见编码
                for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']:
                    try:
                        return raw_content.decode(enc)
                    except (UnicodeDecodeError, LookupError):
                        continue
                # 最后使用 errors='replace' 强制解码
                return raw_content.decode('utf-8', errors='replace')
                
        except httpx.TimeoutException:
            raise FeedParserError(f"Timeout fetching feed: {url}")
        except httpx.HTTPStatusError as e:
            raise FeedParserError(f"HTTP error {e.response.status_code}: {url}")
        except httpx.RequestError as e:
            raise FeedParserError(f"Request error: {str(e)}")


def parse_feed_content(content: str, feed_url: str) -> ParsedFeed:
    """Parse feed content and extract information."""
    parsed: FeedParserDict = feedparser.parse(content)
    
    if parsed.bozo and not parsed.entries:
        raise FeedParserError(f"Invalid feed format: {parsed.bozo_exception}")
    
    feed = parsed.feed
    
    # Extract feed metadata
    title = feed.get("title", "Untitled Feed")
    description = feed.get("description") or feed.get("subtitle")
    site_url = feed.get("link")
    
    # Try to get feed icon
    icon_url = None
    if hasattr(feed, "image") and feed.image:
        icon_url = feed.image.get("href") or feed.image.get("url")
    
    # Parse articles
    articles = []
    for entry in parsed.entries:
        article = _parse_entry(entry)
        if article:
            articles.append(article)
    
    return ParsedFeed(
        title=title,
        description=description,
        site_url=site_url,
        icon_url=icon_url,
        articles=articles
    )


def _parse_entry(entry: dict) -> ParsedArticle | None:
    """Parse a single feed entry."""
    # Get GUID (unique identifier) - truncate to 2048 chars
    guid = entry.get("id") or entry.get("link") or entry.get("title")
    if not guid:
        return None
    if len(guid) > 2048:
        guid = guid[:2048]
    
    # Get title - truncate to 500 chars
    title = entry.get("title", "Untitled")
    if len(title) > 500:
        title = title[:497] + "..."
    
    # Get link - truncate to 2048 chars
    link = entry.get("link", "")
    if link and len(link) > 2048:
        link = link[:2048]
    
    # Get content (prefer full content over summary)
    content = None
    if "content" in entry and entry.content:
        content = entry.content[0].get("value", "")
    elif "summary" in entry:
        content = entry.summary
    elif "description" in entry:
        content = entry.description
    
    # Get author (truncate to 500 chars to avoid DB errors)
    author = entry.get("author")
    if not author and "authors" in entry and entry.authors:
        author = entry.authors[0].get("name")
    if author and len(author) > 500:
        author = author[:500]
    
    # Get published date
    # feedparser returns time in UTC as a time.struct_time
    published_at = None
    if "published_parsed" in entry and entry.published_parsed:
        try:
            # Convert struct_time to datetime (feedparser returns UTC)
            import calendar
            timestamp = calendar.timegm(entry.published_parsed)
            published_at = datetime.utcfromtimestamp(timestamp)
        except (TypeError, ValueError, OverflowError):
            pass
    elif "updated_parsed" in entry and entry.updated_parsed:
        try:
            import calendar
            timestamp = calendar.timegm(entry.updated_parsed)
            published_at = datetime.utcfromtimestamp(timestamp)
        except (TypeError, ValueError, OverflowError):
            pass
    
    return ParsedArticle(
        guid=guid,
        title=title,
        link=link,
        content=content,
        author=author,
        published_at=published_at
    )


async def fetch_feed_content_playwright(
    url: str,
    timeout: float = 90.0,
    proxy_url: str | None = None,
) -> str:
    """Fetch feed content using Playwright browser automation (for Cloudflare protected sites)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise FeedParserError("Playwright not installed. Run: pip install playwright && playwright install chromium")

    from app.core.config import settings

    response_body = None
    browser = None
    context = None

    try:
        async with async_playwright() as p:
            launch_kwargs = {
                "headless": settings.FEED_BROWSER_HEADLESS,
                "args": [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ],
            }
            playwright_proxy = _build_playwright_proxy(proxy_url)
            if playwright_proxy:
                launch_kwargs["proxy"] = playwright_proxy

            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
            )

            # Add stealth scripts
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
            """)

            page = await context.new_page()

            # 拦截响应获取原始内容
            async def handle_response(response):
                nonlocal response_body
                if response.url == url or response.url.rstrip('/') == url.rstrip('/'):
                    try:
                        response_body = await response.text()
                    except:
                        pass

            page.on("response", handle_response)

            # Navigate and wait for network idle (Cloudflare redirect)
            response = await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

            # 如果拦截没有获取到，尝试从响应直接获取
            if not response_body and response:
                try:
                    response_body = await response.text()
                except:
                    pass

            # 如果还是没有，获取页面内容
            if not response_body:
                response_body = await page.content()

            return _ensure_not_blocked_challenge(response_body, url, "Playwright")
    except Exception as e:
        if "FeedParserError" in str(type(e)):
            raise
        raise FeedParserError(f"Playwright error: {str(e)}")
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


async def fetch_feed_content_cloakbrowser(
    url: str,
    timeout: float = 90.0,
    proxy_url: str | None = None,
) -> str:
    """Fetch feed content using CloakBrowser's browser backend."""
    try:
        import cloakbrowser
    except ImportError:
        raise FeedParserError("CloakBrowser not installed. Run: pip install cloakbrowser")

    from app.core.config import settings

    response_body = None
    browser = None
    context = None

    async def _launch_context():
        api = getattr(cloakbrowser, "CloakBrowser", cloakbrowser)
        launch_context_async = getattr(api, "launch_context_async", None)
        launch_persistent_context_async = getattr(api, "launch_persistent_context_async", None)

        if not launch_context_async and not launch_persistent_context_async:
            raise FeedParserError(
                "CloakBrowser API not found. Expected launch_context_async()."
            )

        launch_kwargs = {
            "headless": settings.FEED_BROWSER_HEADLESS,
            "humanize": settings.CLOAKBROWSER_HUMANIZE,
            "geoip": settings.CLOAKBROWSER_GEOIP,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone": "America/New_York",
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        }
        effective_proxy = proxy_url or settings.CLOAKBROWSER_PROXY
        if effective_proxy:
            launch_kwargs["proxy"] = effective_proxy

        async def call_launcher(launcher, *args):
            try:
                return await launcher(*args, **launch_kwargs)
            except TypeError:
                fallback_kwargs = {"headless": settings.FEED_BROWSER_HEADLESS}
                if effective_proxy:
                    fallback_kwargs["proxy"] = effective_proxy
                return await launcher(*args, **fallback_kwargs)

        if settings.CLOAKBROWSER_USER_DATA_DIR:
            if not launch_persistent_context_async:
                raise FeedParserError(
                    "CloakBrowser persistent context API not found. "
                    "Disable CLOAKBROWSER_USER_DATA_DIR or upgrade CloakBrowser."
                )
            result = await call_launcher(
                launch_persistent_context_async,
                settings.CLOAKBROWSER_USER_DATA_DIR,
            )
        else:
            result = await call_launcher(launch_context_async)

        if isinstance(result, tuple):
            if len(result) >= 2:
                return result[0], result[1]
            if len(result) == 1:
                return None, result[0]

        return None, result

    try:
        browser, context = await _launch_context()
        page = await context.new_page()
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
        except Exception:
            pass

        async def handle_response(response):
            nonlocal response_body
            if response.url == url or response.url.rstrip('/') == url.rstrip('/'):
                try:
                    response_body = await response.text()
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        response = await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
        if not response_body and response:
            try:
                response_body = await response.text()
            except Exception:
                pass

        if not response_body:
            response_body = await page.content()

        return _ensure_not_blocked_challenge(response_body, url, "CloakBrowser")
    except Exception as e:
        if "FeedParserError" in str(type(e)):
            raise
        raise FeedParserError(f"CloakBrowser error: {str(e)}")
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


async def parse_feed(
    url: str,
    use_playwright: bool = False,
    browser_engine: str | None = None,
    proxy_url: str | None = None,
) -> ParsedFeed:
    """Fetch and parse a feed from URL."""
    engine = normalize_browser_engine(browser_engine, use_playwright)
    if engine == "playwright":
        content = await fetch_feed_content_playwright(url, proxy_url=proxy_url)
    elif engine == "cloakbrowser":
        content = await fetch_feed_content_cloakbrowser(url, proxy_url=proxy_url)
    else:
        content = await fetch_feed_content(url, proxy_url=proxy_url)
    return parse_feed_content(content, url)
