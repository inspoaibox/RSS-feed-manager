"""Content analysis service for AI-powered article search and analysis."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.feed import Feed
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError

logger = logging.getLogger(__name__)

# 分析生成 Prompt
ANALYSIS_PROMPT = """你是一个内容分析助手。请根据以下文章内容，为用户生成一份关于"{query}"的分析总结。

要求：
1. 按主题分类组织内容
2. 提取每个主题的关键点
3. 识别趋势和热点
4. 使用 Markdown 格式输出
5. 保持简洁，总结不超过 500 字
6. 使用与文章相同的语言输出

文章内容：
{articles_content}

请生成分析总结："""


@dataclass
class ArticleWithScore:
    """Article with relevance score."""
    id: int
    title: str
    content: str | None
    link: str | None
    published_at: datetime | None
    feed_title: str
    relevance_score: float

    def get_snippet(self, max_length: int = 200) -> str:
        """Get a snippet of the article content."""
        text = self.content or ""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text


@dataclass
class AnalysisResult:
    """Result of content analysis."""
    query: str
    analysis: str | None
    articles: List[ArticleWithScore]
    total: int
    page: int
    page_size: int
    search_type: str  # "semantic" or "keyword"


class ContentAnalysisService:
    """Service for AI-powered content analysis."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        ai_client=None
    ):
        self.session = session
        self.embedding_service = embedding_service
        self.ai_client = ai_client

    async def analyze(
        self,
        user_id: int,
        query: str,
        page: int = 1,
        page_size: int = 20,
        use_semantic_search: bool = True
    ) -> AnalysisResult:
        """
        Execute content analysis for a query.
        
        Args:
            user_id: The user ID
            query: The search query
            page: Page number (1-indexed)
            page_size: Number of results per page
            use_semantic_search: Whether to use semantic search
            
        Returns:
            AnalysisResult with analysis and articles
        """
        # 验证查询
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请输入查询内容"
            )

        query = query.strip()
        search_type = "keyword"
        articles: List[ArticleWithScore] = []
        total = 0

        # 尝试语义搜索
        if use_semantic_search and self.embedding_service:
            try:
                query_embedding = await self.embedding_service.generate_query_embedding(query)
                articles, total = await self.semantic_search(
                    user_id, query_embedding, page, page_size
                )
                search_type = "semantic"
            except EmbeddingServiceError as e:
                logger.warning(f"Semantic search failed, falling back to keyword: {e}")
                articles, total = await self.keyword_search(user_id, query, page, page_size)
        else:
            articles, total = await self.keyword_search(user_id, query, page, page_size)

        # 生成 AI 分析
        analysis = None
        if articles and self.ai_client:
            try:
                analysis = await self.generate_analysis(query, articles[:10])
            except Exception as e:
                logger.error(f"Failed to generate analysis: {e}")
                analysis = "AI 分析生成失败，请稍后重试"

        return AnalysisResult(
            query=query,
            analysis=analysis,
            articles=articles,
            total=total,
            page=page,
            page_size=page_size,
            search_type=search_type
        )


    async def semantic_search(
        self,
        user_id: int,
        query_embedding: List[float],
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[ArticleWithScore], int]:
        """
        Search articles using vector similarity.
        
        Args:
            user_id: The user ID
            query_embedding: The query embedding vector
            page: Page number
            page_size: Results per page
            
        Returns:
            Tuple of (articles with scores, total count)
        """
        offset = (page - 1) * page_size
        
        # 使用原生 SQL 进行向量搜索
        # pgvector 使用 <=> 操作符计算余弦距离
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        # 计算总数
        count_sql = text("""
            SELECT COUNT(*)
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE f.user_id = :user_id AND a.embedding IS NOT NULL
        """)
        count_result = await self.session.execute(count_sql, {"user_id": user_id})
        total = count_result.scalar() or 0

        # 搜索文章
        search_sql = text("""
            SELECT 
                a.id,
                a.title,
                a.content,
                a.link,
                a.published_at,
                f.title as feed_title,
                1 - (a.embedding <=> :embedding::vector) as relevance_score
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE f.user_id = :user_id AND a.embedding IS NOT NULL
            ORDER BY a.embedding <=> :embedding::vector
            LIMIT :limit OFFSET :offset
        """)
        
        result = await self.session.execute(
            search_sql,
            {
                "user_id": user_id,
                "embedding": embedding_str,
                "limit": page_size,
                "offset": offset
            }
        )
        rows = result.fetchall()

        articles = [
            ArticleWithScore(
                id=row.id,
                title=row.title,
                content=row.content,
                link=row.link,
                published_at=row.published_at,
                feed_title=row.feed_title,
                relevance_score=float(row.relevance_score) if row.relevance_score else 0.0
            )
            for row in rows
        ]

        return articles, total


    async def keyword_search(
        self,
        user_id: int,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[ArticleWithScore], int]:
        """
        Search articles using keyword matching (fallback).
        
        Args:
            user_id: The user ID
            query: The search query
            page: Page number
            page_size: Results per page
            
        Returns:
            Tuple of (articles with scores, total count)
        """
        offset = (page - 1) * page_size
        search_pattern = f"%{query}%"

        # 计算总数
        count_query = (
            select(func.count(Article.id))
            .join(Feed, Article.feed_id == Feed.id)
            .where(
                Feed.user_id == user_id,
                or_(
                    Article.title.ilike(search_pattern),
                    Article.content.ilike(search_pattern)
                )
            )
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # 搜索文章
        search_query = (
            select(
                Article.id,
                Article.title,
                Article.content,
                Article.link,
                Article.published_at,
                Feed.title.label("feed_title")
            )
            .join(Feed, Article.feed_id == Feed.id)
            .where(
                Feed.user_id == user_id,
                or_(
                    Article.title.ilike(search_pattern),
                    Article.content.ilike(search_pattern)
                )
            )
            .order_by(Article.published_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.session.execute(search_query)
        rows = result.fetchall()

        # 计算简单的相关度分数（基于匹配位置）
        articles = []
        for row in rows:
            # 简单的相关度计算：标题匹配权重更高
            score = 0.5
            if row.title and query.lower() in row.title.lower():
                score = 0.8
            
            articles.append(ArticleWithScore(
                id=row.id,
                title=row.title,
                content=row.content,
                link=row.link,
                published_at=row.published_at,
                feed_title=row.feed_title,
                relevance_score=score
            ))

        # 按相关度排序
        articles.sort(key=lambda x: x.relevance_score, reverse=True)

        return articles, total


    async def generate_analysis(
        self,
        query: str,
        articles: List[ArticleWithScore]
    ) -> str:
        """
        Generate AI analysis summary for the articles.
        
        Args:
            query: The search query
            articles: List of relevant articles
            
        Returns:
            AI-generated analysis summary
        """
        if not articles:
            return "未找到相关文章，无法生成分析。"

        if not self.ai_client:
            return None

        # 组装文章内容
        articles_content = []
        for i, article in enumerate(articles[:10], 1):
            content = article.content or article.title
            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "..."
            articles_content.append(f"{i}. 【{article.title}】\n{content}")

        articles_text = "\n\n".join(articles_content)
        
        # 生成分析
        prompt = ANALYSIS_PROMPT.format(
            query=query,
            articles_content=articles_text
        )

        try:
            analysis = await self.ai_client.chat(prompt)
            return analysis
        except Exception as e:
            logger.error(f"AI analysis generation failed: {e}")
            raise
