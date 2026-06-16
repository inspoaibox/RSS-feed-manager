"""Helpers for title/content translation scope."""
import json
from typing import Any


def translation_targets_for_source(source: Any) -> tuple[bool, bool]:
    """Return whether title/content should be translated for a feed-like source."""
    translate_title = bool(getattr(source, "translate_title", True))
    translate_content = bool(getattr(source, "translate_content", False))

    if not translate_title and not translate_content:
        translate_title = True

    return translate_title, translate_content


def has_translatable_article_text(article: Any, source: Any) -> bool:
    """Return whether the article has text for the configured translation scope."""
    translate_title, translate_content = translation_targets_for_source(source)
    return bool(
        (translate_title and (getattr(article, "title", None) or "").strip())
        or (translate_content and (getattr(article, "content", None) or "").strip())
    )


def translation_satisfies_targets(translation: str | None, source: Any) -> bool:
    """Return whether a stored translation already covers the configured scope."""
    if not translation:
        return False

    translate_title, translate_content = translation_targets_for_source(source)
    try:
        data = json.loads(translation)
    except (TypeError, json.JSONDecodeError):
        return bool(translation.strip()) if translate_content and not translate_title else False

    if translate_title and not data.get("title"):
        return False
    if translate_content and not data.get("content"):
        return False
    return True
