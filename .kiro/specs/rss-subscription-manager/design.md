# Design Document

## Overview

RSS 订阅管理器采用前后端分离架构，后端使用 Python FastAPI 框架提供 RESTful API，前端使用 React + TypeScript 构建现代化 Web 界面。系统支持多用户、多设备同步、全文抓取、离线阅读、自定义抓取规则以及 AI 驱动的翻译和摘要功能。

### 技术栈

- **后端**: Python 3.11+, FastAPI, SQLAlchemy, Celery, Redis
- **前端**: React 18, TypeScript, TailwindCSS, React Query
- **数据库**: PostgreSQL (生产), SQLite (开发/单机)
- **缓存/队列**: Redis
- **AI 集成**: OpenAI API, Google Gemini API, 兼容 OpenAI 的第三方服务

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ 订阅管理  │ │ 文章阅读  │ │ AI 设置  │ │ 用户设置  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      API Layer                            │  │
│  │  /auth  /feeds  /articles  /categories  /ai  /sync       │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Service Layer                          │  │
│  │  AuthService  FeedService  ArticleService  AIService     │  │
│  │  CategoryService  SyncService  RuleService               │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Repository Layer                         │  │
│  │  UserRepo  FeedRepo  ArticleRepo  CategoryRepo  AIRepo   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  PostgreSQL  │    │    Redis     │    │  Celery Workers  │
│  (数据存储)   │    │ (缓存/队列)  │    │  (后台任务)       │
└──────────────┘    └──────────────┘    └──────────────────┘
                                                │
                          ┌─────────────────────┼─────────────────────┐
                          ▼                     ▼                     ▼
                   ┌────────────┐       ┌────────────┐       ┌────────────┐
                   │ Feed 抓取  │       │ 全文提取   │       │ AI 处理    │
                   │   Task     │       │   Task     │       │   Task     │
                   └────────────┘       └────────────┘       └────────────┘
```

## Components and Interfaces

### 1. API Layer (FastAPI Routers)

#### AuthRouter (`/api/v1/auth`)
```python
POST /register          # 用户注册
POST /login             # 用户登录
POST /logout            # 用户登出
POST /refresh           # 刷新令牌
PUT  /password          # 修改密码
GET  /me                # 获取当前用户信息
```

#### FeedRouter (`/api/v1/feeds`)
```python
GET    /                # 获取订阅列表
POST   /                # 添加订阅
GET    /{feed_id}       # 获取订阅详情
PUT    /{feed_id}       # 更新订阅
DELETE /{feed_id}       # 删除订阅
POST   /{feed_id}/refresh  # 手动刷新订阅
POST   /import          # 导入 OPML
GET    /export          # 导出 OPML
```

#### ArticleRouter (`/api/v1/articles`)
```python
GET    /                # 获取文章列表 (支持筛选、分页)
GET    /{article_id}    # 获取文章详情
PUT    /{article_id}/read      # 标记已读
PUT    /{article_id}/unread    # 标记未读
PUT    /{article_id}/favorite  # 收藏/取消收藏
POST   /{article_id}/fetch-full  # 抓取全文
POST   /mark-all-read   # 批量标记已读
GET    /search          # 搜索文章
```

#### CategoryRouter (`/api/v1/categories`)
```python
GET    /                # 获取分类列表
POST   /                # 创建分类
PUT    /{category_id}   # 更新分类
DELETE /{category_id}   # 删除分类
```

#### CustomRuleRouter (`/api/v1/rules`)
```python
GET    /                # 获取规则列表
POST   /                # 创建规则
GET    /{rule_id}       # 获取规则详情
PUT    /{rule_id}       # 更新规则
DELETE /{rule_id}       # 删除规则
POST   /{rule_id}/test  # 测试规则
```

#### AIRouter (`/api/v1/ai`)
```python
# 渠道管理
GET    /providers                    # 获取 AI 渠道列表
POST   /providers                    # 添加 AI 渠道
PUT    /providers/{provider_id}      # 更新渠道
DELETE /providers/{provider_id}      # 删除渠道
POST   /providers/{provider_id}/test # 测试渠道连接

# 模型管理
GET    /providers/{provider_id}/models  # 获取渠道模型列表
POST   /providers/{provider_id}/models  # 添加模型
PUT    /models/{model_id}               # 更新模型
DELETE /models/{model_id}               # 删除模型
PUT    /models/{model_id}/default       # 设为默认模型
GET    /models/default                  # 获取默认模型

# AI 功能
POST   /translate/{article_id}       # 翻译文章
POST   /summarize/{article_id}       # 生成摘要
```

#### SyncRouter (`/api/v1/sync`)
```python
POST   /push            # 推送本地变更
GET    /pull            # 拉取远程变更
GET    /status          # 获取同步状态
```

### 2. Service Layer

#### FeedService
```python
class FeedService:
    async def add_feed(user_id: int, url: str, category_id: int = None) -> Feed
    async def parse_feed(url: str) -> FeedInfo
    async def update_feed(feed_id: int, data: FeedUpdate) -> Feed
    async def delete_feed(feed_id: int) -> None
    async def refresh_feed(feed_id: int) -> List[Article]
    async def import_opml(user_id: int, content: str) -> ImportResult
    async def export_opml(user_id: int) -> str
```

#### ArticleService
```python
class ArticleService:
    async def get_articles(user_id: int, filters: ArticleFilter) -> PaginatedResult
    async def get_article(article_id: int) -> Article
    async def mark_read(article_id: int, user_id: int) -> None
    async def mark_unread(article_id: int, user_id: int) -> None
    async def toggle_favorite(article_id: int, user_id: int) -> bool
    async def fetch_full_content(article_id: int) -> Article
    async def search(user_id: int, query: str, scope: SearchScope) -> List[Article]
```

#### AIService
```python
class AIService:
    async def add_provider(user_id: int, config: ProviderConfig) -> AIProvider
    async def test_provider(provider_id: int) -> TestResult
    async def fetch_models(provider_id: int) -> List[AIModel]
    async def set_default_model(user_id: int, model_id: int) -> None
    async def translate(article_id: int, target_lang: str) -> Translation
    async def summarize(article_id: int) -> Summary
```

#### CustomRuleService
```python
class CustomRuleService:
    async def create_rule(user_id: int, rule: RuleCreate) -> CustomRule
    async def test_rule(rule_id: int) -> TestResult
    async def execute_rule(rule_id: int) -> List[Article]
```

### 3. Background Tasks (Celery)

```python
# tasks/feed_tasks.py
@celery.task
def refresh_all_feeds():
    """定时刷新所有订阅源"""

@celery.task
def refresh_feed(feed_id: int):
    """刷新单个订阅源"""

@celery.task
def fetch_full_content(article_id: int):
    """抓取文章全文"""

# tasks/ai_tasks.py
@celery.task
def auto_translate(article_id: int, target_lang: str):
    """自动翻译文章"""

@celery.task
def auto_summarize(article_id: int):
    """自动生成摘要"""

# tasks/rule_tasks.py
@celery.task
def execute_custom_rule(rule_id: int):
    """执行自定义抓取规则"""
```

## Data Models

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    User     │       │  Category   │       │    Feed     │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id          │──┐    │ id          │──┐    │ id          │
│ username    │  │    │ user_id     │◄─┤    │ user_id     │◄─┐
│ email       │  │    │ name        │  │    │ category_id │◄─┤
│ password    │  │    │ created_at  │  │    │ url         │  │
│ created_at  │  │    └─────────────┘  │    │ title       │  │
└─────────────┘  │                     │    │ description │  │
      │          │                     │    │ site_url    │  │
      │          └─────────────────────┼────│ icon_url    │  │
      │                                │    │ last_fetch  │  │
      │                                │    │ fetch_interval│ │
      │                                │    │ auto_translate│ │
      │                                │    │ auto_summarize│ │
      │                                │    └─────────────┘  │
      │                                │           │         │
      │    ┌─────────────┐             │           │         │
      │    │  Article    │             │           │         │
      │    ├─────────────┤             │           │         │
      │    │ id          │             │           │         │
      │    │ feed_id     │◄────────────┼───────────┘         │
      │    │ guid        │             │                     │
      │    │ title       │             │                     │
      │    │ link        │             │                     │
      │    │ content     │             │                     │
      │    │ full_content│             │                     │
      │    │ summary     │             │                     │
      │    │ translation │             │                     │
      │    │ author      │             │                     │
      │    │ published_at│             │                     │
      │    │ created_at  │             │                     │
      │    └─────────────┘             │                     │
      │           │                    │                     │
      │           ▼                    │                     │
      │    ┌─────────────┐             │                     │
      │    │ UserArticle │             │                     │
      │    ├─────────────┤             │                     │
      └───►│ user_id     │             │                     │
           │ article_id  │             │                     │
           │ is_read     │             │                     │
           │ is_favorite │             │                     │
           │ read_at     │             │                     │
           └─────────────┘             │                     │
                                       │                     │
┌─────────────┐       ┌─────────────┐  │                     │
│ AIProvider  │       │  AIModel    │  │                     │
├─────────────┤       ├─────────────┤  │                     │
│ id          │──┐    │ id          │  │                     │
│ user_id     │◄─┼────│ provider_id │  │                     │
│ name        │  │    │ model_id    │  │                     │
│ type        │  │    │ name        │  │                     │
│ api_key     │  │    │ is_default  │  │                     │
│ base_url    │  │    │ created_at  │  │                     │
│ is_active   │  │    └─────────────┘  │                     │
│ created_at  │  │                     │                     │
└─────────────┘  │                     │                     │
                 │                     │                     │
┌─────────────┐  │                     │                     │
│ CustomRule  │  │                     │                     │
├─────────────┤  │                     │                     │
│ id          │  │                     │                     │
│ user_id     │◄─┘                     │                     │
│ name        │                        │                     │
│ target_url  │                        │                     │
│ list_selector│                       │                     │
│ title_selector│                      │                     │
│ link_selector │                      │                     │
│ content_selector│                    │                     │
│ date_selector│                       │                     │
│ fetch_interval│                      │                     │
│ is_active   │                        │                     │
│ last_fetch  │                        │                     │
│ category_id │◄───────────────────────┘                     │
│ auto_translate│                                            │
│ auto_summarize│                                            │
└─────────────┘                                              │
      │                                                      │
      └──────────────────────────────────────────────────────┘
                    (CustomRule 生成的文章也存入 Feed/Article)
```

### SQLAlchemy Models

```python
# models/user.py
class User(Base):
    __tablename__ = "users"
    
    id: int = Column(Integer, primary_key=True)
    username: str = Column(String(50), unique=True, nullable=False)
    email: str = Column(String(255), unique=True, nullable=False)
    password_hash: str = Column(String(255), nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, onupdate=datetime.utcnow)
    
    categories = relationship("Category", back_populates="user")
    feeds = relationship("Feed", back_populates="user")
    ai_providers = relationship("AIProvider", back_populates="user")

# models/feed.py
class Feed(Base):
    __tablename__ = "feeds"
    
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id: int = Column(Integer, ForeignKey("categories.id"))
    url: str = Column(String(2048), nullable=False)
    title: str = Column(String(255))
    description: str = Column(Text)
    site_url: str = Column(String(2048))
    icon_url: str = Column(String(2048))
    last_fetched_at: datetime = Column(DateTime)
    fetch_interval: int = Column(Integer, default=3600)  # seconds
    auto_translate: bool = Column(Boolean, default=False)
    auto_summarize: bool = Column(Boolean, default=False)
    target_language: str = Column(String(10))
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

# models/article.py
class Article(Base):
    __tablename__ = "articles"
    
    id: int = Column(Integer, primary_key=True)
    feed_id: int = Column(Integer, ForeignKey("feeds.id"), nullable=False)
    guid: str = Column(String(2048), nullable=False)
    title: str = Column(String(500))
    link: str = Column(String(2048))
    content: str = Column(Text)
    full_content: str = Column(Text)
    summary: str = Column(Text)  # AI 生成的摘要
    translation: str = Column(Text)  # AI 翻译内容
    author: str = Column(String(255))
    published_at: datetime = Column(DateTime)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('feed_id', 'guid'),)

# models/user_article.py
class UserArticle(Base):
    __tablename__ = "user_articles"
    
    user_id: int = Column(Integer, ForeignKey("users.id"), primary_key=True)
    article_id: int = Column(Integer, ForeignKey("articles.id"), primary_key=True)
    is_read: bool = Column(Boolean, default=False)
    is_favorite: bool = Column(Boolean, default=False)
    read_at: datetime = Column(DateTime)

# models/ai_provider.py
class AIProvider(Base):
    __tablename__ = "ai_providers"
    
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    name: str = Column(String(100), nullable=False)
    type: str = Column(String(50), nullable=False)  # openai, gemini, openai_compatible
    api_key: str = Column(String(500), nullable=False)
    base_url: str = Column(String(2048))  # 自定义端点
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

# models/ai_model.py
class AIModel(Base):
    __tablename__ = "ai_models"
    
    id: int = Column(Integer, primary_key=True)
    provider_id: int = Column(Integer, ForeignKey("ai_providers.id"), nullable=False)
    model_id: str = Column(String(100), nullable=False)  # gpt-4, gemini-pro
    name: str = Column(String(100))
    is_default: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

# models/custom_rule.py
class CustomRule(Base):
    __tablename__ = "custom_rules"
    
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id: int = Column(Integer, ForeignKey("categories.id"))
    name: str = Column(String(100), nullable=False)
    target_url: str = Column(String(2048), nullable=False)
    list_selector: str = Column(String(500))
    title_selector: str = Column(String(500))
    link_selector: str = Column(String(500))
    content_selector: str = Column(String(500))
    date_selector: str = Column(String(500))
    fetch_interval: int = Column(Integer, default=3600)
    is_active: bool = Column(Boolean, default=True)
    auto_translate: bool = Column(Boolean, default=False)
    auto_summarize: bool = Column(Boolean, default=False)
    last_fetched_at: datetime = Column(DateTime)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 认证往返一致性
*For any* 有效的用户注册信息（用户名、邮箱、密码），注册成功后使用相同的凭据登录应返回有效的访问令牌。
**Validates: Requirements 1.1, 1.2**

### Property 2: 密码修改使旧令牌失效
*For any* 已认证用户，修改密码后使用旧令牌访问 API 应被拒绝。
**Validates: Requirements 1.4**

### Property 3: OPML 往返一致性
*For any* 用户的订阅列表，导出为 OPML 后再导入应保留所有订阅源的 URL 和标题。
**Validates: Requirements 2.5, 2.6**

### Property 4: 编辑订阅源保留文章
*For any* 包含文章的订阅源，编辑其标题或分类后，该订阅源下的文章数量应保持不变。
**Validates: Requirements 2.3**

### Property 5: 删除订阅源级联删除文章
*For any* 订阅源，删除后该订阅源及其所有文章都应从数据库中移除。
**Validates: Requirements 2.4**

### Property 6: 分类名称唯一性
*For any* 用户，同一用户下的分类名称应唯一，创建重复名称的分类应被拒绝。
**Validates: Requirements 3.1, 3.2**

### Property 7: 删除分类保留订阅源
*For any* 包含订阅源的分类，删除后其下的订阅源应移至默认分类，订阅源总数不变。
**Validates: Requirements 3.4**

### Property 8: 重命名分类保持关联
*For any* 分类，重命名后其下的订阅源数量应保持不变。
**Validates: Requirements 3.5**

### Property 9: 文章列表时间排序
*For any* 文章列表查询，返回的文章应按发布时间倒序排列（后发布的在前）。
**Validates: Requirements 4.1**

### Property 10: 文章筛选正确性
*For any* 按分类或订阅源筛选的文章列表，返回的所有文章都应属于指定的分类或订阅源。
**Validates: Requirements 4.2, 4.3**

### Property 11: 分页数量限制
*For any* 分页请求，返回的文章数量应不超过请求的 page_size。
**Validates: Requirements 4.5**

### Property 12: 阅读状态切换一致性
*For any* 文章，标记为已读后 is_read 应为 true，标记为未读后 is_read 应为 false。
**Validates: Requirements 5.1, 5.2**

### Property 13: 批量标记已读完整性
*For any* 订阅源或分类，执行"全部标记已读"后，其下所有文章的 is_read 都应为 true。
**Validates: Requirements 5.3, 5.4**

### Property 14: 未读列表过滤正确性
*For any* 未读文章列表查询，返回的所有文章的 is_read 都应为 false。
**Validates: Requirements 5.5**

### Property 15: 收藏状态切换一致性
*For any* 文章，收藏后应出现在收藏列表中，取消收藏后应从收藏列表中移除。
**Validates: Requirements 6.1, 6.2, 6.3**

### Property 16: 删除订阅源保留收藏文章
*For any* 已收藏的文章，即使其订阅源被删除，文章内容应保留在收藏列表中。
**Validates: Requirements 6.4**

### Property 17: 同步冲突解决
*For any* 同一数据的多个修改，冲突解决后应保留时间戳最新的修改。
**Validates: Requirements 9.3**

### Property 18: 自定义规则 CRUD 一致性
*For any* 自定义规则，创建后应存在于列表中，编辑后配置应更新，删除后应从列表中移除。
**Validates: Requirements 10.1, 10.3, 10.4**

### Property 19: 删除规则保留文章
*For any* 自定义规则，删除后已抓取的文章应保留在数据库中。
**Validates: Requirements 10.4**

### Property 20: CSS 选择器解析正确性
*For any* 有效的 HTML 文档和 CSS 选择器，解析器应正确提取匹配的元素内容。
**Validates: Requirements 10.2**

### Property 21: 更新频率设置生效
*For any* 订阅源，设置更新频率后 fetch_interval 应更新为指定值。
**Validates: Requirements 11.2**

### Property 22: 新文章默认未读
*For any* 新抓取的文章，其初始 is_read 状态应为 false。
**Validates: Requirements 11.4**

### Property 23: 搜索结果匹配性
*For any* 搜索查询，返回的所有文章的标题或内容应包含搜索关键词。
**Validates: Requirements 12.1**

### Property 24: 搜索范围限制
*For any* 指定范围的搜索，返回的文章应属于指定的分类或订阅源。
**Validates: Requirements 12.2**

### Property 25: AI 渠道 CRUD 一致性
*For any* AI 渠道配置，创建后应存在于列表中，编辑后配置应更新，删除后应从列表中移除。
**Validates: Requirements 13.1, 13.4, 13.5**

### Property 26: 自定义端点保存正确性
*For any* OpenAI 兼容的第三方渠道，自定义的 base_url 应正确保存和返回。
**Validates: Requirements 13.2**

### Property 27: 删除渠道级联删除模型
*For any* AI 渠道，删除后其关联的所有模型配置也应被删除。
**Validates: Requirements 13.5**

### Property 28: AI 模型 CRUD 一致性
*For any* AI 模型，添加后应存在于列表中，编辑后配置应更新，删除后应从列表中移除。
**Validates: Requirements 14.2, 14.3, 14.4**

### Property 29: 默认模型唯一性
*For any* 用户，设置默认模型后该模型的 is_default 应为 true，其他所有模型的 is_default 应为 false。
**Validates: Requirements 14.5**

### Property 30: 删除渠道清除默认模型
*For any* 默认模型所属的渠道被删除后，应无默认模型（所有模型的 is_default 都为 false）。
**Validates: Requirements 14.6**

### Property 31: 翻译保留原文
*For any* 翻译完成的文章，原文内容（content 字段）应保持不变，译文存储在 translation 字段。
**Validates: Requirements 15.4**

### Property 32: 摘要关联文章
*For any* 生成摘要的文章，summary 字段应有非空值。
**Validates: Requirements 16.3**

## Error Handling

### API 错误响应格式

```python
class ErrorResponse(BaseModel):
    code: str           # 错误代码，如 "FEED_NOT_FOUND"
    message: str        # 用户友好的错误信息
    details: dict = {}  # 可选的详细信息

# HTTP 状态码映射
400 Bad Request      # 请求参数无效
401 Unauthorized     # 未认证或令牌无效
403 Forbidden        # 无权限访问
404 Not Found        # 资源不存在
409 Conflict         # 资源冲突（如重复名称）
422 Unprocessable    # 业务逻辑错误
500 Internal Error   # 服务器内部错误
```

### 错误处理策略

| 场景 | 处理方式 |
|------|----------|
| RSS 解析失败 | 返回具体错误原因，保留用户输入供修改 |
| 全文抓取失败 | 保留原有摘要，记录错误日志，允许重试 |
| AI API 调用失败 | 保留原文，记录错误，提示用户检查配置 |
| 同步冲突 | 使用时间戳解决，保留最新修改 |
| 自定义规则执行失败 | 记录错误，下次调度重试 |

## Testing Strategy

### 测试框架

- **单元测试**: pytest
- **属性测试**: hypothesis (Python PBT 库)
- **API 测试**: pytest + httpx
- **前端测试**: Vitest + React Testing Library

### 单元测试

单元测试覆盖以下场景：
- Service 层业务逻辑
- Repository 层数据操作
- 工具函数（OPML 解析、CSS 选择器解析等）
- 错误处理和边界情况

### 属性测试

使用 hypothesis 库实现属性测试，每个属性测试配置运行至少 100 次迭代。

属性测试标注格式：
```python
# **Feature: rss-subscription-manager, Property {number}: {property_text}**
@given(...)
def test_property_name():
    ...
```

属性测试重点覆盖：
- 数据往返一致性（OPML 导入导出、认证流程）
- 状态切换一致性（已读/未读、收藏/取消收藏）
- 筛选和搜索正确性
- 级联操作完整性（删除订阅源/分类/渠道）
- 唯一性约束（分类名称、默认模型）

### 测试数据生成策略

```python
from hypothesis import strategies as st

# 用户数据生成
user_strategy = st.fixed_dictionaries({
    "username": st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
    "email": st.emails(),
    "password": st.text(min_size=8, max_size=100)
})

# 订阅源数据生成
feed_strategy = st.fixed_dictionaries({
    "url": st.from_regex(r"https?://[a-z]+\.[a-z]+/feed\.xml"),
    "title": st.text(min_size=1, max_size=255),
    "fetch_interval": st.integers(min_value=300, max_value=86400)
})

# 文章数据生成
article_strategy = st.fixed_dictionaries({
    "title": st.text(min_size=1, max_size=500),
    "content": st.text(min_size=0, max_size=10000),
    "link": st.from_regex(r"https?://[a-z]+\.[a-z]+/article/[0-9]+"),
    "published_at": st.datetimes()
})
```
