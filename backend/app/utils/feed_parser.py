"""RSS/Atom feed parser utilities."""
from dataclasses import dataclass
from datetime import datetime
from typing import List

import feedparser
import httpx
from feedparser import FeedParserDict


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


async def fetch_feed_content(url: str, timeout: float = 30.0) -> str:
    """Fetch feed content from URL."""
    # 模拟真实浏览器的完整请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            )
            response.raise_for_status()
            return response.text
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
    # Get GUID (unique identifier)
    guid = entry.get("id") or entry.get("link") or entry.get("title")
    if not guid:
        return None
    
    # Get title
    title = entry.get("title", "Untitled")
    
    # Get link
    link = entry.get("link", "")
    
    # Get content (prefer full content over summary)
    content = None
    if "content" in entry and entry.content:
        content = entry.content[0].get("value", "")
    elif "summary" in entry:
        content = entry.summary
    elif "description" in entry:
        content = entry.description
    
    # Get author
    author = entry.get("author")
    if not author and "authors" in entry and entry.authors:
        author = entry.authors[0].get("name")
    
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


async def fetch_feed_content_playwright(url: str, timeout: float = 60.0) -> str:
    """Fetch feed content using Playwright browser automation (for Cloudflare protected sites)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise FeedParserError("Playwright not installed. Run: pip install playwright && playwright install chromium")
    
    response_body = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
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
            
            # Navigate and wait for content
            response = await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            
            # 如果拦截没有获取到，尝试从响应直接获取
            if not response_body and response:
                try:
                    response_body = await response.text()
                except:
                    pass
            
            # 如果还是没有，等待一下再获取页面内容
            if not response_body:
                await page.wait_for_timeout(3000)
                response_body = await page.content()
            
            await browser.close()
            
            if not response_body:
                raise FeedParserError(f"Failed to get content from: {url}")
            
            # Check if we got actual RSS/XML content or still a challenge page
            if "Just a moment" in response_body or "challenge-platform" in response_body:
                raise FeedParserError(f"Cloudflare challenge not bypassed: {url}")
            
            return response_body
    except Exception as e:
        if "FeedParserError" in str(type(e)):
            raise
        raise FeedParserError(f"Playwright error: {str(e)}")


async def parse_feed(url: str, use_playwright: bool = False) -> ParsedFeed:
    """Fetch and parse a feed from URL."""
    if use_playwright:
        content = await fetch_feed_content_playwright(url)
    else:
        content = await fetch_feed_content(url)
    return parse_feed_content(content, url)
