"""Helpers for AI article translation with long-text chunking."""

from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup

from app.services.ai_client import AIClientError, BaseAIClient, translation_prompt

AI_TRANSLATION_MAX_CHARS = 3500
AI_TRANSLATION_MIN_CHARS = 800
_BLOCK_TAGS = [
    "p",
    "div",
    "section",
    "article",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "tr",
    "br",
]


def extract_text_from_html(html_content: str) -> str:
    """Extract readable plain text while preserving paragraph structure."""
    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style", "noscript", "template", "svg", "iframe", "head"]):
        tag.decompose()

    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    text = soup.get_text()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"data:[^\s<>]+;base64,[A-Za-z0-9+/=]+", "", text)
    return text.strip()


def select_translation_body_input(full_content: str | None, content: str | None) -> str:
    """Choose the best body text source for AI translation."""
    for value in (full_content, content):
        if value and value.strip():
            extracted = extract_text_from_html(value)
            if extracted:
                return extracted
    return ""


def plain_text_to_html(text: str) -> str:
    """Convert translated plain text into simple safe HTML paragraphs."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    paragraphs = [
        paragraph.strip() for paragraph in re.split(r"\n{2,}", normalized) if paragraph.strip()
    ]
    html_parts: list[str] = []
    for paragraph in paragraphs:
        lines = [html.escape(line.strip()) for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        html_parts.append(f"<p>{'<br>'.join(lines)}</p>")
    return "".join(html_parts)


def split_text_for_translation(text: str, max_chars: int = AI_TRANSLATION_MAX_CHARS) -> list[str]:
    """Split long text into translation-friendly chunks."""
    normalized = text.strip()
    if not normalized:
        return []

    paragraphs = [
        paragraph.strip() for paragraph in re.split(r"\n{2,}", normalized) if paragraph.strip()
    ]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        for piece in _split_oversized_piece(paragraph, max_chars):
            separator = 2 if current else 0
            projected_length = current_length + separator + len(piece)
            if current and projected_length > max_chars:
                chunks.append("\n\n".join(current))
                current = [piece]
                current_length = len(piece)
            else:
                current.append(piece)
                current_length = projected_length

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def is_translation_truncation_error(error: Exception) -> bool:
    """Return whether an AI client error indicates a truncated response."""
    message = str(error).lower()
    return (
        "finish_reason=length" in message
        or "finish_reason=max_tokens" in message
        or "truncated" in message
    )


def _split_by_bytes(text: str, limit: int) -> list[str]:
    chunks = []
    while len(text.encode("utf-8")) > limit:
        used = 0
        index = 0
        for char in text:
            size = len(char.encode("utf-8"))
            if used + size > limit:
                break
            used += size
            index += 1
        if not index:
            raise AIClientError("输入预算不足以容纳正文，请缩短提示词或提高预算")
        boundary = text.rfind(" ", 0, index + 1)
        if boundary >= index // 2:
            index = max(boundary, 1)
        chunks.append(text[:index].strip())
        text = text[index:].strip()
    if text:
        chunks.append(text)
    return chunks


async def translate_text_with_chunking(
    client: BaseAIClient,
    text: str,
    target_language: str,
    custom_prompt: str | None = None,
    *,
    max_chunk_chars: int = AI_TRANSLATION_MAX_CHARS,
    min_chunk_chars: int = AI_TRANSLATION_MIN_CHARS,
) -> str:
    """Retry only strictly smaller pieces; completed pieces are checkpointed by the client."""
    normalized = text.strip()
    if not normalized:
        return ""
    if min(max_chunk_chars, min_chunk_chars) <= 0:
        raise ValueError("Chunk limits must be positive")
    chunks = split_text_for_translation(normalized, max_chunk_chars)
    input_limit = getattr(client, "max_input_tokens", None)
    if input_limit is not None:
        overhead = len(translation_prompt(custom_prompt, target_language).encode("utf-8")) + 64
        budget = input_limit - overhead
        if budget < 16:
            raise AIClientError("提示词已占满输入预算，请缩短提示词或提高预算")
        chunks = [piece for chunk in chunks for piece in _split_by_bytes(chunk, budget)]

    async def translate_piece(piece: str) -> str:
        try:
            return await client.translate(piece, target_language, custom_prompt)
        except AIClientError as exc:
            if not is_translation_truncation_error(exc):
                raise
            if len(piece) <= min_chunk_chars:
                raise AIClientError(
                    "AI response truncated：短分段输出仍被截断，请提高输出上限或更换模型"
                ) from exc
            smaller = _hard_wrap_text(piece, max(1, len(piece) // 2))
            if len(smaller) < 2 or any(len(part) >= len(piece) for part in smaller):
                raise
            translated = []
            for part in smaller:
                translated.append(await translate_piece(part))
            return "\n\n".join(translated)

    translated = []
    for chunk in chunks:
        translated.append(await translate_piece(chunk))
    return "\n\n".join(translated)


def _split_oversized_piece(text: str, max_chars: int) -> list[str]:
    """Split one oversized paragraph into smaller sentence-aware pieces."""
    if len(text) <= max_chars:
        return [text]

    sentences = [
        sentence.strip() for sentence in re.split(r"(?<=[。！？.!?])\s+", text) if sentence.strip()
    ]
    if len(sentences) > 1:
        pieces: list[str] = []
        current: list[str] = []
        current_length = 0
        for sentence in sentences:
            separator = 1 if current else 0
            projected_length = current_length + separator + len(sentence)
            if current and projected_length > max_chars:
                pieces.append(" ".join(current))
                current = [sentence]
                current_length = len(sentence)
            else:
                current.append(sentence)
                current_length = projected_length
        if current:
            pieces.append(" ".join(current))

        flattened: list[str] = []
        for piece in pieces:
            if len(piece) > max_chars:
                flattened.extend(_hard_wrap_text(piece, max_chars))
            else:
                flattened.append(piece)
        return flattened

    return _hard_wrap_text(text, max_chars)


def _hard_wrap_text(text: str, max_chars: int) -> list[str]:
    """Fallback splitter for text without useful paragraph or sentence boundaries."""
    remaining = text.strip()
    chunks: list[str] = []

    while len(remaining) > max_chars:
        split_at = remaining.rfind(" ", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks
