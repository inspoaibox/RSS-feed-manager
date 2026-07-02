"""Utilities for monitoring WHMCS product availability pages."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup


WHMCS_STATUS_MARKER = "WHMCS_STATUS="


@dataclass(frozen=True)
class WhmcsProductState:
    """Normalized WHMCS product availability state."""

    title: str
    status: str
    status_label: str
    evidence: str


def parse_whmcs_product_state(html: str, target_url: str) -> WhmcsProductState:
    """Parse a WHMCS product/store page and detect availability.

    WHMCS templates vary heavily, so detection uses stable platform signals:
    explicit out-of-stock error/messages first, then order/configuration controls.
    """
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_product_title(soup, target_url)
    page_text = _compact_text(soup.get_text(" ", strip=True))
    lower_text = page_text.lower()

    out_of_stock_phrases = (
        "out of stock",
        "sold out",
        "currently unavailable",
        "orders for it have been suspended",
        "缺货",
        "售罄",
        "暂无库存",
        "已下架",
    )
    for phrase in out_of_stock_phrases:
        if phrase in lower_text:
            return WhmcsProductState(
                title=title,
                status="out_of_stock",
                status_label="下架/缺货",
                evidence=_find_evidence_text(soup, phrase) or phrase,
            )

    if _has_order_signal(soup):
        return WhmcsProductState(
            title=title,
            status="in_stock",
            status_label="上架/可购买",
            evidence="页面存在 WHMCS 下单/配置入口",
        )

    if _looks_like_whmcs(soup, html):
        raise ValueError("已识别为 WHMCS 页面，但没有找到上下架状态或下单入口")

    raise ValueError("未识别到 WHMCS 页面特征")


def build_whmcs_status_content(state: WhmcsProductState, target_url: str) -> str:
    """Build article content with a machine-readable status marker."""
    return (
        f"{WHMCS_STATUS_MARKER}{state.status}\n"
        f"产品：{state.title}\n"
        f"状态：{state.status_label}\n"
        f"证据：{state.evidence}\n"
        f"页面：{target_url}"
    )


def extract_whmcs_status_from_content(content: str | None) -> str | None:
    """Read the stored WHMCS status marker from an article body."""
    if not content:
        return None
    for line in content.splitlines():
        if line.startswith(WHMCS_STATUS_MARKER):
            status = line[len(WHMCS_STATUS_MARKER) :].strip()
            return status or None
    return None


def _looks_like_whmcs(soup: BeautifulSoup, html: str) -> bool:
    if "whmcsBaseUrl" in html or "csrfToken" in html:
        return True
    if soup.select_one('a[href*="cart.php"], form[action*="cart.php"]'):
        return True
    body_classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    return "page-order" in body_classes or "whmcs" in html.lower()


def _has_order_signal(soup: BeautifulSoup) -> bool:
    order_text_phrases = (
        "order now",
        "configure",
        "continue",
        "add to cart",
        "buy now",
        "checkout",
        "立即订购",
        "加入购物车",
        "购买",
        "配置",
        "继续",
    )

    for form in soup.select('form[action*="cart.php"], form[action*="cart"]'):
        form_text = form.get_text(" ", strip=True).lower()
        if any(phrase in form_text for phrase in order_text_phrases):
            return True
        if form.select_one('input[name="pid"], input[name="product"], input[name="a"]'):
            return True

    for element in soup.select("a[href], button, input[type=submit]"):
        href = element.get("href", "")
        if "cart.php?a=add" in href or "a=confproduct" in href or "pid=" in href:
            return True
        text = element.get_text(" ", strip=True) or element.get("value", "") or ""
        if any(phrase in text.lower() for phrase in order_text_phrases):
            return True

    return False


def _extract_product_title(soup: BeautifulSoup, target_url: str) -> str:
    meta_title = soup.select_one('meta[property="og:title"], meta[name="twitter:title"]')
    if meta_title and meta_title.get("content"):
        title = _clean_title(meta_title["content"])
        if title:
            return title

    for selector in (
        ".product-title",
        ".package-title",
        ".product-name",
        "h1",
        "h2",
    ):
        element = soup.select_one(selector)
        if not element:
            continue
        title = _clean_title(element.get_text(" ", strip=True))
        if title and title.lower() not in {"out of stock", "oops, there's a problem..."}:
            return title

    if soup.title:
        title = _clean_title(soup.title.get_text(" ", strip=True))
        if title and "shopping cart" not in title.lower():
            return title

    return _title_from_url(target_url)


def _title_from_url(target_url: str) -> str:
    parsed = urlparse(target_url)
    query = parse_qs(parsed.query)
    route = query.get("rp", [""])[0]
    path = route or parsed.path
    slug = unquote(path.rstrip("/").split("/")[-1])
    if not slug:
        return parsed.hostname or target_url
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def _clean_title(value: str) -> str:
    title = _compact_text(value)
    for separator in (" - ", " | "):
        if separator in title:
            title = title.split(separator, 1)[0].strip()
    return title[:120]


def _compact_text(value: str) -> str:
    return " ".join(value.split())


def _find_evidence_text(soup: BeautifulSoup, phrase: str) -> str | None:
    phrase_lower = phrase.lower()
    for text_node in soup.find_all(string=lambda value: value and phrase_lower in value.lower()):
        parent = text_node.parent
        if parent:
            text = _compact_text(parent.get_text(" ", strip=True))
            if text:
                return text[:300]
    return None
