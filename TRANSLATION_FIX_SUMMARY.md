# 翻译功能修复总结

## 修复日期
2026-06-16

## 问题描述

用户报告的核心问题：
1. **订阅源设置只翻译标题**
2. **点击右上角"翻译"按钮**
3. **提示"翻译完成"**
4. **但译文和原文内容一样（正文还是英文）**

### 问题根源

当 Feed 配置为"只翻译标题"时：
- 自动翻译只翻译标题，正文不翻译
- 用户点击"翻译"按钮想翻译全文
- 但后端仍然遵循 Feed 配置，只翻译标题
- 导致正文没有被翻译，用户看到的"译文"正文还是原文

## 修复方案

### 核心逻辑

**区分自动翻译和手动翻译**：
- **自动翻译**（Feed 刷新时）：遵循 Feed 的 `translate_title` 和 `translate_content` 配置
- **手动翻译**（点击翻译按钮时）：**强制翻译标题+正文**，忽略 Feed 配置

### 实现细节

#### 1. API 层修改

**文件**: `backend/app/api/v1/endpoints/articles.py`

```python
@router.post("/{article_id}/translate")
async def translate_article(
    article_id: int,
    user_id: CurrentUserId,
    db: DbSession,
    target_language: str = Query("zh-CN"),
    force_full: bool = Query(True, description="强制翻译标题+正文（手动触发时默认为 True）")
):
    """Queue article content translation."""
    service = ArticleService(db)
    result = await service.translate_article(user_id, article_id, target_language, force_full=force_full)
    return result
```

**关键点**：
- 添加 `force_full` 参数
- 默认值为 `True`（手动触发时强制全文翻译）

#### 2. Service 层修改

**文件**: `backend/app/services/article_service.py`

```python
async def translate_article(self, user_id: int, article_id: int, target_language: str, force_full: bool = False) -> dict:
    """Queue article title/content translation using the feed's configured provider.

    Args:
        user_id: User ID
        article_id: Article ID
        target_language: Target language code
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    # ...
    queued, error = dispatch_article_translation(article.id, target_language=target_language, force_full=force_full)
```

**关键点**：
- 传递 `force_full` 参数到任务派发

#### 3. Task 派发层修改

**文件**: `backend/app/tasks/feed_tasks.py`

```python
def dispatch_article_translation(article_id: int, target_language: str | None = None, force_full: bool = False) -> tuple[bool, str | None]:
    """Dispatch a single-article translation task with a Redis dedupe lock.

    Args:
        article_id: Article ID
        target_language: Target language code
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    # ...
    kwargs = {}
    if target_language:
        kwargs["target_language"] = target_language
    if force_full:
        kwargs["force_full"] = True

    celery_app.send_task(
        "app.tasks.feed_tasks.translate_article",
        args=[article_id],
        kwargs=kwargs,
        task_id=owner,
        queue="translation",
    )
```

**关键点**：
- 将 `force_full` 传递给 Celery 任务

#### 4. Celery 任务修改

**文件**: `backend/app/tasks/feed_tasks.py`

```python
def translate_article_task(self, article_id: int, target_language: str | None = None, force_full: bool = False) -> dict:
    """Translate one article in the background and persist translation status.

    Args:
        article_id: Article ID
        target_language: Target language code
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    # ...
    translation_data, method = _perform_article_translation_sync(
        db,
        article,
        feed,
        target_language=target,
        force_full=force_full,  # 传递给实际翻译函数
    )
```

#### 5. 翻译执行层修改

**文件**: `backend/app/tasks/feed_tasks.py`

```python
def _perform_article_translation_sync(
    db: Session,
    article: Article,
    feed: Feed,
    target_language: str | None = None,
    force_full: bool = False,
) -> tuple[str, str]:
    """Translate article title/content with the feed's configured translation provider.

    Args:
        force_full: 如果为 True，强制翻译标题+正文，忽略 Feed 的 translate_title/translate_content 配置
    """
    from app.services.translation_scope import translation_targets_for_source

    # Get translation scope from feed settings
    if force_full:
        # 手动触发时，强制翻译标题+正文
        translate_title, translate_content = True, True
    else:
        # 自动翻译时，遵循 Feed 配置
        translate_title, translate_content = translation_targets_for_source(feed)

    # Prepare input based on translation scope
    title = (article.title or "") if translate_title else ""
    content = (article.content or "") if translate_content else ""
```

**关键点**：
- `force_full=True` 时：强制 `translate_title=True, translate_content=True`
- `force_full=False` 时：使用 Feed 的配置

### 前端 UI 优化

**文件**: `frontend/src/pages/HomePage.tsx`

#### 修复 1：只有标题+正文都翻译时才显示切换按钮

```tsx
{/* 只有当标题和正文都有翻译时，才显示译文/原文切换按钮 */}
{selectedArticle.translation && hasTranslatedTitle && hasTranslatedContent && (
  <div className="mb-4 flex gap-2">
    <button>译文</button>
    <button>原文</button>
  </div>
)}
```

#### 修复 2：只翻译标题时显示提示

```tsx
{/* 如果只翻译了标题，显示提示 */}
{selectedArticle.translation && hasTranslatedTitle && !hasTranslatedContent && (
  <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded text-sm text-blue-700 dark:text-blue-300">
    💡 当前仅翻译了标题，正文显示原文。点击右上角 <Languages className="w-3 h-3 inline mx-1" /> 按钮可翻译全文。
  </div>
)}
```

**效果**：
- 用户清楚知道只翻译了标题
- 知道如何翻译全文
- 不会误认为正文也是译文

## 用户体验流程

### 场景 1：Feed 配置只翻译标题

1. **自动刷新订阅源**
   - 系统只翻译标题
   - 正文保持原文
   - 节省翻译成本

2. **打开文章**
   - 标题显示译文
   - 正文显示原文
   - 显示蓝色提示：只翻译了标题
   - **不显示"译文/原文"切换按钮**（避免混淆）

3. **点击右上角"翻译"按钮**
   - `force_full=True`
   - **重新翻译标题+正文**
   - 正文也被翻译

4. **翻译完成后**
   - 标题显示新译文
   - 正文显示新译文
   - **显示"译文/原文"切换按钮**
   - 可以在译文和原文之间切换

### 场景 2：Feed 配置翻译标题+正文

1. **自动刷新订阅源**
   - 系统翻译标题+正文

2. **打开文章**
   - 标题显示译文
   - 正文显示译文
   - 显示"译文/原文"切换按钮

3. **点击右上角"翻译"按钮**
   - `force_full=True`
   - 重新翻译标题+正文
   - 更新译文

## 测试验证

### 测试步骤

1. **创建测试订阅源**
   - 翻译方式：Google 或 Argos
   - 翻译范围：只勾选"标题"

2. **刷新订阅**
   - 验证：只有标题被翻译

3. **打开文章详情**
   - 验证：标题是中文，正文是英文
   - 验证：显示蓝色提示框
   - 验证：**没有"译文/原文"切换按钮**

4. **点击右上角翻译按钮**
   - 验证：提示"翻译任务已加入队列"
   - 等待翻译完成

5. **翻译完成后**
   - 验证：标题是中文
   - 验证：**正文也是中文**
   - 验证：显示"译文/原文"切换按钮
   - 验证：可以切换查看原文

### 预期结果

✅ 自动翻译遵循 Feed 配置（节省成本）  
✅ 手动翻译强制全文（满足用户需求）  
✅ UI 清晰提示当前状态  
✅ 不会混淆译文和原文  

## 相关文件清单

### 后端
- ✅ `backend/app/api/v1/endpoints/articles.py` - API 接口
- ✅ `backend/app/services/article_service.py` - Service 层
- ✅ `backend/app/tasks/feed_tasks.py` - Task 派发和执行

### 前端
- ✅ `frontend/src/pages/HomePage.tsx` - 文章详情页 UI

## 部署步骤

### 1. 拉取最新代码
```bash
git pull
```

### 2. 重启服务
```bash
# 拉取最新镜像
docker compose --profile browser -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production pull

# 重启服务
docker compose --profile browser -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d
```

### 3. 验证
- 测试只翻译标题的 Feed
- 点击翻译按钮
- 验证正文被翻译

## 注意事项

1. **不影响现有功能**
   - 自动翻译逻辑不变
   - 只影响手动点击翻译按钮的行为

2. **向后兼容**
   - `force_full` 默认值为 `False`
   - 不传参数时保持原有行为

3. **成本控制**
   - 自动翻译仍遵循 Feed 配置
   - 手动翻译由用户主动触发
   - 用户知道会翻译全文

---

**修复状态**: ✅ 已完成  
**测试状态**: ⏳ 待部署验证  
**文档状态**: ✅ 完整

**修复者**: Claude Code  
**完成时间**: 2026-06-16
