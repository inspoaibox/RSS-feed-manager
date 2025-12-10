"""Embedding service for generating vector embeddings using OpenAI API."""
import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

# 默认 OpenAI Embedding 模型配置
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingServiceError(Exception):
    """Exception raised when embedding generation fails."""
    pass


class EmbeddingService:
    """Service for generating text embeddings using OpenAI API."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None
    ):
        """
        Initialize the embedding service.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional custom base URL for OpenAI-compatible APIs
            model: Optional embedding model name (default: text-embedding-3-small)
        """
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model or DEFAULT_EMBEDDING_MODEL

    async def generate_embedding(self, text: str) -> List[float] | None:
        """
        Generate embedding vector for a single text.
        
        Args:
            text: The text to generate embedding for
            
        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding generation")
            return None

        try:
            # 截断过长的文本（OpenAI 限制约 8191 tokens）
            # 简单处理：限制字符数
            max_chars = 30000
            if len(text) > max_chars:
                text = text[:max_chars]
                logger.info(f"Text truncated to {max_chars} characters for embedding")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": text,
                        "dimensions": EMBEDDING_DIMENSIONS
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error generating embedding: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error generating embedding: {str(e)}")
            return None
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected response format: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {str(e)}")
            return None

    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding vector for a search query.
        
        Args:
            query: The search query text
            
        Returns:
            List of floats representing the embedding vector
            
        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        if not query or not query.strip():
            raise EmbeddingServiceError("Query cannot be empty")

        embedding = await self.generate_embedding(query)
        if embedding is None:
            raise EmbeddingServiceError("Failed to generate embedding for query")
        
        return embedding

    async def batch_generate_embeddings(
        self, texts: List[str]
    ) -> List[List[float] | None]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of embedding vectors (or None for failed items)
        """
        if not texts:
            return []

        # 过滤空文本
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text[:30000])  # 截断
                valid_indices.append(i)

        if not valid_texts:
            return [None] * len(texts)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": valid_texts,
                        "dimensions": EMBEDDING_DIMENSIONS
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                
                # 构建结果列表
                results: List[List[float] | None] = [None] * len(texts)
                for item in data["data"]:
                    original_index = valid_indices[item["index"]]
                    results[original_index] = item["embedding"]
                
                return results

        except Exception as e:
            logger.error(f"Error in batch embedding generation: {str(e)}")
            # 返回全部 None
            return [None] * len(texts)
