"""Helpers for AI article translation with long-text chunking."""
from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup

from app.services.ai_client import AIClientError, BaseAIClient

AI_TRANSLATION_MAX_CHARS = 3500
AI_TRANSLATION_MIN_CHARS = 800
_BLOCK_TAGS = ["p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br"]


def extract_text_from_html(html_content: str) -> str:
    """Extract readable plain text while preserving paragraph structure."""
    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    text = soup.get_text()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def select_translation_body_input(full_content: str | None, content: str | None) -> str:
    """Choose the best body text source for AI translation."""
    preferred = (full_content or "").strip()
    if preferred:
        return preferred

    fallback = (content or "").strip()
    if not fallback:
        return ""

    extracted = extract_text_from_html(fallback)
    return extracted or fallback


def plain_text_to_html(text: str) -> str:
    """Convert translated plain text into simple safe HTML paragraphs."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", normalized) if paragraph.strip()]
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

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", normalized) if paragraph.strip()]
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
    return "finish_reason=length" in message or "finish_reason=max_tokens" in message or "truncated" in message


async def translate_text_with_chunking(
    client: BaseAIClient,
    text: str,
    target_language: str,
    custom_prompt: str | None = None,
    *,
    max_chunk_chars: int = AI_TRANSLATION_MAX_CHARS,
    min_chunk_chars: int = AI_TRANSLATION_MIN_CHARS,
) -> str:
    """Translate text, automatically chunking and retrying on truncation."""
    normalized = text.strip()
    if not normalized:
        return ""

    if len(normalized) <= max_chunk_chars:
        try:
            return await client.translate(normalized, target_language, custom_prompt)
        except AIClientError as exc:
            if not is_translation_truncation_error(exc) or max_chunk_chars <= min_chunk_chars:
                raise

    split_limit = max_chunk_chars if len(normalized) > max_chunk_chars else max(min_chunk_chars, max_chunk_chars // 2)
    chunks = split_text_for_translation(normalized, split_limit)

    if len(chunks) <= 1:
        if split_limit <= min_chunk_chars:
            return await client.translate(normalized, target_language, custom_prompt)
        chunks = _hard_wrap_text(normalized, max(min_chunk_chars, split_limit // 2))

    translated_chunks: list[str] = []
    for chunk in chunks:
        translated = await translate_text_with_chunking(
            client,
            chunk,
            target_language,
            custom_prompt,
            max_chunk_chars=split_limit,
            min_chunk_chars=min_chunk_chars,
        )
        if translated.strip():
            translated_chunks.append(translated.strip())

    return "\n\n".join(translated_chunks)


def _split_oversized_piece(text: str, max_chars: int) -> list[str]:
    """Split one oversized paragraph into smaller sentence-aware pieces."""
    if len(text) <= max_chars:
        return [text]

    sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？.!?])\s+", text) if sentence.strip()]
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
