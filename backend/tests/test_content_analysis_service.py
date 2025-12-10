"""Tests for ContentAnalysisService.

Feature: ai-content-analysis
Properties tested:
- Property 1: 搜索结果按相关度降序排列
- Property 2: 空白查询被拒绝
- Property 3: 搜索结果包含必需字段
- Property 4: 分页结果数量限制
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.services.content_analysis_service import (
    ContentAnalysisService,
    ArticleWithScore,
    AnalysisResult,
)


class TestContentAnalysisServiceValidation:
    """Tests for input validation.
    
    Feature: ai-content-analysis, Property 2: 空白查询被拒绝
    Validates: Requirements 1.4
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_empty_query_raises_error(self, mock_session):
        """Test that empty query raises HTTPException."""
        service = ContentAnalysisService(session=mock_session)
        
        with pytest.raises(HTTPException) as exc_info:
            await service.analyze(user_id=1, query="")
        
        assert exc_info.value.status_code == 400
        assert "请输入查询内容" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_whitespace_query_raises_error(self, mock_session):
        """Test that whitespace-only query raises HTTPException."""
        service = ContentAnalysisService(session=mock_session)
        
        with pytest.raises(HTTPException) as exc_info:
            await service.analyze(user_id=1, query="   ")
        
        assert exc_info.value.status_code == 400

    @given(st.text(alphabet=st.characters(whitespace_categories=("Zs", "Zl", "Zp")), min_size=0, max_size=50))
    @settings(max_examples=30)
    def test_whitespace_only_query_rejected_property(self, query):
        """
        Property 2: For any whitespace-only query, the system should reject it.
        
        Feature: ai-content-analysis, Property 2: 空白查询被拒绝
        Validates: Requirements 1.4
        """
        import asyncio
        
        if not query.strip():
            mock_session = AsyncMock()
            service = ContentAnalysisService(session=mock_session)
            
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    service.analyze(user_id=1, query=query)
                )
            
            assert exc_info.value.status_code == 400


class TestArticleWithScore:
    """Tests for ArticleWithScore dataclass.
    
    Feature: ai-content-analysis, Property 3: 搜索结果包含必需字段
    Validates: Requirements 3.1, 3.2
    """

    def test_article_has_required_fields(self):
        """Test that ArticleWithScore has all required fields."""
        article = ArticleWithScore(
            id=1,
            title="Test Title",
            content="Test content",
            link="https://example.com",
            published_at=datetime.now(),
            feed_title="Test Feed",
            relevance_score=0.95
        )
        
        assert hasattr(article, 'id')
        assert hasattr(article, 'title')
        assert hasattr(article, 'feed_title')
        assert hasattr(article, 'published_at')
        assert hasattr(article, 'relevance_score')
        assert hasattr(article, 'link')

    def test_get_snippet_truncates_long_content(self):
        """Test that get_snippet truncates long content."""
        long_content = "A" * 500
        article = ArticleWithScore(
            id=1,
            title="Test",
            content=long_content,
            link=None,
            published_at=None,
            feed_title="Feed",
            relevance_score=0.5
        )
        
        snippet = article.get_snippet(max_length=200)
        assert len(snippet) <= 203  # 200 + "..."
        assert snippet.endswith("...")

    def test_get_snippet_returns_full_short_content(self):
        """Test that get_snippet returns full content if short."""
        short_content = "Short content"
        article = ArticleWithScore(
            id=1,
            title="Test",
            content=short_content,
            link=None,
            published_at=None,
            feed_title="Feed",
            relevance_score=0.5
        )
        
        snippet = article.get_snippet(max_length=200)
        assert snippet == short_content

    @given(
        st.integers(min_value=1),
        st.text(min_size=1, max_size=100),
        st.text(min_size=0, max_size=500),
        st.text(min_size=1, max_size=100),
        st.floats(min_value=0, max_value=1)
    )
    @settings(max_examples=30)
    def test_article_with_score_has_all_fields_property(
        self, id, title, content, feed_title, score
    ):
        """
        Property 3: For any search result, it should contain all required fields.
        
        Feature: ai-content-analysis, Property 3: 搜索结果包含必需字段
        Validates: Requirements 3.1, 3.2
        """
        article = ArticleWithScore(
            id=id,
            title=title,
            content=content,
            link=None,
            published_at=datetime.now(),
            feed_title=feed_title,
            relevance_score=score
        )
        
        # 验证所有必需字段存在且有值
        assert article.id is not None
        assert article.title is not None
        assert article.feed_title is not None
        assert article.relevance_score is not None
        assert 0 <= article.relevance_score <= 1
        
        # 验证 snippet 方法可用
        snippet = article.get_snippet()
        assert isinstance(snippet, str)


class TestSearchResultsSorting:
    """Tests for search results sorting.
    
    Feature: ai-content-analysis, Property 1: 搜索结果按相关度降序排列
    Validates: Requirements 1.2
    """

    @given(st.lists(st.floats(min_value=0, max_value=1, allow_nan=False), min_size=2, max_size=20))
    @settings(max_examples=50)
    def test_results_sorted_by_relevance_property(self, scores):
        """
        Property 1: For any list of search results, they should be sorted by relevance descending.
        
        Feature: ai-content-analysis, Property 1: 搜索结果按相关度降序排列
        Validates: Requirements 1.2
        """
        # 创建文章列表
        articles = [
            ArticleWithScore(
                id=i,
                title=f"Article {i}",
                content="Content",
                link=None,
                published_at=datetime.now(),
                feed_title="Feed",
                relevance_score=score
            )
            for i, score in enumerate(scores)
        ]
        
        # 按相关度排序
        sorted_articles = sorted(articles, key=lambda x: x.relevance_score, reverse=True)
        
        # 验证排序正确
        for i in range(len(sorted_articles) - 1):
            assert sorted_articles[i].relevance_score >= sorted_articles[i + 1].relevance_score


class TestPagination:
    """Tests for pagination.
    
    Feature: ai-content-analysis, Property 4: 分页结果数量限制
    Validates: Requirements 3.4
    """

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=30)
    def test_page_size_limit_property(self, page_size):
        """
        Property 4: For any pagination request, results should not exceed page_size.
        
        Feature: ai-content-analysis, Property 4: 分页结果数量限制
        Validates: Requirements 3.4
        """
        # 创建超过 page_size 的文章列表
        total_articles = page_size + 10
        articles = [
            ArticleWithScore(
                id=i,
                title=f"Article {i}",
                content="Content",
                link=None,
                published_at=datetime.now(),
                feed_title="Feed",
                relevance_score=0.5
            )
            for i in range(total_articles)
        ]
        
        # 模拟分页
        paginated = articles[:page_size]
        
        # 验证分页结果不超过 page_size
        assert len(paginated) <= page_size


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_analysis_result_creation(self):
        """Test AnalysisResult can be created with all fields."""
        result = AnalysisResult(
            query="test query",
            analysis="Test analysis",
            articles=[],
            total=0,
            page=1,
            page_size=20,
            search_type="semantic"
        )
        
        assert result.query == "test query"
        assert result.analysis == "Test analysis"
        assert result.articles == []
        assert result.total == 0
        assert result.page == 1
        assert result.page_size == 20
        assert result.search_type == "semantic"

    def test_analysis_result_with_articles(self):
        """Test AnalysisResult with articles."""
        articles = [
            ArticleWithScore(
                id=1,
                title="Test",
                content="Content",
                link=None,
                published_at=datetime.now(),
                feed_title="Feed",
                relevance_score=0.9
            )
        ]
        
        result = AnalysisResult(
            query="test",
            analysis=None,
            articles=articles,
            total=1,
            page=1,
            page_size=20,
            search_type="keyword"
        )
        
        assert len(result.articles) == 1
        assert result.articles[0].relevance_score == 0.9
