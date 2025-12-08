# RSS 订阅管理器

一个功能完善的 RSS 订阅管理器，支持多用户、分类管理、定时抓取、自定义抓取规则以及 AI 翻译和摘要功能。

## 功能特性

- 📰 RSS/Atom 订阅源管理
- 📁 分类管理
- 📖 文章阅读（已读/未读、收藏）
- 🔍 全文搜索和排序
- ⏰ 定时自动抓取（可设置 1 分钟 - 24 小时间隔）
- 🌐 Playwright 浏览器模式（支持 Cloudflare 保护的网站）
- 🤖 AI 自动翻译和整理（支持 OpenAI、Gemini 及兼容 API）
- 🕷️ 自定义抓取规则
- 📦 OPML 导入导出
- 💾 配置备份恢复

## 技术栈

| 后端 | 前端 |
|------|------|
| Python 3.11+ | React 18 |
| FastAPI | TypeScript |
| SQLAlchemy 2.0 | TailwindCSS |
| Celery + Redis | React Query |
| PostgreSQL / SQLite | Zustand |

## 快速开始

### 方式一：生产环境部署（Docker 一键启动，推荐）

只需安装 Docker，几条命令启动所有服务：

```bash
# 1. 启动所有服务
docker compose -f docker-compose.prod.yml up -d

# 2. 初始化数据库（首次部署必须执行）
docker exec -it rss_manager_backend alembic upgrade head
```

启动后访问：http://localhost:5666

包含的服务：
- PostgreSQL 数据库
- Redis 缓存
- 后端 API
- Celery 定时任务（自动抓取订阅源）
- 前端界面

停止服务：
```bash
docker compose -f docker-compose.prod.yml down
```

**更新代码后重新部署：**
```bash
# 拉取最新代码后，重建并重启所有服务
docker compose -f docker-compose.prod.yml up -d --build

# 如果有数据库结构变更，执行迁移
docker exec -it rss_manager_backend alembic upgrade head
```

> ⚠️ 如果只重建单个服务（如 `--build backend`），需要同时重启 frontend，否则 nginx 会因 DNS 缓存连接失败：
> ```bash
> docker compose -f docker-compose.prod.yml up -d --build backend
> docker restart rss_manager_frontend
> ```

### 方式二：开发环境（SQLite，无需 Docker）

适合本地开发调试，不支持定时抓取功能。

**后端设置：**
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate          # Linux/Mac: source venv/bin/activate
pip install -e ".[dev]"
copy .env.sqlite .env            # Linux/Mac: cp .env.sqlite .env
alembic upgrade head
uvicorn app.main:app --reload
```

**前端设置（新终端）：**
```bash
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173

### 方式三：开发环境 + 定时抓取（需要 Docker）

使用 Docker 运行 PostgreSQL 和 Redis，本地运行代码。

**1. 启动数据库：**
```bash
docker compose up -d postgres redis
```

**2. 后端设置：**
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -e ".[dev]"
copy .env.postgres .env
alembic upgrade head
uvicorn app.main:app --reload
```

**3. 启动定时任务（新终端）：**
```bash
cd backend
.\venv\Scripts\activate
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
```

**4. 启动调度器（新终端）：**
```bash
cd backend
.\venv\Scripts\activate
celery -A app.tasks.celery_app beat --loglevel=info
```

**5. 前端设置（新终端）：**
```bash
cd frontend
npm install
npm run dev
```

> Windows 上 Celery Worker 需要 `--pool=solo` 参数

## 定时任务说明

| 任务 | 执行频率 | 说明 |
|------|---------|------|
| 订阅源刷新 | 每分钟检查 | 根据每个订阅源设置的同步间隔自动抓取 |
| 自定义规则 | 每分钟检查 | 根据规则设置的间隔执行 |
| 旧文章清理 | 每天凌晨 3 点 | 清理 90 天前的非收藏文章 |

## 默认配置

**开发环境 (docker-compose.yml)：**
- PostgreSQL: 用户 `rss_manager`，密码 `rss_manager_password`
- Redis: 无密码

**生产环境 (docker-compose.prod.yml)：**
- PostgreSQL: 用户 `rss_manager`，密码 `rss_manager_prod_2024`
- Redis: 密码 `redis_prod_2024`
- JWT 密钥: `rss_manager_secret_key_2024_production`

> 部署到公网服务器时，建议通过环境变量修改默认密码

## 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面（生产） | http://localhost:5666 |
| 前端界面（开发） | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

## 项目结构

```
├── backend/                 # Python FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── repositories/   # 数据访问层
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 业务逻辑
│   │   ├── tasks/          # Celery 后台任务
│   │   └── utils/          # 工具函数
│   └── alembic/            # 数据库迁移
├── frontend/               # React 前端
│   └── src/
│       ├── components/     # UI 组件
│       ├── pages/          # 页面组件
│       ├── services/       # API 服务
│       ├── stores/         # 状态管理
│       └── types/          # TypeScript 类型
├── docker-compose.yml      # 开发环境 Docker 配置
└── docker-compose.prod.yml # 生产环境 Docker 配置
```

## 开源协议

MIT
