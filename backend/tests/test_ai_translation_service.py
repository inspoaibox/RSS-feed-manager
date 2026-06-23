"""Tests for AI translation helpers."""
from __future__ import annotations

import pytest

from app.services.ai_client import AIClientError, BaseAIClient
from app.services.ai_translation_service import (
    plain_text_to_html,
    select_translation_body_input,
    split_text_for_translation,
    translate_text_with_chunking,
)


class FakeAIClient(BaseAIClient):
    """A tiny fake client that truncates long requests."""

    def __init__(self, max_chars: int):
        self.max_chars = max_chars
        self.calls: list[str] = []

    async def list_models(self) -> list[dict]:
        return []

    async def translate(self, text: str, target_language: str, custom_prompt: str | None = None) -> str:
        self.calls.append(text)
        if len(text) > self.max_chars:
            raise AIClientError("AI response truncated (finish_reason=length)")
        return f"[{target_language}] {text}"

    async def summarize(self, text: str, custom_prompt: str | None = None) -> str:
        return text

    async def chat(self, prompt: str) -> str:
        return prompt

    async def test_connection(self) -> bool:
        return True


def test_select_translation_body_input_prefers_full_content() -> None:
    full_content = "完整正文\n\n第二段"
    html_content = "<p>摘要正文</p>"

    selected = select_translation_body_input(full_content, html_content)

    assert selected == full_content


def test_plain_text_to_html_preserves_paragraphs() -> None:
    translated = "第一段第一行\n第一段第二行\n\n第二段"

    html = plain_text_to_html(translated)

    assert html == "<p>第一段第一行<br>第一段第二行</p><p>第二段</p>"


def test_split_text_for_translation_respects_max_chars() -> None:
    text = "第一段。" * 20 + "\n\n" + "第二段。" * 20

    chunks = split_text_for_translation(text, max_chars=40)

    assert len(chunks) >= 2
    assert all(len(chunk) <= 40 for chunk in chunks)


@pytest.mark.asyncio
async def test_translate_text_with_chunking_retries_on_truncation() -> None:
    client = FakeAIClient(max_chars=40)
    text = (
        "第一段内容很长，需要拆分翻译。第一段内容很长，需要拆分翻译。\n\n"
        "第二段内容也很长，需要继续拆分翻译。第二段内容也很长，需要继续拆分翻译。"
    )

    translated = await translate_text_with_chunking(
        client,
        text,
        "zh-CN",
        max_chunk_chars=80,
        min_chunk_chars=20,
    )

    assert "[zh-CN]" in translated
    assert len(client.calls) > 1
    assert "第一段内容很长" in translated
    assert "第二段内容也很长" in translated
