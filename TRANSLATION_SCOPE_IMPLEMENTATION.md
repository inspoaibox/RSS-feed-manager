# 翻译范围功能实现总结

## 功能需求
用户在添加/编辑订阅源时，可以选择翻译的内容范围：
- **标题**：默认勾选
- **正文**：默认不勾选

这样可以降低翻译字符消耗，加快翻译速度，减轻服务器压力。

## 已完成的修改

### 1. 数据库层
✅ **文件**: `backend/alembic/versions/029_add_translation_scope.py`
- 新增迁移文件，为 `feeds` 和 `custom_rules` 表添加字段：
  - `translate_title BOOLEAN DEFAULT TRUE`
  - `translate_content BOOLEAN DEFAULT FALSE`

### 2. 数据模型层
✅ **文件**: `backend/app/models/feed.py`
- 添加字段：`translate_title` 和 `translate_content`

✅ **文件**: `backend/app/models/custom_rule.py`
- 添加字段：`translate_title` 和 `translate_content`

### 3. Schema 层
✅ **文件**: `backend/app/schemas/feed.py`
- `FeedCreate`: 添加 `translate_title` 和 `translate_content` 字段
- `FeedUpdate`: 添加 `translate_title` 和 `translate_content` 字段
- `FeedResponse`: 添加 `translate_title` 和 `translate_content` 字段，默认值为 `True` 和 `False`

✅ **文件**: `backend/app/schemas/custom_rule.py`
- `CustomRuleBase`: 添加 `translate_title` 和 `translate_content` 字段

### 4. Service 层
✅ **文件**: `backend/app/services/feed_service.py`
- `create()`: 保存 `translate_title` 和 `translate_content`
- `_to_response()`: 返回 `translate_title` 和 `translate_content`，使用 `getattr` 兼容旧数据

✅ **文件**: `backend/app/services/custom_rule_service.py`
- `create_rule()`: 保存 `translate_title` 和 `translate_content` 到 Feed
- `update_rule()`: 更新 `translate_title` 和 `translate_content`
- `_ensure_feed_for_rule()`: 为旧规则创建 Feed 时设置默认值

✅ **文件**: `backend/app/services/translation_scope.py` (新文件)
- `translation_targets_for_source()`: 从 Feed/CustomRule 对象提取翻译范围
- `has_translatable_article_text()`: 检查文章是否有可翻译内容
- `translation_satisfies_targets()`: 检查已有翻译是否满足当前范围

### 5. Repository 层
✅ **文件**: `backend/app/repositories/feed_repository.py`
- `create()`: 接收并保存 `translate_title` 和 `translate_content` 参数

### 6. 翻译任务层（核心逻辑）
✅ **文件**: `backend/app/tasks/feed_tasks.py`
- `_perform_article_translation_sync()`: 
  - 引入 `translation_targets_for_source()` 
  - 根据 `translate_title` 和 `translate_content` 决定是否翻译标题/正文
  - 如果只翻译标题，正文参数传空字符串给翻译服务
  - 如果只翻译正文，标题参数传空字符串给翻译服务

### 7. 前端 UI 层
✅ **文件**: `frontend/src/pages/SettingsPage.tsx`
- 添加状态变量：
  - `newFeedTranslateTitle` (默认 `true`)
  - `newFeedTranslateContent` (默认 `false`)
- 添加表单 UI（添加订阅表单）：
  - 翻译方式选择后，显示"翻译范围"复选框组
  - 包含"标题"和"正文"两个复选框
  - 校验：至少需要勾选一个
- 添加表单 UI（编辑订阅表单）：
  - 同样的翻译范围复选框组
- API 调用：
  - `addFeedMutation`: 提交 `translate_title` 和 `translate_content`
  - `updateFeedMutation`: 提交 `translate_title` 和 `translate_content`
- 编辑初始化：
  - `startEdit()`: 从 feed 对象读取 `translate_title` 和 `translate_content`（使用 `??` 提供默认值）

## 数据流程

1. **用户配置**:
   - 用户在前端选择翻译方式 (AI/Google/Argos)
   - 勾选翻译范围 (标题/正文)
   - 提交保存

2. **后端保存**:
   - `feed_service.create()` 将配置保存到数据库
   - `translate_title` 和 `translate_content` 字段持久化

3. **文章翻译触发**:
   - 新文章保存时，调用 `_queue_article_translation()`
   - 检查 Feed 的翻译配置，标记文章为待翻译状态
   - 调度 Celery 翻译任务

4. **翻译执行**:
   - `translate_article_task` 调用 `_perform_article_translation_sync()`
   - 使用 `translation_targets_for_source(feed)` 获取翻译范围
   - 根据范围准备输入：
     - 只翻译标题：`title = article.title, content = ""`
     - 只翻译正文：`title = "", content = article.content`
     - 都翻译：`title = article.title, content = article.content`
   - 调用实际翻译服务 (Google/Argos/AI)
   - 保存翻译结果为 JSON：`{"title": "...", "content": "..."}`

## 兼容性处理

### 旧数据兼容
- 数据库迁移：字段默认值 `translate_title=TRUE, translate_content=FALSE`
- 前端读取：使用 `??` 操作符提供默认值
- Service 层：使用 `getattr(feed, 'translate_title', True)` 兼容

### 默认行为
- **新订阅源**：默认只翻译标题（节省字符）
- **旧订阅源**：迁移后默认只翻译标题（降低负载）
- **用户可以随时调整**：勾选正文以获得全文翻译

## 测试建议

### 单元测试
1. 测试 `translation_targets_for_source()` 各种组合
2. 测试只翻译标题时，正文是否为空字符串
3. 测试只翻译正文时，标题是否为空字符串

### 集成测试
1. 创建新订阅源，验证默认值
2. 更新订阅源，验证翻译范围生效
3. 翻译任务执行，验证实际调用参数
4. 验证翻译结果 JSON 格式正确

### E2E 测试
1. 添加订阅源 → 只勾选标题 → 触发翻译 → 检查结果
2. 添加订阅源 → 勾选标题+正文 → 触发翻译 → 检查结果
3. 编辑现有订阅源 → 修改翻译范围 → 重新翻译 → 检查结果

## 运行数据库迁移

```bash
cd backend
alembic upgrade head
```

## 文件清单

### 新增文件
- `backend/alembic/versions/029_add_translation_scope.py`
- `backend/app/services/translation_scope.py`

### 修改文件
- `backend/app/models/feed.py`
- `backend/app/models/custom_rule.py`
- `backend/app/schemas/feed.py`
- `backend/app/schemas/custom_rule.py`
- `backend/app/services/feed_service.py`
- `backend/app/services/custom_rule_service.py`
- `backend/app/repositories/feed_repository.py`
- `backend/app/tasks/feed_tasks.py`
- `frontend/src/pages/SettingsPage.tsx`

## 预期效果

### 性能优化
- **只翻译标题**：字符消耗减少 70-90%（取决于正文长度）
- **翻译速度**：提升 50-80%
- **API 调用成本**：降低 70-90%（Google/AI 翻译）
- **服务器负载**：CPU/内存占用降低（本地翻译）

### 用户体验
- 默认配置下，翻译更快
- 用户可按需选择全文翻译
- UI 直观清晰，操作简单

