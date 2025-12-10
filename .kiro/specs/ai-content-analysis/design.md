# 设计文档

## 概述

本设计文档描述 AI 智能内容分析功能的技术实现方案。采用 **pgvector + OpenAI Embedding** 方案，复用现有 PostgreSQL 数据库，通过向量相似度搜索实现语义检索，结合 AI 生成分析总结。

## 技术选型

| 组件 | 技术方案 | 说明 |
|-----|---------|------|
| 向量存储 | PostgreSQL + pgvector | 复用现有数据库 |
| 向量生成 | OpenAI text-embedding-3-small | 1536维，成本低 |
| 分析生成 | 现有 AI 服务 | OpenAI/Gemini |
| 前端渲染 | React + react-markdown | Markdown 支持 |

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (React)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 搜索输入框   │  │ 分析结果卡片 │  │ 文章列表组件        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端 API (FastAPI)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ POST /api/v1/ai/analyze - 执行分析查询               │   │
│  │ GET  /api/v1/ai/history - 获取查询历史               │   │
│  │ DELETE /api/v1/ai/history/{id} - 删除历史记录        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     服务层 (Services)                       │
│  ┌───────────────────┐  ┌───────────────────────────────┐  │
│  │ ContentAnalysis   │  │ EmbeddingService              │  │
│  │ Service           │  │ - generate_embedding()        │  │
│  │ - analyze()       │  │ - generate_query_embedding()  │  │
│  │ - search()        │  └───────────────────────────────┘  │
│  └───────────────────┘                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   数据层 (PostgreSQL)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ articles 表                                          │   │
│  │ + embedding vector(1536)  -- 新增向量列              │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ analysis_queries 表 (新增)                           │   │
│  │ - id, user_id, query, created_at                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```


## 组件和接口

### 1. API 端点

#### POST /api/v1/ai/analyze

执行内容分析查询。

**请求体：**
```json
{
  "query": "Python 相关的技术文章",
  "page": 1,
  "page_size": 20,
  "use_semantic_search": true
}
```

**响应体：**
```json
{
  "query": "Python 相关的技术文章",
  "analysis": "根据您订阅的内容，关于 Python 的话题主要集中在...",
  "articles": [
    {
      "id": 123,
      "title": "Python 3.12 正式发布",
      "feed_title": "Python Weekly",
      "link": "https://...",
      "published_at": "2024-12-01T10:00:00Z",
      "relevance_score": 0.95,
      "snippet": "Python 3.12 带来了多项重要更新..."
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20,
  "search_type": "semantic"
}
```

#### GET /api/v1/ai/history

获取用户的查询历史。

**响应体：**
```json
{
  "queries": [
    {
      "id": 1,
      "query": "Python 相关的技术文章",
      "created_at": "2024-12-10T10:00:00Z"
    }
  ]
}
```

#### DELETE /api/v1/ai/history/{query_id}

删除指定的查询历史记录。

### 2. 服务层接口

#### EmbeddingService

```python
class EmbeddingService:
    async def generate_embedding(self, text: str) -> list[float] | None:
        """为文本生成向量嵌入"""
        pass
    
    async def generate_query_embedding(self, query: str) -> list[float]:
        """为查询生成向量嵌入"""
        pass
    
    async def batch_generate_embeddings(
        self, texts: list[str]
    ) -> list[list[float] | None]:
        """批量生成向量嵌入"""
        pass
```

#### ContentAnalysisService

```python
class ContentAnalysisService:
    async def analyze(
        self,
        user_id: int,
        query: str,
        page: int = 1,
        page_size: int = 20,
        use_semantic_search: bool = True
    ) -> AnalysisResult:
        """执行内容分析"""
        pass
    
    async def semantic_search(
        self,
        user_id: int,
        query_embedding: list[float],
        limit: int = 20
    ) -> list[ArticleWithScore]:
        """语义搜索"""
        pass
    
    async def keyword_search(
        self,
        user_id: int,
        query: str,
        limit: int = 20
    ) -> list[ArticleWithScore]:
        """关键词搜索（回退方案）"""
        pass
    
    async def generate_analysis(
        self,
        query: str,
        articles: list[Article]
    ) -> str:
        """生成AI分析总结"""
        pass
```


## 数据模型

### 1. 数据库变更

#### articles 表新增列

```sql
-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 为 articles 表添加向量列
ALTER TABLE articles ADD COLUMN embedding vector(1536);

-- 创建向量索引（IVFFlat，适合中等规模数据）
CREATE INDEX idx_articles_embedding ON articles 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### 新增 analysis_queries 表

```sql
CREATE TABLE analysis_queries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_analysis_queries_user_id ON analysis_queries(user_id);
CREATE INDEX idx_analysis_queries_created_at ON analysis_queries(created_at DESC);
```

### 2. SQLAlchemy 模型

#### Article 模型更新

```python
from pgvector.sqlalchemy import Vector

class Article(BaseModel):
    # ... 现有字段 ...
    
    # 新增向量嵌入列
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )
```

#### AnalysisQuery 模型（新增）

```python
class AnalysisQuery(BaseModel):
    """用户分析查询历史"""
    
    __tablename__ = "analysis_queries"
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 关系
    user: Mapped["User"] = relationship("User")
```

### 3. Pydantic Schema

```python
class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    use_semantic_search: bool = True

class ArticleResult(BaseModel):
    id: int
    title: str
    feed_title: str
    link: str | None
    published_at: datetime | None
    relevance_score: float
    snippet: str

class AnalyzeResponse(BaseModel):
    query: str
    analysis: str | None
    articles: list[ArticleResult]
    total: int
    page: int
    page_size: int
    search_type: str  # "semantic" | "keyword"

class QueryHistoryItem(BaseModel):
    id: int
    query: str
    created_at: datetime

class QueryHistoryResponse(BaseModel):
    queries: list[QueryHistoryItem]
```


## 正确性属性

*属性是系统在所有有效执行中应保持为真的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### Property 1: 搜索结果按相关度降序排列

**对于任意**查询返回的文章列表，列表中每篇文章的相关度分数应大于或等于其后续文章的相关度分数。

**验证: 需求 1.2**

### Property 2: 空白查询被拒绝

**对于任意**仅包含空白字符的查询字符串，系统应返回验证错误而非执行搜索。

**验证: 需求 1.4**

### Property 3: 搜索结果包含必需字段

**对于任意**搜索返回的文章，每篇文章应包含 title、feed_title、published_at、relevance_score 和 snippet 字段。

**验证: 需求 3.1, 3.2**

### Property 4: 分页结果数量限制

**对于任意**分页查询，返回的文章数量应不超过请求的 page_size。

**验证: 需求 3.4**

### Property 5: 新文章生成向量嵌入

**对于任意**新保存的文章（当 embedding 服务可用时），文章的 embedding 字段应不为空。

**验证: 需求 4.1**

### Property 6: 查询历史保存

**对于任意**成功执行的分析查询，该查询应被保存到用户的历史记录中。

**验证: 需求 6.1**

### Property 7: 查询历史数量限制

**对于任意**用户的查询历史请求，返回的记录数量应不超过 10 条。

**验证: 需求 6.2**

### Property 8: 查询历史删除

**对于任意**被删除的查询历史记录，该记录应不再出现在用户的历史列表中。

**验证: 需求 6.4**

### Property 9: Embedding 失败不阻塞文章存储

**对于任意**文章，当 embedding 生成失败时，文章应仍被成功保存（embedding 为 null）。

**验证: 需求 7.3**

### Property 10: 无 Embedding 文章在回退搜索中可被找到

**对于任意** embedding 为 null 的文章，当系统回退到关键词搜索时，该文章应能被匹配的关键词查询找到。

**验证: 需求 7.4**


## 错误处理

### 错误场景和处理策略

| 错误场景 | 处理策略 | 用户提示 |
|---------|---------|---------|
| 查询为空 | 返回 400 错误 | "请输入查询内容" |
| AI 服务未配置 | 仅返回文章列表，analysis 为 null | "未配置 AI 服务，仅显示搜索结果" |
| Embedding API 失败 | 回退到关键词搜索 | 静默处理，search_type 返回 "keyword" |
| 分析生成失败 | 返回文章列表，analysis 包含错误信息 | "AI 分析生成失败，请稍后重试" |
| 无匹配结果 | 返回空列表 | "未找到相关文章，请尝试其他关键词" |
| 数据库连接失败 | 返回 500 错误 | "服务暂时不可用，请稍后重试" |

### 错误响应格式

```json
{
  "detail": "错误描述信息",
  "error_code": "ERROR_CODE"
}
```

## 测试策略

### 单元测试

1. **EmbeddingService 测试**
   - 测试正常文本生成 embedding
   - 测试空文本处理
   - 测试 API 失败时的错误处理

2. **ContentAnalysisService 测试**
   - 测试语义搜索返回正确排序的结果
   - 测试关键词搜索回退
   - 测试分析生成

3. **输入验证测试**
   - 测试空白查询被拒绝
   - 测试超长查询被截断
   - 测试分页参数验证

### 属性测试

使用 **Hypothesis** 库进行属性测试：

```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=0, max_value=1)))
def test_results_sorted_by_relevance(scores):
    """Property 1: 搜索结果按相关度降序排列"""
    # 验证排序属性
    pass

@given(st.text(alphabet=st.characters(whitespace_only=True)))
def test_whitespace_query_rejected(query):
    """Property 2: 空白查询被拒绝"""
    # 验证空白查询处理
    pass
```

### 集成测试

1. **端到端分析流程测试**
   - 创建测试文章 → 生成 embedding → 执行查询 → 验证结果

2. **回退机制测试**
   - 模拟 embedding 服务失败 → 验证回退到关键词搜索

3. **查询历史测试**
   - 执行查询 → 验证历史保存 → 删除历史 → 验证删除成功


## 实现细节

### 1. 向量搜索 SQL 查询

```sql
-- 语义搜索：使用余弦相似度
SELECT 
    a.id,
    a.title,
    a.content,
    a.published_at,
    f.title as feed_title,
    1 - (a.embedding <=> $1) as relevance_score
FROM articles a
JOIN feeds f ON a.feed_id = f.id
WHERE f.user_id = $2
    AND a.embedding IS NOT NULL
ORDER BY a.embedding <=> $1
LIMIT $3;
```

### 2. 关键词搜索 SQL 查询（回退方案）

```sql
-- 全文搜索
SELECT 
    a.id,
    a.title,
    a.content,
    a.published_at,
    f.title as feed_title,
    ts_rank(
        to_tsvector('simple', coalesce(a.title, '') || ' ' || coalesce(a.content, '')),
        plainto_tsquery('simple', $1)
    ) as relevance_score
FROM articles a
JOIN feeds f ON a.feed_id = f.id
WHERE f.user_id = $2
    AND (
        a.title ILIKE '%' || $1 || '%'
        OR a.content ILIKE '%' || $1 || '%'
    )
ORDER BY relevance_score DESC
LIMIT $3;
```

### 3. 分析生成 Prompt

```python
ANALYSIS_PROMPT = """你是一个内容分析助手。请根据以下文章内容，为用户生成一份关于"{query}"的分析总结。

要求：
1. 按主题分类组织内容
2. 提取每个主题的关键点
3. 识别趋势和热点
4. 使用 Markdown 格式输出
5. 保持简洁，总结不超过 500 字

文章内容：
{articles_content}

请生成分析总结："""
```

### 4. 文章入库时生成 Embedding

```python
async def save_article_with_embedding(self, article_data: dict) -> Article:
    """保存文章并生成 embedding"""
    article = await self.article_repo.create(**article_data)
    
    # 异步生成 embedding（不阻塞主流程）
    try:
        text = f"{article.title} {article.content or ''}"
        embedding = await self.embedding_service.generate_embedding(text)
        if embedding:
            article.embedding = embedding
            await self.session.commit()
    except Exception as e:
        logger.warning(f"Failed to generate embedding for article {article.id}: {e}")
    
    return article
```

### 5. 前端组件结构

```
frontend/src/
├── pages/
│   └── AIAnalysisPage.tsx      # AI 分析页面
├── components/
│   └── ai/
│       ├── SearchInput.tsx      # 搜索输入框
│       ├── AnalysisCard.tsx     # 分析结果卡片
│       ├── ArticleList.tsx      # 文章列表
│       └── QueryHistory.tsx     # 查询历史
└── services/
    └── api.ts                   # 新增 AI 分析 API 调用
```

## 依赖项

### 与现有框架的兼容性

本设计方案充分复用现有技术栈，最小化新增依赖：

| 功能 | 现有依赖 | 新增依赖 | 说明 |
|-----|---------|---------|------|
| Embedding 生成 | `openai` ✅ | 无 | 直接使用现有 OpenAI 库 |
| HTTP 请求 | `httpx` ✅ | 无 | 后端已有 |
| 属性测试 | `hypothesis` ✅ | 无 | 已在 dev 依赖中 |
| 向量存储 | - | `pgvector` | 唯一后端新增 |
| 数据获取 | `@tanstack/react-query` ✅ | 无 | 前端已有 |
| 状态管理 | `zustand` ✅ | 无 | 前端已有 |
| Markdown 样式 | `@tailwindcss/typography` ✅ | 无 | 已有 prose 类 |
| Markdown 渲染 | - | `react-markdown` | 唯一前端新增 |

### 后端新增依赖（仅 1 个）

```toml
# pyproject.toml - 添加到 dependencies
pgvector = "^0.2.0"        # PostgreSQL 向量扩展 Python 支持
```

### 数据库扩展

```sql
-- 需要在 PostgreSQL 中安装 pgvector 扩展
-- Docker 环境可使用 pgvector/pgvector:pg16 镜像
CREATE EXTENSION IF NOT EXISTS vector;
```

### 前端新增依赖（仅 1 个）

```json
{
  "dependencies": {
    "react-markdown": "^9.0.0"
  }
}
```

**注意：** `remark-gfm` 可选，用于支持 GitHub 风格 Markdown（表格、任务列表等）。基础 Markdown 渲染只需 `react-markdown`。
