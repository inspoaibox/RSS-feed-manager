# 实现计划

## 阶段一：数据库和基础设施

- [x] 1. 配置 pgvector 扩展和数据库迁移

  - [x] 1.1 更新 docker-compose.yml 使用支持 pgvector 的 PostgreSQL 镜像
    - 将 postgres 镜像改为 `pgvector/pgvector:pg16`
    - _需求: 4.1_
  - [x] 1.2 创建 Alembic 迁移文件添加 embedding 列
    - 启用 vector 扩展
    - 为 articles 表添加 `embedding vector(1536)` 列
    - 创建向量索引
    - _需求: 4.1_
  - [x] 1.3 创建 Alembic 迁移文件添加 analysis_queries 表
    - 创建查询历史表
    - 添加索引
    - _需求: 6.1_
  - [x] 1.4 更新 Article 模型添加 embedding 字段
    - 安装 pgvector Python 包
    - 添加 Vector 类型列
    - _需求: 4.1_
  - [x] 1.5 创建 AnalysisQuery 模型
    - 定义查询历史模型
    - _需求: 6.1_

## 阶段二：后端服务层

- [x] 2. 实现 Embedding 服务

  - [x] 2.1 创建 EmbeddingService 类

    - 实现 `generate_embedding()` 方法调用 OpenAI API
    - 实现 `generate_query_embedding()` 方法
    - 添加错误处理和日志
    - _需求: 4.1, 4.4_
  - [x] 2.2 编写 EmbeddingService 属性测试


    - **Property 5: 新文章生成向量嵌入**

    - **验证: 需求 4.1**
  - [-] 2.3 编写 EmbeddingService 单元测试



    - 测试正常生成 embedding

    - 测试 API 失败时的错误处理
    - _需求: 4.1_


- [x] 3. 实现内容分析服务
  - [x] 3.1 创建 ContentAnalysisService 类
    - 实现 `analyze()` 主方法
    - _需求: 1.1, 2.1_
  - [x] 3.2 实现语义搜索方法
    - 使用 pgvector 进行向量相似度搜索
    - 返回带相关度分数的文章列表
    - _需求: 4.2_
  - [x] 3.3 实现关键词搜索方法（回退方案）
    - 使用 ILIKE 进行关键词匹配
    - _需求: 4.3_
  - [x] 3.4 实现 AI 分析生成方法
    - 组装 Prompt
    - 调用现有 AI 服务生成分析
    - _需求: 2.1, 2.2_
  - [x] 3.5 编写搜索结果排序属性测试
    - **Property 1: 搜索结果按相关度降序排列**
    - **验证: 需求 1.2**
  - [x] 3.6 编写输入验证属性测试
    - **Property 2: 空白查询被拒绝**
    - **验证: 需求 1.4**
  - [x] 3.7 编写搜索结果字段属性测试
    - **Property 3: 搜索结果包含必需字段**
    - **验证: 需求 3.1, 3.2**
  - [x] 3.8 编写分页属性测试
    - **Property 4: 分页结果数量限制**
    - **验证: 需求 3.4**




- [x] 4. 实现查询历史服务

  - [x] 4.1 创建 AnalysisQueryRepository

    - 实现 CRUD 操作
    - _需求: 6.1, 6.4_
  - [x] 4.2 实现查询历史保存和获取

    - 保存新查询
    - 获取最近 10 条历史
    - 删除指定历史
    - _需求: 6.1, 6.2, 6.4_
  - [x] 4.3 编写查询历史属性测试


    - **Property 6: 查询历史保存**
    - **Property 7: 查询历史数量限制**
    - **Property 8: 查询历史删除**
    - **验证: 需求 6.1, 6.2, 6.4**

- [x] 5. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 阶段三：API 端点

- [x] 6. 实现 AI 分析 API 端点
  - [x] 6.1 创建 Pydantic Schema
    - AnalyzeRequest, AnalyzeResponse
    - ArticleResult, QueryHistoryItem
    - _需求: 1.1, 3.1_
  - [x] 6.2 实现 POST /api/v1/ai/analyze 端点
    - 输入验证
    - 调用 ContentAnalysisService
    - 返回分析结果和文章列表
    - _需求: 1.1, 2.1, 3.1_
  - [x] 6.3 实现 GET /api/v1/ai/history 端点
    - 获取用户查询历史
    - _需求: 6.2_
  - [x] 6.4 实现 DELETE /api/v1/ai/history/{id} 端点
    - 删除指定查询历史
    - _需求: 6.4_
  - [x] 6.5 编写 API 端点集成测试
    - 测试完整分析流程
    - 测试错误处理
    - _需求: 1.1, 2.1_

## 阶段四：文章入库时生成 Embedding

- [x] 7. 集成 Embedding 生成到文章保存流程
  - [x] 7.1 修改 FeedService 在保存文章时生成 embedding
    - 异步生成，不阻塞主流程
    - 失败时记录日志，文章仍保存
    - _需求: 4.1, 7.3_
  - [x] 7.2 编写 Embedding 失败不阻塞属性测试
    - **Property 9: Embedding 失败不阻塞文章存储**
    - **验证: 需求 7.3**
  - [x] 7.3 编写回退搜索属性测试
    - **Property 10: 无 Embedding 文章在回退搜索中可被找到**
    - **验证: 需求 7.4**

- [x] 8. 检查点 - 确保所有后端测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 阶段五：前端实现

- [x] 9. 前端基础设施
  - [x] 9.1 安装 react-markdown 依赖
    - `npm install react-markdown`
    - _需求: 5.2_
  - [x] 9.2 添加 AI 分析 API 调用方法
    - 在 api.ts 中添加 analyze, getHistory, deleteHistory 方法
    - _需求: 1.1, 6.2_

- [x] 10. 实现 AI 分析页面
  - [x] 10.1 创建 AIAnalysisPage 组件
    - 页面布局和路由配置
    - _需求: 5.1_
  - [x] 10.2 实现搜索输入组件
    - 输入框和提交按钮
    - 加载状态显示
    - _需求: 5.1, 5.4_
  - [x] 10.3 实现分析结果卡片组件
    - Markdown 渲染
    - 使用 Tailwind typography 样式
    - _需求: 5.2_
  - [x] 10.4 实现文章列表组件
    - 显示标题、来源、日期、相关度
    - 文章摘要片段
    - 点击跳转到文章详情
    - _需求: 3.1, 3.2, 3.3_
  - [x] 10.5 实现查询历史组件
    - 显示最近查询
    - 点击重新执行
    - 删除功能
    - _需求: 6.2, 6.3, 6.4_
  - [x] 10.6 添加分页支持
    - 加载更多按钮
    - _需求: 3.4_

- [x] 11. 导航集成
  - [x] 11.1 在侧边栏添加 AI 分析入口
    - 添加菜单项和图标
    - _需求: 5.1_
  - [x] 11.2 配置路由
    - 添加 /ai-analysis 路由
    - _需求: 5.1_

## 阶段六：最终验证

- [x] 12. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 13. 端到端测试和文档
  - [x] 13.1 手动测试完整流程
    - 创建文章 → 生成 embedding → 执行查询 → 查看结果
    - _需求: 全部_
  - [x] 13.2 更新 README 文档
    - 添加 AI 分析功能说明
    - 添加 pgvector 配置说明
    - _需求: 全部_
