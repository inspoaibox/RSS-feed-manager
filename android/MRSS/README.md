# MRSS Android

MRSS 是基于根目录 RSS Manager 逻辑拆出的 Android 单机客户端。它不再连接独立服务器，也不包含登录、注册、多用户或管理员系统；手机上的本地数据库就是唯一数据源。

## 迁移原则

- 单用户：删除 Web 版的 `users`、JWT、登录注册、OAuth、管理员权限。
- 本地数据：使用 Android SQLite 保存订阅源、分类、文章和阅读状态。
- 本地服务端化：手机端自己抓取 RSS、解析、入库和定时同步，不依赖 FastAPI/Celery/Redis/PostgreSQL。
- 文章状态：`is_read`、`is_favorite` 直接存在文章表，不再使用 Web 版的 `user_articles` 关联表。
- 后台刷新：使用 Android 系统闹钟触发同步，后续可替换为 WorkManager。

## 当前雏形功能

- 添加 RSS/Atom 订阅
- 手动刷新全部订阅
- 本地定时刷新
- 后台同步开关与新订阅默认同步间隔
- 分类创建、重命名、删除
- 按分类和订阅源筛选文章
- 左侧分类菜单，按分类或具体订阅源快速切换，长按可重命名、编辑或删除
- 订阅标题、分类、同步间隔、启用状态管理
- 删除订阅及其本地文章
- 文章列表、搜索、未读/收藏过滤
- 文章排序：发布时间、抓取时间、标题
- 日期筛选：今天、昨天、最近 7 天
- 阅读文章、自动标记已读、单篇重新标为未读、收藏/取消收藏
- OPML 导入导出
- JSON 全量备份恢复（分类、订阅、文章、已读/收藏状态）
- 本地统计：分类、订阅、文章、未读、收藏、今日新增、最近 7 天
- 按当前分类或订阅源范围刷新
- 卡片式文章列表，显示标题、摘要、来源和时间
- 分页加载文章，默认每页 50 篇
- 后台同步发现新文章时发送系统通知
- 顶部状态栏安全区适配，避免内容顶到电量/信号区域
- 后台定时同步按订阅源间隔计算下一次到期时间；同步执行期间使用前台 dataSync 服务，并提供精准闹钟系统权限入口
- 应用启动时自动补同步所有启用订阅，防止后台被系统杀掉后长期不刷新
- 使用根目录 `11-logo.png` 作为应用图标

## 后台定时说明

Android 手机端不适合做永久常驻后台服务。MRSS 当前采用系统闹钟唤醒，到期后启动前台数据同步服务，抓取完成后退出并安排下一次同步；若系统限制前台服务启动，会使用 JobScheduler 兜底执行。

- 已开启精准闹钟权限时，会尽量按订阅源设置的时间准点触发。
- 未开启精准闹钟、处于 Doze 省电模式、厂商后台限制或网络不可用时，系统可能延迟触发。
- 建议在系统设置中允许 MRSS 通知、精准闹钟，并把电池策略设为不限制，以获得更稳定的后台同步。

## 与原 Web 版的功能对照

已迁移到 Android 本地端：

- RSS/Atom 订阅管理
- 分类管理
- 文章阅读、已读/未读、收藏
- 搜索、排序、日期筛选
- 本地定时刷新
- OPML 导入导出
- 本地备份恢复
- 统计概览

暂未迁移或刻意不迁移：

- 登录、注册、多用户、管理员系统：Android 版明确不需要。
- Redis、Celery、PostgreSQL、FastAPI 服务端：Android 版不需要单独服务器。
- pgvector 语义搜索：手机端暂用关键词搜索。
- AI 翻译/摘要：后续可接入本机保存的 API Key 直接调用 AI 服务。
- 自定义网页抓取规则/Playwright：Android 端需改成 WebView/HTTP 抓取方案，不能直接照搬桌面版 Chromium。
- WebDAV：已有 JSON 本地备份，后续可再加 WebDAV 云端同步。

## 构建

当前机器的 Android SDK 位于 `D:\Android\Sdk`，Gradle 分发位于 `D:\Android\gradle\wrapper\dists\gradle-9.3.1-bin\...`。

可在本目录执行：

```powershell
$env:ANDROID_HOME='D:\Android\Sdk'
& 'D:\Android\gradle\wrapper\dists\gradle-9.3.1-bin\23ovyewtku6u96viwx3xl3oks\gradle-9.3.1\bin\gradle.bat' assembleDebug
```
