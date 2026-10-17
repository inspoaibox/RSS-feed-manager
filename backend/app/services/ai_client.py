"""AI client adapters for different providers."""

from abc import ABC, abstractmethod
from inspect import isawaitable

import httpx

# 默认 Prompt 模板
DEFAULT_PROMPTS = {
    "translate": (
        "You are a translator. Translate the following text to {target_language}. "
        "Keep the original paragraph structure and formatting. "
        "Only output the translation, nothing else."
    ),
    "summarize": """You are a content organizer.
Please organize and summarize the following article content:

1. Extract the key points and main ideas
2. Organize the information in a clear, structured format
3. Use bullet points or numbered lists where appropriate
4. Keep the summary concise but comprehensive
5. Output in the same language as the input text

Only output the organized summary, nothing else.""",
}

# 运行时 Prompt（可被用户设置覆盖）
PROMPTS = DEFAULT_PROMPTS.copy()


class AIClientError(Exception):
    """Exception raised when AI client operation fails."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def translation_prompt(custom_prompt: str | None, target_language: str) -> str:
    template = custom_prompt or PROMPTS["translate"]
    # Only substitute the documented placeholder; JSON braces remain literal.
    if "{target_language}" in template:
        return template.replace("{target_language}", target_language)
    return f"{template}\nTarget language: {target_language}."


def _raise_if_truncated(finish_reason: str | None) -> None:
    """Raise a typed client error when the model output was cut short."""
    normalized = (finish_reason or "").strip().lower()
    if normalized in {"length", "max_tokens"}:
        raise AIClientError(f"AI response truncated (finish_reason={finish_reason})")


def completion_text(result: dict, *, gemini: bool = False) -> str:
    if not isinstance(result, dict):
        raise AIClientError("AI 服务返回了无效响应")
    choices = result.get("candidates" if gemini else "choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AIClientError("AI response did not include any choices")
    choice = choices[0]
    _raise_if_truncated(choice.get("finishReason" if gemini else "finish_reason"))
    if gemini:
        content = choice.get("content") or {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        text = "".join(
            p["text"]
            for p in parts
            if isinstance(p, dict) and isinstance(p.get("text"), str) and not p.get("thought")
        )
    else:
        message = choice.get("message") or {}
        text = message.get("content") if isinstance(message, dict) else None
        if isinstance(text, list):
            text = "".join(
                p["text"]
                for p in text
                if isinstance(p, dict)
                and p.get("type") == "text"
                and isinstance(p.get("text"), str)
            )
    if not isinstance(text, str) or not text.strip():
        raise AIClientError("AI response did not include translated content")
    return text.strip()


class BaseAIClient(ABC):
    """Base class for AI clients."""

    async def _generate(self, endpoint: str, data: dict) -> dict:
        recorder = getattr(self, "recorder", None)
        if recorder:
            cached = recorder.begin(endpoint, data)
            if isawaitable(cached):
                cached = await cached
            if cached is not None:
                return cached
        try:
            result = await self._request(endpoint, data)
        except Exception as exc:
            if recorder:
                outcome = recorder.fail(exc)
                if isawaitable(outcome):
                    await outcome
            raise
        if recorder:
            outcome = recorder.finish(result)
            if isawaitable(outcome):
                await outcome
        return result

    @abstractmethod
    async def list_models(self) -> list[dict]:
        """List available models."""
        pass

    @abstractmethod
    async def translate(
        self, text: str, target_language: str, custom_prompt: str | None = None
    ) -> str:
        """Translate text to target language."""
        pass

    @abstractmethod
    async def summarize(self, text: str, custom_prompt: str | None = None) -> str:
        """Generate summary of text."""
        pass

    @abstractmethod
    async def chat(self, prompt: str) -> str:
        """Send a chat message and get response."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection is valid."""
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI API client."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "gpt-3.5-turbo",
        *,
        max_output_tokens: int = 4096,
        max_input_tokens: int = 12000,
        token_limit_parameter: str = "max_tokens",
        recorder=None,
    ):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.max_input_tokens = max_input_tokens
        self.token_limit_parameter = token_limit_parameter
        self.recorder = recorder

    async def _request(self, endpoint: str, data: dict | None = None, method: str = "POST") -> dict:
        """Make request to OpenAI API."""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            url = f"{self.base_url.rstrip('/')}/{endpoint}"

            try:
                if method == "GET":
                    response = await client.get(url, headers=headers, timeout=30.0)
                else:
                    response = await client.post(url, headers=headers, json=data, timeout=60.0)

                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise AIClientError(
                    f"AI 服务返回 HTTP {e.response.status_code}，请检查渠道、模型和输出限制参数",
                    status_code=e.response.status_code,
                ) from e
            except httpx.RequestError as e:
                raise AIClientError(f"Request error: {str(e)}")
            except ValueError as e:
                raise AIClientError("AI 服务未返回有效 JSON") from e

    async def list_models(self) -> list[dict]:
        """List available models."""
        result = await self._request("models", method="GET")
        models = []
        for model in result.get("data", []):
            model_id = model.get("id", "")
            # 获取所有模型，不再过滤
            # 排除一些明显不是聊天模型的（如 embedding、whisper、tts、dall-e）
            skip_keywords = ["embedding", "whisper", "tts", "dall-e", "moderation"]
            if any(kw in model_id.lower() for kw in skip_keywords):
                continue
            models.append({"model_id": model_id, "name": model.get("name", model_id)})
        return models

    async def translate(
        self, text: str, target_language: str, custom_prompt: str | None = None
    ) -> str:
        """Translate text using ChatGPT."""
        prompt = translation_prompt(custom_prompt, target_language)
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            self.token_limit_parameter: self.max_output_tokens,
        }
        result = await self._generate("chat/completions", data)
        return completion_text(result)

    async def summarize(self, text: str, custom_prompt: str | None = None) -> str:
        """Generate summary using ChatGPT."""
        prompt = custom_prompt or PROMPTS["summarize"]
        data = {
            "model": self.model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            self.token_limit_parameter: self.max_output_tokens,
        }
        result = await self._generate("chat/completions", data)
        return completion_text(result)

    async def chat(self, prompt: str) -> str:
        """Send a chat message and get response."""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            self.token_limit_parameter: self.max_output_tokens,
        }
        result = await self._generate("chat/completions", data)
        return completion_text(result)

    async def test_connection(self) -> bool:
        """Test connection by listing models."""
        try:
            await self.list_models()
            return True
        except AIClientError:
            return False


class GeminiClient(BaseAIClient):
    """Google Gemini API client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro",
        *,
        max_output_tokens: int = 4096,
        max_input_tokens: int = 12000,
        recorder=None,
    ):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.max_input_tokens = max_input_tokens
        self.recorder = recorder

    async def _request(self, endpoint: str, data: dict | None = None, method: str = "POST") -> dict:
        """Make request to Gemini API."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/{endpoint}?key={self.api_key}"

            try:
                if method == "GET":
                    response = await client.get(url, timeout=30.0)
                else:
                    response = await client.post(url, json=data, timeout=60.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise AIClientError(
                    f"AI 服务返回 HTTP {e.response.status_code}", status_code=e.response.status_code
                ) from e
            except httpx.RequestError as e:
                raise AIClientError(f"Request error: {str(e)}")
            except ValueError as e:
                raise AIClientError("AI 服务未返回有效 JSON") from e

    async def list_models(self) -> list[dict]:
        """List available Gemini models."""
        result = await self._request("models", method="GET")
        return [
            {
                "model_id": item["name"].removeprefix("models/"),
                "name": item.get("displayName", item["name"]),
            }
            for item in result.get("models", [])
            if "generateContent" in item.get("supportedGenerationMethods", [])
        ]

    async def translate(
        self, text: str, target_language: str, custom_prompt: str | None = None
    ) -> str:
        """Translate text using Gemini."""
        prompt = translation_prompt(custom_prompt, target_language)
        data = {
            "contents": [{"parts": [{"text": f"{prompt}\n\n{text}"}]}],
            "generationConfig": {"maxOutputTokens": self.max_output_tokens},
        }
        result = await self._generate(f"models/{self.model}:generateContent", data)
        return completion_text(result, gemini=True)

    async def summarize(self, text: str, custom_prompt: str | None = None) -> str:
        """Generate summary using Gemini."""
        prompt = custom_prompt or PROMPTS["summarize"]
        data = {
            "contents": [{"parts": [{"text": f"{prompt}\n\n{text}"}]}],
            "generationConfig": {"maxOutputTokens": self.max_output_tokens},
        }
        result = await self._generate(f"models/{self.model}:generateContent", data)
        return completion_text(result, gemini=True)

    async def chat(self, prompt: str) -> str:
        """Send a chat message and get response."""
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": self.max_output_tokens},
        }
        result = await self._generate(f"models/{self.model}:generateContent", data)
        return completion_text(result, gemini=True)

    async def test_connection(self) -> bool:
        """Test connection."""
        try:
            await self.list_models()
            return True
        except AIClientError:
            return False


def create_ai_client(
    provider_type: str,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
    *,
    max_output_tokens: int = 4096,
    max_input_tokens: int = 12000,
    token_limit_parameter: str = "auto",
    recorder=None,
) -> BaseAIClient:
    """Factory function to create AI client based on provider type."""
    options = {
        "max_output_tokens": max_output_tokens,
        "max_input_tokens": max_input_tokens,
        "recorder": recorder,
    }
    if token_limit_parameter == "auto":
        token_limit_parameter = (
            "max_completion_tokens" if provider_type == "openai" else "max_tokens"
        )
    if token_limit_parameter not in {"max_tokens", "max_completion_tokens"}:
        raise ValueError("Unsupported output token limit parameter")
    if provider_type == "openai":
        return OpenAIClient(
            api_key,
            base_url,
            model or "gpt-3.5-turbo",
            token_limit_parameter=token_limit_parameter,
            **options,
        )
    elif provider_type == "gemini":
        return GeminiClient(api_key, model or "gemini-pro", **options)
    elif provider_type == "openai_compatible":
        if not base_url:
            raise ValueError("base_url is required for openai_compatible provider")
        return OpenAIClient(
            api_key,
            base_url,
            model or "gpt-3.5-turbo",
            token_limit_parameter=token_limit_parameter,
            **options,
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
