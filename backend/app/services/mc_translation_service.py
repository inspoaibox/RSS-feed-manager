"""Mc-Translation API client."""
from typing import Optional

import httpx


class McTranslationError(Exception):
    """Raised when Mc-Translation cannot complete a request."""


DEFAULT_BASE_URL = "https://fanyi.aboen.com"
DEFAULT_MODEL = "argos"

LANGUAGE_MAP = {
    "zh-CN": "zh",
    "zh-Hans": "zh",
    "zh": "zh",
    "zh-TW": "zt",
    "zh-Hant": "zt",
    "zt": "zt",
    "en-US": "en",
    "en-GB": "en",
    "en": "en",
    "ja": "ja",
    "jp": "ja",
    "ko": "ko",
    "kr": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ru": "ru",
    "ar": "ar",
    "hi": "hi",
    "th": "th",
    "pt": "pt",
    "it": "it",
    "nl": "nl",
    "tr": "tr",
    "vi": "vi",
    "id": "id",
    "fa": "fa",
    "pl": "pl",
    "uk": "uk",
    "sv": "sv",
    "ms": "ms",
}


def normalize_mc_language(language: str | None, default: str = "en") -> str:
    normalized = (language or default).strip()
    if not normalized:
        normalized = default
    return LANGUAGE_MAP.get(normalized, LANGUAGE_MAP.get(normalized.lower(), normalized.lower()))


def _translate_url(base_url: str | None) -> str:
    url = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if not url:
        url = DEFAULT_BASE_URL
    return url if url.endswith("/translate") else f"{url}/translate"


class McTranslationService:
    """Translate text with a Mc-Translation compatible API."""

    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        source_language: Optional[str] = None,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url or DEFAULT_BASE_URL
        self.model = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self.source_language = normalize_mc_language(source_language, default="en")

    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        if not text or not text.strip():
            return text
        if not self.api_key:
            raise McTranslationError("Mc-Translation API Key is not configured")

        source = normalize_mc_language(source_language, default=self.source_language)
        target = normalize_mc_language(target_language, default="zh")
        if source == target:
            return text

        payload = {
            "text": text,
            "source_lang": source,
            "target_lang": target,
            "model": self.model,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    _translate_url(self.base_url),
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                detail = exc.response.json().get("detail", detail)
            except ValueError:
                pass
            raise McTranslationError(
                f"Mc-Translation API error: {exc.response.status_code} - {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise McTranslationError(f"Mc-Translation request error: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise McTranslationError("Mc-Translation returned invalid JSON") from exc

        if data.get("success") is False:
            raise McTranslationError(str(data.get("detail") or "Mc-Translation failed"))

        translated = data.get("translated_text")
        if not isinstance(translated, str):
            raise McTranslationError("Mc-Translation response missing translated_text")
        return translated

    async def translate_article(
        self,
        title: str,
        content: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> tuple[str, str]:
        translated_title = (
            await self.translate(title, target_language, source_language)
            if title
            else ""
        )
        translated_content = (
            await self.translate(content, target_language, source_language)
            if content
            else ""
        )
        return translated_title, translated_content
