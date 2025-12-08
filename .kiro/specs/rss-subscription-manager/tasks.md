# Implementation Plan

## Phase 1: 项目基础设施

- [x] 1. 初始化项目结构和配置




  - [x] 1.1 创建 Python 后端项目结构（FastAPI）

    - 创建目录结构：app/api, app/services, app/repositories, app/models, app/schemas, app/tasks
    - 配置 pyproject.toml 和依赖管理
    - 配置 alembic 数据库迁移
    - _Requirements: 全局_


  - [x] 1.2 创建 React 前端项目结构
    - 使用 Vite + React + TypeScript 初始化
    - 配置 TailwindCSS


    - 创建目录结构：src/components, src/pages, src/hooks, src/services, src/types
    - _Requirements: 全局_
  - [x] 1.3 配置开发环境
    - 创建 docker-compose.yml（PostgreSQL, Redis）
    - 配置环境变量管理
    - _Requirements: 全局_

## Phase 2: 数据模型和数据库

- [x] 2. 实现数据模型



  - [x] 2.1 创建 SQLAlchemy 基础模型

    - 实现 Base 类和通用字段
    - 配置数据库连接
    - _Requirements: 全局_

  - [x] 2.2 实现 User 模型

    - 创建 User 表结构
    - 实现密码哈希和验证方法
    - _Requirements: 1.1, 1.2_
  - [ ]* 2.3 编写 User 模型属性测试
    - **Property 1: 认证往返一致性**
    - **Validates: Requirements 1.1, 1.2**
  - [x] 2.4 实现 Category 模型


    - 创建 Category 表结构
    - 添加用户关联和唯一约束
    - _Requirements: 3.1, 3.2_

  - [x] 2.5 实现 Feed 模型

    - 创建 Feed 表结构
    - 添加用户和分类关联
    - _Requirements: 2.1, 2.3_

  - [x] 2.6 实现 Article 和 UserArticle 模型

    - 创建 Article 表结构
    - 创建 UserArticle 关联表（已读、收藏状态）
    - _Requirements: 4.1, 5.1, 6.1_

  - [x] 2.7 实现 AIProvider 和 AIModel 模型

    - 创建 AI 渠道和模型表结构
    - 添加默认模型约束
    - _Requirements: 13.1, 14.1_

  - [x] 2.8 实现 CustomRule 模型

    - 创建自定义规则表结构
    - _Requirements: 10.1_


  - [x] 2.9 创建数据库迁移脚本
    - 使用 alembic 生成初始迁移
    - _Requirements: 全局_

- [ ] 3. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: 认证系统

- [x] 4. 实现认证服务



  - [x] 4.1 实现 AuthService

    - 用户注册逻辑
    - 用户登录和 JWT 令牌生成
    - 密码修改和令牌失效
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [ ]* 4.2 编写认证属性测试
    - **Property 2: 密码修改使旧令牌失效**
    - **Validates: Requirements 1.4**

  - [x] 4.3 实现 AuthRouter API 端点

    - POST /register, /login, /logout, /refresh
    - PUT /password
    - GET /me
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 4.4 实现 JWT 中间件和依赖注入

    - 令牌验证中间件
    - 当前用户依赖注入
    - _Requirements: 1.5_

- [ ] 5. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: 分类管理



- [x] 6. 实现分类功能

  - [x] 6.1 实现 CategoryRepository

    - CRUD 操作
    - 名称唯一性检查
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 6.2 实现 CategoryService

    - 创建、更新、删除分类
    - 删除时移动订阅源到默认分类
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [ ]* 6.3 编写分类属性测试
    - **Property 6: 分类名称唯一性**
    - **Property 7: 删除分类保留订阅源**
    - **Property 8: 重命名分类保持关联**
    - **Validates: Requirements 3.1, 3.2, 3.4, 3.5**
  - [x] 6.4 实现 CategoryRouter API 端点


    - GET, POST, PUT, DELETE /categories
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

## Phase 5: 订阅源管理

- [x] 7. 实现订阅源功能




  - [x] 7.1 实现 RSS/Atom 解析器

    - 使用 feedparser 解析订阅源
    - 提取标题、描述、文章列表
    - _Requirements: 2.1, 2.2_

  - [x] 7.2 实现 OPML 解析和生成

    - 导入 OPML 文件解析
    - 导出订阅列表为 OPML
    - _Requirements: 2.5, 2.6_
  - [ ]* 7.3 编写 OPML 往返属性测试
    - **Property 3: OPML 往返一致性**
    - **Validates: Requirements 2.5, 2.6**

  - [x] 7.4 实现 FeedRepository

    - CRUD 操作
    - 按用户、分类查询
    - _Requirements: 2.1, 2.3, 2.4_

  - [x] 7.5 实现 FeedService

    - 添加、编辑、删除订阅源
    - 导入导出 OPML
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  - [ ]* 7.6 编写订阅源属性测试
    - **Property 4: 编辑订阅源保留文章**
    - **Property 5: 删除订阅源级联删除文章**
    - **Validates: Requirements 2.3, 2.4**

  - [x] 7.7 实现 FeedRouter API 端点

    - GET, POST, PUT, DELETE /feeds
    - POST /feeds/import, GET /feeds/export
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 8. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Phase 6: 文章管理

- [x] 9. 实现文章功能


  - [x] 9.1 实现 ArticleRepository

    - CRUD 操作
    - 按订阅源、分类、已读状态筛选
    - 分页查询
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 5.5_


  - [x] 9.2 实现 ArticleService
    - 获取文章列表（筛选、分页）
    - 标记已读/未读
    - 收藏/取消收藏
    - 批量标记已读
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3_
  - [ ]* 9.3 编写文章列表属性测试
    - **Property 9: 文章列表时间排序**
    - **Property 10: 文章筛选正确性**
    - **Property 11: 分页数量限制**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5**
  - [ ]* 9.4 编写阅读状态属性测试
    - **Property 12: 阅读状态切换一致性**
    - **Property 13: 批量标记已读完整性**
    - **Property 14: 未读列表过滤正确性**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
  - [ ]* 9.5 编写收藏功能属性测试
    - **Property 15: 收藏状态切换一致性**
    - **Property 16: 删除订阅源保留收藏文章**

    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [x] 9.6 实现 ArticleRouter API 端点
    - GET /articles（筛选、分页）
    - GET /articles/{id}
    - PUT /articles/{id}/read, /unread, /favorite
    - POST /articles/mark-all-read
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2_

## Phase 7: 搜索功能

- [x] 10. 实现搜索功能


  - [x] 10.1 实现文章搜索
    - 标题和内容全文搜索
    - 按范围筛选（全部/分类/订阅源）
    - _Requirements: 12.1, 12.2, 12.3_
  - [ ]* 10.2 编写搜索属性测试
    - **Property 23: 搜索结果匹配性**
    - **Property 24: 搜索范围限制**

    - **Validates: Requirements 12.1, 12.2**
  - [x] 10.3 实现搜索 API 端点
    - GET /articles/search
    - _Requirements: 12.1, 12.2, 12.3_

- [ ] 11. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Phase 8: 后台任务

- [x] 12. 实现 Celery 后台任务
  - [x] 12.1 配置 Celery 和 Redis
    - 创建 Celery 应用配置
    - 配置任务队列
    - _Requirements: 11.1_
  - [x] 12.2 实现订阅源刷新任务
    - 单个订阅源刷新
    - 定时刷新所有订阅源
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  - [ ]* 12.3 编写新文章属性测试
    - **Property 21: 更新频率设置生效**
    - **Property 22: 新文章默认未读**
    - **Validates: Requirements 11.2, 11.4**
  - [ ] 12.4 实现全文抓取任务
    - 使用 readability 或 newspaper3k 提取全文
    - 图片下载和缓存
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

## Phase 9: 自定义规则

- [x] 13. 实现自定义抓取规则
  - [x] 13.1 实现 CSS 选择器解析器
    - 使用 BeautifulSoup 解析 HTML
    - 根据选择器提取内容
    - _Requirements: 10.2_
  - [ ]* 13.2 编写选择器解析属性测试
    - **Property 20: CSS 选择器解析正确性**
    - **Validates: Requirements 10.2**
  - [x] 13.3 实现 CustomRuleRepository
    - CRUD 操作
    - _Requirements: 10.1, 10.3, 10.4_
  - [x] 13.4 实现 CustomRuleService
    - 创建、编辑、删除规则
    - 测试规则
    - 执行规则抓取
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  - [ ]* 13.5 编写自定义规则属性测试
    - **Property 18: 自定义规则 CRUD 一致性**
    - **Property 19: 删除规则保留文章**
    - **Validates: Requirements 10.1, 10.3, 10.4**
  - [x] 13.6 实现 CustomRuleRouter API 端点
    - GET, POST, PUT, DELETE /rules
    - POST /rules/{id}/test
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  - [x] 13.7 实现规则执行后台任务
    - 定时执行自定义规则
    - _Requirements: 10.6_

- [ ] 14. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Phase 10: AI 功能

- [x] 15. 实现 AI 渠道管理


  - [x] 15.1 实现 AI 客户端适配器

    - OpenAI 客户端
    - Gemini 客户端
    - OpenAI 兼容客户端（自定义端点）
    - _Requirements: 13.1, 13.2_

  - [x] 15.2 实现 AIProviderRepository

    - CRUD 操作
    - _Requirements: 13.1, 13.4, 13.5_

  - [x] 15.3 实现 AIModelRepository
    - CRUD 操作
    - 默认模型管理

    - _Requirements: 14.2, 14.3, 14.4, 14.5, 14.6_
  - [x] 15.4 实现 AIService

    - 渠道管理
    - 模型管理
    - 获取可用模型列表
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_
  - [ ]* 15.5 编写 AI 渠道属性测试
    - **Property 25: AI 渠道 CRUD 一致性**
    - **Property 26: 自定义端点保存正确性**
    - **Property 27: 删除渠道级联删除模型**
    - **Validates: Requirements 13.1, 13.2, 13.4, 13.5**
  - [ ]* 15.6 编写 AI 模型属性测试
    - **Property 28: AI 模型 CRUD 一致性**
    - **Property 29: 默认模型唯一性**
    - **Property 30: 删除渠道清除默认模型**
    - **Validates: Requirements 14.2, 14.3, 14.4, 14.5, 14.6**

  - [x] 15.7 实现 AIRouter API 端点


    - 渠道管理端点
    - 模型管理端点
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [x] 16. 实现 AI 翻译和摘要
  - [x] 16.1 实现翻译服务
    - 调用 AI 模型翻译文章
    - 保存译文
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  - [ ]* 16.2 编写翻译属性测试
    - **Property 31: 翻译保留原文**
    - **Validates: Requirements 15.4**
  - [x] 16.3 实现摘要服务
    - 调用 AI 模型生成摘要
    - 保存摘要
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_
  - [ ]* 16.4 编写摘要属性测试
    - **Property 32: 摘要关联文章**
    - **Validates: Requirements 16.3**
  - [x] 16.5 实现 AI 功能 API 端点
    - POST /ai/translate/{article_id}
    - POST /ai/summarize/{article_id}
    - _Requirements: 15.2, 16.2_
  - [ ] 16.6 实现自动翻译/摘要后台任务
    - 根据订阅源/分类设置自动处理
    - _Requirements: 15.1, 16.1_

- [ ] 17. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Phase 11: 同步功能

- [ ] 18. 实现多设备同步
  - [ ] 18.1 实现 SyncService
    - 推送本地变更
    - 拉取远程变更
    - 冲突解决（时间戳优先）
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [ ]* 18.2 编写同步属性测试
    - **Property 17: 同步冲突解决**
    - **Validates: Requirements 9.3**
  - [ ] 18.3 实现 SyncRouter API 端点
    - POST /sync/push
    - GET /sync/pull
    - GET /sync/status
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

## Phase 12: 前端实现

- [x] 19. 实现前端基础
  - [x] 19.1 配置 API 客户端
    - 使用 axios 或 fetch 封装
    - 配置认证拦截器
    - _Requirements: 全局_
  - [x] 19.2 实现认证页面
    - 登录页面
    - 注册页面
    - _Requirements: 1.1, 1.2_
  - [x] 19.3 实现主布局
    - 侧边栏（分类、订阅源列表）
    - 文章列表区域
    - 文章详情区域
    - _Requirements: 全局_

- [x] 20. 实现订阅管理页面
  - [x] 20.1 实现订阅源列表组件
    - 显示订阅源和未读数
    - 支持拖拽排序
    - _Requirements: 2.1_
  - [x] 20.2 实现添加订阅对话框
    - URL 输入和验证
    - 分类选择
    - _Requirements: 2.1, 2.2_
  - [x] 20.3 实现 OPML 导入导出
    - 文件上传
    - 导出下载
    - _Requirements: 2.5, 2.6_
  - [x] 20.4 实现分类管理
    - 创建、重命名、删除分类
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 21. 实现文章阅读页面
  - [x] 21.1 实现文章列表组件
    - 显示标题、来源、时间、摘要
    - 已读/未读状态显示
    - 收藏标记
    - _Requirements: 4.1, 5.1, 6.1_
  - [x] 21.2 实现文章详情组件
    - 显示完整内容
    - 原文/译文切换
    - AI 摘要显示
    - _Requirements: 4.4, 15.4, 16.4_
  - [x] 21.3 实现筛选和搜索
    - 按分类/订阅源筛选
    - 关键词搜索
    - _Requirements: 4.2, 4.3, 12.1, 12.2_

- [x] 22. 实现 AI 设置页面
  - [x] 22.1 实现渠道管理界面
    - 添加、编辑、删除渠道
    - 测试连接
    - _Requirements: 13.1, 13.2, 13.4, 13.5_
  - [x] 22.2 实现模型管理界面
    - 显示可用模型
    - 设置默认模型
    - _Requirements: 14.1, 14.2, 14.5_
  - [ ] 22.3 实现订阅源 AI 设置
    - 启用/禁用自动翻译
    - 启用/禁用自动摘要
    - _Requirements: 15.1, 16.1_

- [x] 23. 实现自定义规则页面
  - [x] 23.1 实现规则列表
    - 显示规则状态
    - _Requirements: 10.1_
  - [x] 23.2 实现规则编辑器
    - CSS 选择器配置
    - 规则测试预览
    - _Requirements: 10.1, 10.2, 10.3, 10.5_

- [ ] 24. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
