"""AI client adapters for different providers."""
from abc import ABC, abstractmethod
from typing import List

import httpx


# 默认 Prompt 模板
DEFAULT_PROMPTS = {
    "translate": "You are a translator. Translate the following text to {target_language}. Keep the [TITLE] and [CONTENT] markers and the original paragraph structure. Only output the translation with markers, nothing else.",
    "summarize": """You are a content organizer. Please organize and summarize the following article content:

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
    pass


class BaseAIClient(ABC):
    """Base class for AI clients."""
    
    @abstractmethod
    async def list_models(self) -> List[dict]:
        """List available models."""
        pass
    
    @abstractmethod
    async def translate(self, text: str, target_language: str, custom_prompt: str | None = None) -> str:
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
    
    def __init__(self, api_key: str, base_url: str | None = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.model = model
    
    async def _request(self, endpoint: str, data: dict | None = None, method: str = "POST") -> dict:
        """Make request to OpenAI API."""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
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
                raise AIClientError(f"API error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                raise AIClientError(f"Request error: {str(e)}")
    
    async def list_models(self) -> List[dict]:
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
            models.append({
                "model_id": model_id,
                "name": model.get("name", model_id)
            })
        return models
    
    async def translate(self, text: str, target_language: str, custom_prompt: str | None = None) -> str:
        """Translate text using ChatGPT."""
        prompt = custom_prompt or PROMPTS["translate"]
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt.format(target_language=target_language)},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3
        }
        result = await self._request("chat/completions", data)
        return result["choices"][0]["message"]["content"]
    
    async def summarize(self, text: str, custom_prompt: str | None = None) -> str:
        """Generate summary using ChatGPT."""
        prompt = custom_prompt or PROMPTS["summarize"]
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.5
        }
        result = await self._request("chat/completions", data)
        return result["choices"][0]["message"]["content"]
    
    async def chat(self, prompt: str) -> str:
        """Send a chat message and get response."""
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        result = await self._request("chat/completions", data)
        return result["choices"][0]["message"]["content"]
    
    async def test_connection(self) -> bool:
        """Test connection by listing models."""
        try:
            await self.list_models()
            return True
        except AIClientError:
            return False


class GeminiClient(BaseAIClient):
    """Google Gemini API client."""
    
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = model
    
    async def _request(self, endpoint: str, data: dict | None = None) -> dict:
        """Make request to Gemini API."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/{endpoint}?key={self.api_key}"
            
            try:
                response = await client.post(url, json=data, timeout=60.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise AIClientError(f"API error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                raise AIClientError(f"Request error: {str(e)}")
    
    async def list_models(self) -> List[dict]:
        """List available Gemini models."""
        # Gemini doesn't have a list models endpoint, return known models
        return [
            {"model_id": "gemini-pro", "name": "Gemini Pro"},
            {"model_id": "gemini-pro-vision", "name": "Gemini Pro Vision"},
        ]
    
    async def translate(self, text: str, target_language: str, custom_prompt: str | None = None) -> str:
        """Translate text using Gemini."""
        prompt_template = custom_prompt or PROMPTS["translate"]
        prompt = prompt_template.format(target_language=target_language)
        data = {
            "contents": [{
                "parts": [{
                    "text": f"{prompt}\n\n{text}"
                }]
            }]
        }
        result = await self._request(f"models/{self.model}:generateContent", data)
        return result["candidates"][0]["content"]["parts"][0]["text"]
    
    async def summarize(self, text: str, custom_prompt: str | None = None) -> str:
        """Generate summary using Gemini."""
        prompt = custom_prompt or PROMPTS["summarize"]
        data = {
            "contents": [{
                "parts": [{
                    "text": f"{prompt}\n\n{text}"
                }]
            }]
        }
        result = await self._request(f"models/{self.model}:generateContent", data)
        return result["candidates"][0]["content"]["parts"][0]["text"]
    
    async def chat(self, prompt: str) -> str:
        """Send a chat message and get response."""
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        result = await self._request(f"models/{self.model}:generateContent", data)
        return result["candidates"][0]["content"]["parts"][0]["text"]
    
    async def test_connection(self) -> bool:
        """Test connection."""
        try:
            data = {"contents": [{"parts": [{"text": "Hello"}]}]}
            await self._request(f"models/{self.model}:generateContent", data)
            return True
        except AIClientError:
            return False


def create_ai_client(
    provider_type: str,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None
) -> BaseAIClient:
    """Factory function to create AI client based on provider type."""
    if provider_type == "openai":
        return OpenAIClient(api_key, base_url, model or "gpt-3.5-turbo")
    elif provider_type == "gemini":
        return GeminiClient(api_key, model or "gemini-pro")
    elif provider_type == "openai_compatible":
        if not base_url:
            raise ValueError("base_url is required for openai_compatible provider")
        return OpenAIClient(api_key, base_url, model or "gpt-3.5-turbo")
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
