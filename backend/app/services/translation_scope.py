"""Helpers for title/content translation scope."""

import json
from hashlib import sha256
from typing import Any

from app.services.ai_translation_service import (
    extract_text_from_html,
    select_translation_body_input,
)


def translation_targets_for_source(source: Any) -> tuple[bool, bool]:
    """Return whether title/content should be translated for a feed-like source."""
    translate_title = bool(getattr(source, "translate_title", True))
    translate_content = bool(getattr(source, "translate_content", False))

    if not translate_title and not translate_content:
        translate_title = True

    return translate_title, translate_content


def translation_inputs(article: Any) -> dict[str, str]:
    return {
        "title": extract_text_from_html(getattr(article, "title", None) or ""),
        "content": select_translation_body_input(
            getattr(article, "full_content", None), getattr(article, "content", None)
        ),
    }


def source_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def translation_parts(article: Any, source: Any, target: str) -> dict[str, str]:
    raw = getattr(article, "translation", None)
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        data = {"content": raw or ""}
    if not isinstance(data, dict):
        data = {}
    meta = data.get("_meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    revision = getattr(article, "translation_revision", 0) or 0
    known_target = meta.get("target_language", getattr(source, "target_language", target))
    if known_target != target or meta.get("revision", 0) != revision:
        return {"title": "", "content": ""}
    inputs = translation_inputs(article)
    return {
        part: data.get(part, "")
        if isinstance(data.get(part), str)
        and meta.get(part + "_hash", source_hash(inputs[part])) == source_hash(inputs[part])
        else ""
        for part in ("title", "content")
    }


def encode_translation(parts: dict, article: Any, target: str) -> str:
    inputs = translation_inputs(article)
    return json.dumps(
        {
            **parts,
            "_meta": {
                "target_language": target,
                "revision": getattr(article, "translation_revision", 0) or 0,
                "title_hash": source_hash(inputs["title"]),
                "content_hash": source_hash(inputs["content"]),
            },
        },
        ensure_ascii=False,
    )


def has_translatable_article_text(article: Any, source: Any, *, force_full=False) -> bool:
    title, content = (True, True) if force_full else translation_targets_for_source(source)
    inputs = translation_inputs(article)
    return bool((title and inputs["title"]) or (content and inputs["content"]))


def translation_satisfies_targets(
    translation: str | None, source: Any, *, article=None, target_language=None, force_full=False
) -> bool:
    if not translation:
        return False
    title, content = (True, True) if force_full else translation_targets_for_source(source)
    if article is not None:
        data = translation_parts(article, source, target_language or source.target_language)
        inputs = translation_inputs(article)
        title, content = title and bool(inputs["title"]), content and bool(inputs["content"])
    else:
        try:
            data = json.loads(translation)
        except (TypeError, json.JSONDecodeError):
            data = {"content": translation}
        if not isinstance(data, dict):
            return False
    return (not title or bool(data.get("title"))) and (not content or bool(data.get("content")))
