"""OPML import/export utilities."""
from dataclasses import dataclass
from typing import List
from xml.etree import ElementTree as ET


@dataclass
class OPMLFeed:
    """Feed entry from OPML."""
    title: str
    url: str
    site_url: str | None
    category: str | None


@dataclass
class OPMLCategory:
    """Category from OPML."""
    name: str
    feeds: List[OPMLFeed]


class OPMLParseError(Exception):
    """Exception raised when OPML parsing fails."""
    pass


def parse_opml(content: str) -> List[OPMLFeed]:
    """Parse OPML content and extract feeds."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise OPMLParseError(f"Invalid OPML format: {str(e)}")
    
    body = root.find("body")
    if body is None:
        raise OPMLParseError("OPML missing body element")
    
    feeds = []
    _parse_outlines(body, feeds, None)
    
    return feeds


def _parse_outlines(
    element: ET.Element,
    feeds: List[OPMLFeed],
    current_category: str | None
) -> None:
    """Recursively parse outline elements."""
    for outline in element.findall("outline"):
        # Check if this is a feed or a category
        xml_url = outline.get("xmlUrl")
        
        if xml_url:
            # This is a feed
            feed = OPMLFeed(
                title=outline.get("title") or outline.get("text") or "Untitled",
                url=xml_url,
                site_url=outline.get("htmlUrl"),
                category=current_category
            )
            feeds.append(feed)
        else:
            # This might be a category (folder)
            category_name = outline.get("title") or outline.get("text")
            if category_name:
                _parse_outlines(outline, feeds, category_name)
            else:
                _parse_outlines(outline, feeds, current_category)


def generate_opml(
    feeds: List[dict],
    title: str = "RSS Manager Subscriptions"
) -> str:
    """Generate OPML content from feeds.
    
    Args:
        feeds: List of dicts with keys: title, url, site_url, category
        title: Title for the OPML document
    
    Returns:
        OPML XML string
    """
    # Create root element
    opml = ET.Element("opml", version="2.0")
    
    # Create head
    head = ET.SubElement(opml, "head")
    title_elem = ET.SubElement(head, "title")
    title_elem.text = title
    
    # Create body
    body = ET.SubElement(opml, "body")
    
    # Group feeds by category
    categories: dict[str | None, List[dict]] = {}
    for feed in feeds:
        cat = feed.get("category")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(feed)
    
    # Add feeds without category first
    if None in categories:
        for feed in categories[None]:
            _add_feed_outline(body, feed)
    
    # Add categorized feeds
    for cat_name, cat_feeds in categories.items():
        if cat_name is None:
            continue
        
        cat_outline = ET.SubElement(body, "outline", text=cat_name, title=cat_name)
        for feed in cat_feeds:
            _add_feed_outline(cat_outline, feed)
    
    # Generate XML string
    return ET.tostring(opml, encoding="unicode", xml_declaration=True)


def _add_feed_outline(parent: ET.Element, feed: dict) -> None:
    """Add a feed outline element."""
    attrs = {
        "type": "rss",
        "text": feed.get("title", "Untitled"),
        "title": feed.get("title", "Untitled"),
        "xmlUrl": feed.get("url", ""),
    }
    
    if feed.get("site_url"):
        attrs["htmlUrl"] = feed["site_url"]
    
    ET.SubElement(parent, "outline", **attrs)
