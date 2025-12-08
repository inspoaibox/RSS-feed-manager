# Requirements Document

## Introduction

本地 RSS 订阅管理器是一个功能完善的内容聚合平台，支持标准 RSS/Atom 订阅源管理以及自定义规则抓取。系统采用 Python 后端 + Web 前端架构，支持多用户、多设备同步、全文抓取和离线阅读。前期以 Web 应用为主，后期可扩展至桌面应用和移动端。

## Glossary

- **RSS_Manager**: RSS 订阅管理系统的核心服务
- **Feed**: RSS/Atom 订阅源，包含多篇文章的内容源
- **Article**: 订阅源中的单篇文章或条目
- **Category**: 用于组织和分类订阅源的分组
- **Custom_Rule**: 用户定义的网页抓取规则，用于从不支持 RSS 的网站提取内容
- **User**: 系统的注册用户，拥有独立的订阅和设置
- **Sync_Service**: 负责多设备间数据同步的服务组件
- **Full_Text_Extractor**: 从文章链接抓取完整内容的组件
- **AI_Provider**: AI 服务提供商渠道，如 OpenAI、Gemini 或兼容 OpenAI 的第三方服务
- **AI_Model**: AI 提供商下的具体模型，如 gpt-4、gemini-pro 等
- **AI_Service**: 负责调用 AI 模型进行翻译和摘要的服务组件

## Requirements

### Requirement 1: 用户管理

**User Story:** As a 用户, I want to 注册和管理我的账户, so that 我可以拥有独立的订阅空间并在多设备间同步数据。

#### Acceptance Criteria

1. WHEN a 用户提交有效的注册信息（用户名、邮箱、密码） THEN the RSS_Manager SHALL 创建新用户账户并返回认证令牌
2. WHEN a 用户使用正确的凭据登录 THEN the RSS_Manager SHALL 验证身份并返回有效的访问令牌
3. WHEN a 用户提交无效的登录凭据 THEN the RSS_Manager SHALL 拒绝登录请求并返回明确的错误信息
4. WHEN a 用户请求修改密码并提供正确的当前密码 THEN the RSS_Manager SHALL 更新密码并使旧令牌失效
5. IF a 访问令牌过期 THEN the RSS_Manager SHALL 拒绝请求并提示用户重新认证

### Requirement 2: 订阅源管理

**User Story:** As a 用户, I want to 添加、编辑和删除 RSS 订阅源, so that 我可以管理我关注的内容来源。

#### Acceptance Criteria

1. WHEN a 用户提交有效的 RSS/Atom URL THEN the RSS_Manager SHALL 解析订阅源并将其添加到用户的订阅列表
2. WHEN a 用户提交无效或无法访问的 URL THEN the RSS_Manager SHALL 拒绝添加并返回具体的错误原因
3. WHEN a 用户编辑订阅源的标题或分类 THEN the RSS_Manager SHALL 更新订阅源信息并保留已抓取的文章
4. WHEN a 用户删除订阅源 THEN the RSS_Manager SHALL 移除订阅源及其关联的所有文章数据
5. WHEN a 用户导入 OPML 文件 THEN the RSS_Manager SHALL 解析文件并批量添加所有有效的订阅源
6. WHEN a 用户请求导出订阅 THEN the RSS_Manager SHALL 生成包含所有订阅源的 OPML 文件

### Requirement 3: 分类管理

**User Story:** As a 用户, I want to 创建和管理订阅源分类, so that 我可以有组织地浏览不同主题的内容。

#### Acceptance Criteria

1. WHEN a 用户创建新分类并提供唯一名称 THEN the RSS_Manager SHALL 创建分类并返回分类标识符
2. WHEN a 用户尝试创建重复名称的分类 THEN the RSS_Manager SHALL 拒绝创建并提示名称已存在
3. WHEN a 用户将订阅源移动到指定分类 THEN the RSS_Manager SHALL 更新订阅源的分类归属
4. WHEN a 用户删除分类 THEN the RSS_Manager SHALL 移除分类并将其下的订阅源移至默认分类
5. WHEN a 用户重命名分类 THEN the RSS_Manager SHALL 更新分类名称并保持订阅源关联不变

### Requirement 4: 文章列表与阅读

**User Story:** As a 用户, I want to 浏览和阅读订阅的文章, so that 我可以获取感兴趣的内容。

#### Acceptance Criteria

1. WHEN a 用户请求文章列表 THEN the RSS_Manager SHALL 返回按发布时间倒序排列的文章列表
2. WHEN a 用户按分类筛选文章 THEN the RSS_Manager SHALL 仅返回该分类下订阅源的文章
3. WHEN a 用户按订阅源筛选文章 THEN the RSS_Manager SHALL 仅返回该订阅源的文章
4. WHEN a 用户打开文章详情 THEN the RSS_Manager SHALL 显示文章标题、来源、发布时间和内容
5. WHEN a 用户请求分页加载 THEN the RSS_Manager SHALL 返回指定页码和数量的文章数据

### Requirement 5: 已读/未读状态管理

**User Story:** As a 用户, I want to 追踪文章的阅读状态, so that 我可以知道哪些内容还未阅读。

#### Acceptance Criteria

1. WHEN a 用户打开文章详情 THEN the RSS_Manager SHALL 自动将该文章标记为已读
2. WHEN a 用户手动标记文章为未读 THEN the RSS_Manager SHALL 更新文章状态为未读
3. WHEN a 用户标记订阅源的所有文章为已读 THEN the RSS_Manager SHALL 批量更新该订阅源下所有文章状态
4. WHEN a 用户标记分类的所有文章为已读 THEN the RSS_Manager SHALL 批量更新该分类下所有文章状态
5. WHEN a 用户请求未读文章列表 THEN the RSS_Manager SHALL 仅返回未读状态的文章

### Requirement 6: 收藏功能

**User Story:** As a 用户, I want to 收藏重要的文章, so that 我可以稍后快速找到它们。

#### Acceptance Criteria

1. WHEN a 用户收藏文章 THEN the RSS_Manager SHALL 将文章添加到用户的收藏列表
2. WHEN a 用户取消收藏 THEN the RSS_Manager SHALL 从收藏列表中移除该文章
3. WHEN a 用户请求收藏列表 THEN the RSS_Manager SHALL 返回所有已收藏的文章
4. WHEN a 订阅源被删除 THEN the RSS_Manager SHALL 保留该订阅源下已收藏文章的内容

### Requirement 7: 全文抓取

**User Story:** As a 用户, I want to 获取文章的完整内容, so that 我可以阅读完整文章而非仅摘要。

#### Acceptance Criteria

1. WHEN a RSS 源仅提供摘要内容 THEN the Full_Text_Extractor SHALL 从原文链接抓取完整文章内容
2. WHEN a 用户手动请求抓取全文 THEN the Full_Text_Extractor SHALL 重新获取并更新文章内容
3. WHEN a 全文抓取失败 THEN the RSS_Manager SHALL 保留原有摘要内容并记录错误信息
4. WHEN a 文章内容包含图片 THEN the Full_Text_Extractor SHALL 下载并缓存图片以支持离线阅读

### Requirement 8: 离线阅读

**User Story:** As a 用户, I want to 在没有网络时阅读已同步的文章, so that 我可以随时随地阅读内容。

#### Acceptance Criteria

1. WHEN a 文章被同步到本地 THEN the RSS_Manager SHALL 存储文章内容和关联资源以供离线访问
2. WHEN a 用户在离线状态下请求已缓存的文章 THEN the RSS_Manager SHALL 从本地存储返回文章内容
3. WHEN a 用户在离线状态下执行写操作 THEN the RSS_Manager SHALL 将操作存入队列待网络恢复后同步
4. WHEN a 网络连接恢复 THEN the Sync_Service SHALL 自动处理离线操作队列并同步数据

### Requirement 9: 多设备同步

**User Story:** As a 用户, I want to 在多个设备间同步我的订阅和阅读状态, so that 我可以无缝切换设备继续阅读。

#### Acceptance Criteria

1. WHEN a 用户在一台设备上添加订阅 THEN the Sync_Service SHALL 将订阅同步到用户的所有设备
2. WHEN a 用户在一台设备上标记文章已读 THEN the Sync_Service SHALL 将阅读状态同步到所有设备
3. WHEN a 多台设备同时修改同一数据 THEN the Sync_Service SHALL 使用时间戳解决冲突并保留最新修改
4. WHEN a 设备首次登录 THEN the Sync_Service SHALL 下载用户的完整订阅和文章数据

### Requirement 10: 自定义 RSS 规则

**User Story:** As a 用户, I want to 为不支持 RSS 的网站创建自定义抓取规则, so that 我可以订阅任何网站的内容更新。

#### Acceptance Criteria

1. WHEN a 用户创建自定义规则并指定目标 URL 和 CSS 选择器 THEN the RSS_Manager SHALL 保存规则并开始按规则抓取内容
2. WHEN a 自定义规则执行抓取 THEN the RSS_Manager SHALL 根据选择器提取标题、链接、内容和发布时间
3. WHEN a 用户编辑自定义规则 THEN the RSS_Manager SHALL 更新规则并在下次抓取时应用新规则
4. WHEN a 用户删除自定义规则 THEN the RSS_Manager SHALL 停止抓取并移除规则（保留已抓取的文章）
5. WHEN a 用户测试自定义规则 THEN the RSS_Manager SHALL 执行一次抓取并返回预览结果供用户验证
6. WHEN a 自定义规则抓取失败 THEN the RSS_Manager SHALL 记录错误并在下次调度时重试

### Requirement 11: 内容更新调度

**User Story:** As a 用户, I want to 系统自动定期更新订阅内容, so that 我可以及时获取最新文章。

#### Acceptance Criteria

1. WHEN a 订阅源到达更新间隔时间 THEN the RSS_Manager SHALL 自动抓取该订阅源的最新内容
2. WHEN a 用户设置订阅源的更新频率 THEN the RSS_Manager SHALL 按指定频率调度更新任务
3. WHEN a 用户手动触发刷新 THEN the RSS_Manager SHALL 立即抓取指定订阅源或所有订阅源的最新内容
4. WHEN a 新文章被抓取 THEN the RSS_Manager SHALL 将文章添加到列表并标记为未读状态

### Requirement 12: 搜索功能

**User Story:** As a 用户, I want to 搜索我订阅的文章, so that 我可以快速找到特定内容。

#### Acceptance Criteria

1. WHEN a 用户输入搜索关键词 THEN the RSS_Manager SHALL 在文章标题和内容中搜索并返回匹配结果
2. WHEN a 用户指定搜索范围（全部/分类/订阅源） THEN the RSS_Manager SHALL 仅在指定范围内搜索
3. WHEN a 搜索无结果 THEN the RSS_Manager SHALL 返回空列表并提示无匹配内容


### Requirement 13: AI 渠道管理

**User Story:** As a 用户, I want to 配置多个 AI 服务渠道, so that 我可以灵活选择和切换不同的 AI 提供商。

#### Acceptance Criteria

1. WHEN a 用户添加 AI 渠道并提供名称、类型和 API Key THEN the RSS_Manager SHALL 保存渠道配置并验证连接有效性
2. WHEN a 用户添加 OpenAI 兼容的第三方渠道 THEN the RSS_Manager SHALL 支持自定义 API 端点地址
3. WHEN a 渠道配置保存成功 THEN the RSS_Manager SHALL 自动获取该渠道下所有可用的模型列表
4. WHEN a 用户编辑渠道配置 THEN the RSS_Manager SHALL 更新配置并重新验证连接
5. WHEN a 用户删除 AI 渠道 THEN the RSS_Manager SHALL 移除渠道及其关联的模型配置
6. IF a API Key 无效或连接失败 THEN the RSS_Manager SHALL 提示具体错误信息并保留配置供用户修改

### Requirement 14: AI 模型管理

**User Story:** As a 用户, I want to 管理各渠道下的 AI 模型, so that 我可以选择最适合的模型进行内容处理。

#### Acceptance Criteria

1. WHEN a 渠道连接成功 THEN the RSS_Manager SHALL 自动获取并显示该渠道所有可用模型
2. WHEN a 用户手动添加模型 THEN the RSS_Manager SHALL 将模型添加到指定渠道的模型列表
3. WHEN a 用户编辑模型信息（名称、描述） THEN the RSS_Manager SHALL 更新模型配置
4. WHEN a 用户删除模型 THEN the RSS_Manager SHALL 从列表中移除该模型
5. WHEN a 用户设置默认模型 THEN the RSS_Manager SHALL 将该模型标记为系统默认调用模型
6. WHEN a 默认模型所属渠道被删除 THEN the RSS_Manager SHALL 清除默认模型设置并提示用户重新选择

### Requirement 15: AI 翻译功能

**User Story:** As a 用户, I want to 使用 AI 翻译外语文章, so that 我可以阅读不同语言的内容。

#### Acceptance Criteria

1. WHEN a 用户为分类或订阅源启用自动翻译 THEN the AI_Service SHALL 在文章抓取后自动翻译内容
2. WHEN a 用户手动请求翻译单篇文章 THEN the AI_Service SHALL 调用默认模型翻译文章并保存译文
3. WHEN a 用户指定目标语言 THEN the AI_Service SHALL 将文章翻译为指定语言
4. WHEN a 翻译完成 THEN the RSS_Manager SHALL 同时保留原文和译文供用户切换查看
5. IF a 翻译请求失败 THEN the RSS_Manager SHALL 记录错误并保留原文内容

### Requirement 16: AI 摘要功能

**User Story:** As a 用户, I want to 使用 AI 生成文章摘要, so that 我可以快速了解文章要点。

#### Acceptance Criteria

1. WHEN a 用户为分类或订阅源启用自动摘要 THEN the AI_Service SHALL 在文章抓取后自动生成摘要
2. WHEN a 用户手动请求生成摘要 THEN the AI_Service SHALL 调用默认模型生成文章摘要
3. WHEN a 摘要生成完成 THEN the RSS_Manager SHALL 将摘要与文章关联并在列表中显示
4. WHEN a 用户查看文章详情 THEN the RSS_Manager SHALL 显示 AI 生成的摘要（如有）
5. IF a 摘要生成失败 THEN the RSS_Manager SHALL 记录错误并显示原有摘要或内容预览
