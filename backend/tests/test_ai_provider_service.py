"""Tests for AI provider validation helpers."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.ai_service import _normalize_provider_base_url


def test_openai_compatible_requires_base_url() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _normalize_provider_base_url("openai_compatible", "", required=True)

    assert exc_info.value.status_code == 400
    assert "Base URL" in str(exc_info.value.detail)


def test_openai_compatible_requires_http_scheme() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _normalize_provider_base_url("openai_compatible", "api.example.com/v1", required=True)

    assert exc_info.value.status_code == 400
    assert "http" in str(exc_info.value.detail)


def test_openai_compatible_normalizes_trailing_slash() -> None:
    normalized = _normalize_provider_base_url(
        "openai_compatible",
        "https://api.example.com/v1/",
        required=True,
    )

    assert normalized == "https://api.example.com/v1"


def test_openai_compatible_appends_v1_when_missing() -> None:
    normalized = _normalize_provider_base_url(
        "openai_compatible",
        "https://api.example.com",
        required=True,
    )

    assert normalized == "https://api.example.com/v1"


def test_openai_compatible_appends_v1_to_custom_prefix() -> None:
    normalized = _normalize_provider_base_url(
        "openai_compatible",
        "https://dashscope.aliyuncs.com/compatible-mode",
        required=True,
    )

    assert normalized == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_openai_compatible_rejects_endpoint_url() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _normalize_provider_base_url(
            "openai_compatible",
            "https://api.example.com/v1/chat/completions",
            required=True,
        )

    assert exc_info.value.status_code == 400
    assert "API 根路径" in str(exc_info.value.detail)


def test_non_compatible_provider_ignores_base_url() -> None:
    normalized = _normalize_provider_base_url("openai", "https://proxy.example.com/v1", required=False)

    assert normalized is None
