# RSS Manager 桌面版架构说明

## 架构对比

### Web 版（原版）

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Browser   │────▶│   FastAPI    │────▶│ PostgreSQL │
│  (React)    │◀────│   Backend    │◀────│  + Redis   │
└─────────────┘     └──────────────┘     └────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Celery    │
                    │   Workers    │
                    └──────────────┘
```

**特点**：
- 多用户系统（JWT 认证）
- PostgreSQL + pgvector（语义搜索）
- Redis + Celery（分布式任务队列）
- 需要 Docker 或手动配置服务

### 桌面版

```
┌─────────────────────────────────────┐
│         PyWebView Window            │
│  ┌───────────────────────────────┐  │
│  │      React Frontend           │  │
│  │      (Static Files)           │  │
│  └───────────────────────────────┘  │
│                 │                    │
│                 ▼                    │
│  ┌───────────────────────────────┐  │
│  │      FastAPI Backend          │  │
│  │   (Embedded in Process)       │  │
│  └───────────────────────────────┘  │
│                 │                    │
│                 ▼                    │
│  ┌───────────────────────────────┐  │
│  │       APScheduler             │  │
│  │    (Background Tasks)         │  │
│  └───────────────────────────────┘  │
│                 │                    │
│                 ▼                    │
│  ┌───────────────────────────────┐  │
│  │    SQLite Database            │  │
│  │  (%APPDATA%\RSSManager\)      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**特点**：
- 单用户模式（无需认证）
- SQLite（本地数据库）
- APScheduler（内置定时任务）
- 单个可执行文件
- 数据存储在用户目录

## 核心组件

### 1. PyWebView 窗口管理器

**文件**: `desktop/backend/main_desktop.py`

**功能**：
- 创建原生窗口
- 嵌入 FastAPI 服务器
- 管理应用生命周期

**关键代码**：
```python
class DesktopApp:
    def start_server(self):
        # 在后台线程启动 FastAPI
        
    def start(self):
        # 创建 PyWebView 窗口
        window = webview.create_window(
            title="RSS Manager",
            url="http://127.0.0.1:8765",
            width=1280,
            height=800
        )
        webview.start()
```

### 2. FastAPI 后端（简化版）

**文件**: `desktop/backend/app/main_desktop.py`

**变化**：
- 移除认证中间件
- 移除 auth 和 oauth 路由
- 添加静态文件服务
- 集成 APScheduler

**关键代码**：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    await init_db()
    # 创建默认用户
    await ensure_default_user()
    # 启动定时任务
    await scheduler.start()
    yield
    # 停止定时任务
    await scheduler.stop()
```

### 3. APScheduler 定时任务

**文件**: `desktop/backend/app/scheduler/scheduler.py`

**功能**：
- 替代 Celery + Redis
- 订阅源定时抓取
- 自定义规则执行
- 旧文章清理

**任务列表**：
```python
# 每分钟检查订阅源
scheduler.add_job(check_feeds, IntervalTrigger(minutes=1))

# 每分钟检查自定义规则
scheduler.add_job(check_custom_rules, IntervalTrigger(minutes=1))

# 每天凌晨 3 点清理旧文章
scheduler.add_job(cleanup_old_articles, CronTrigger(hour=3))
```

### 4. 单用户模式

**文件**: `desktop/backend/app/core/deps_desktop.py`

**实现**：
```python
async def get_current_user_id() -> int:
    """Always return user_id = 1"""
    return 1
```

**影响**：
- 所有 API 自动使用 user_id = 1
- 无需 JWT token
- 无需登录/注册

### 5. 配置管理

**文件**: `desktop/backend/app/core/config_desktop.py`

**特点**：
- 数据库路径：`%APPDATA%\RSSManager\rss_manager.db`
- 无需 Redis 配置
- 桌面模式标志

**关键配置**：
```python
class DesktopSettings(BaseSettings):
    DESKTOP_MODE: bool = True
    SINGLE_USER_MODE: bool = True
    
    @property
    def DATABASE_URL(self) -> str:
        db_path = get_app_data_dir() / "rss_manager.db"
        return f"sqlite+aiosqlite:///{db_path}"
```

### 6. 前端适配

**补丁文件**：
- `authStore.desktop.ts` - 移除认证状态管理
- `api.desktop.ts` - 移除认证拦截器
- `App.desktop.tsx` - 移除登录路由

**变化**：
```typescript
// 桌面版：始终认证
export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: true,
  user: { id: 1, username: 'Desktop User' },
}))
```

## 打包流程

### 1. 前端构建

```bash
cd frontend
npm run build
# 输出: frontend/dist/
```

### 2. 前端补丁

```bash
python desktop/build/patch_frontend.py
# 替换认证相关文件
```

### 3. 重新构建前端

```bash
cd frontend
npm run build
# 输出: desktop/frontend/
```

### 4. 后端文件复制

```bash
# 复制 backend/app/ 到 desktop/backend/app/
# 保留桌面版特有文件
```

### 5. PyInstaller 打包

```bash
pyinstaller desktop/build/main.spec
# 输出: desktop/dist/RSSManager/
```

### 6. 创建安装程序

```bash
iscc desktop/installer/setup.iss
# 输出: desktop/installer/output/RSSManager-Setup-1.0.0.exe
```

## 数据流

### 启动流程

```
1. 用户启动 RSSManager.exe
   ↓
2. PyInstaller 解压到临时目录
   ↓
3. 执行 main_desktop.py
   ↓
4. 启动 FastAPI 服务器（后台线程）
   ↓
5. 初始化数据库（%APPDATA%\RSSManager\）
   ↓
6. 创建默认用户（user_id = 1）
   ↓
7. 启动 APScheduler
   ↓
8. 创建 PyWebView 窗口
   ↓
9. 加载前端（http://127.0.0.1:8765）
   ↓
10. 用户开始使用
```

### API 请求流程

```
前端组件
   ↓
axios.get('/api/v1/feeds')
   ↓
FastAPI 路由
   ↓
get_current_user_id() → 返回 1
   ↓
FeedService(user_id=1)
   ↓
SQLite 数据库
   ↓
返回数据
```

### 定时任务流程

```
APScheduler
   ↓
每分钟触发 check_feeds()
   ↓
查询所有订阅源
   ↓
检查是否需要抓取
   ↓
FeedService.fetch_feed(feed_id, user_id=1)
   ↓
下载并解析 RSS
   ↓
保存文章到数据库
```

## 性能优化

### 1. 减小包体积

- 排除不需要的模块（Celery, Redis, PostgreSQL）
- 使用 UPX 压缩
- 只包含 Chromium 浏览器（Playwright）

### 2. 启动速度

- 延迟加载 Playwright
- 异步初始化数据库
- 后台启动定时任务

### 3. 运行性能

- SQLite WAL 模式
- 连接池优化
- 定时任务间隔控制

## 安全考虑

### 1. 本地数据

- 数据库文件存储在用户目录
- 仅当前用户可访问
- 无网络暴露

### 2. API 安全

- 仅监听 127.0.0.1
- 不接受外部连接
- 无需认证（单用户）

### 3. AI API Key

- 存储在本地数据库
- 不传输到其他服务器
- 用户自行管理

## 限制和权衡

### 功能限制

| 功能 | Web 版 | 桌面版 | 说明 |
|------|--------|--------|------|
| 多用户 | ✅ | ❌ | 桌面版单用户 |
| 语义搜索 | ✅ | ❌ | 降级为关键词搜索 |
| 分布式任务 | ✅ | ❌ | 使用本地定时任务 |
| 远程访问 | ✅ | ❌ | 仅本地访问 |

### 性能权衡

| 指标 | Web 版 | 桌面版 |
|------|--------|--------|
| 启动时间 | 快（服务常驻） | 慢（需要启动） |
| 内存占用 | 低（共享） | 高（独立进程） |
| 并发能力 | 高 | 低 |
| 数据库性能 | 高（PostgreSQL） | 中（SQLite） |

### 适用场景

**Web 版适合**：
- 多用户团队使用
- 需要远程访问
- 大量订阅源（1000+）
- 需要语义搜索

**桌面版适合**：
- 个人使用
- 本地数据管理
- 无需配置服务器
- 便携使用

## 未来改进

### 短期

- [ ] 添加自动更新功能
- [ ] 优化启动速度
- [ ] 减小包体积
- [ ] 添加系统托盘

### 长期

- [ ] macOS 版本
- [ ] Linux 版本
- [ ] 离线 AI 模型
- [ ] 本地向量搜索（使用 ChromaDB）
