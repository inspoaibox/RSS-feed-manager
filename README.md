# RSS 订阅管理器

一个功能完善的 RSS 订阅管理器，支持多用户、分类管理、定时抓取、自定义抓取规则以及 AI 翻译和摘要功能。

项目地址：[https://github.com/inspoaibox/RSS-feed-manager](https://github.com/inspoaibox/RSS-feed-manager)

## 功能特性

- 📰 RSS/Atom 订阅源管理
- 📁 分类管理
- 📖 文章阅读（已读/未读、收藏）
- 🔍 全文搜索和排序
- ⏰ 定时自动抓取（可设置 1 分钟 - 24 小时间隔）
- 🌐 Playwright 浏览器模式（支持 Cloudflare 保护的网站）
- 🤖 AI 自动翻译和整理（支持 OpenAI、Gemini 及兼容 API）
- 🧠 **AI 智能内容分析**（语义搜索 + AI 总结）
- 🕷️ 自定义抓取规则
- 📦 OPML 导入导出
- 💾 配置备份恢复
- 🏷️ 关键词订阅：按指定关键词自动聚合命中的 RSS 文章

## 技术栈

| 后端 | 前端 |
|------|------|
| Python 3.11+ | React 18 |
| FastAPI | TypeScript |
| SQLAlchemy 2.0 | TailwindCSS |
| Celery + Redis | React Query |
| PostgreSQL + pgvector | Zustand |

## 快速开始

从 GitHub 拉取、GitHub Actions 构建镜像、服务器拉取运行、Nginx/Caddy 反向代理、HTTPS 配置、更新和备份的完整流程见：[GitHub 构建镜像 + Docker Compose 部署完整说明](docs/GITHUB_DOCKER_USAGE.md)。

生产环境推荐流程：

1. 从 GitHub 克隆项目
2. 复制并修改 `.env.production`
3. 等 GitHub Actions 构建并发布 GHCR 镜像
4. 在服务器使用 Docker Compose 拉取镜像并启动服务
5. 通过 `http://服务器IP:5666` 测试访问
6. 使用 Nginx 或 Caddy 反向代理到 `127.0.0.1:5666`
7. 将 `.env.production` 中的 `CORS_ORIGINS` 和 `BASE_URL` 改为最终域名
8. 后续通过 `git pull origin main`、`docker compose pull` 和 `docker compose up -d` 更新

### 方式一：生产环境部署（Docker 一键启动，推荐）

只需安装 Docker，几条命令拉取 GitHub Actions 构建好的镜像并启动所有服务：

```bash
# 1. 复制并编辑生产环境配置
cp .env.production.example .env.production

# 2. 拉取 GitHub Container Registry 镜像
docker compose -f docker-compose.prod.yml --env-file .env.production pull

# 3. 启动所有服务
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

后端容器启动时会自动执行数据库迁移。需要手动确认或重跑迁移时：

```bash
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
# 等 GitHub Actions 构建成功后，在服务器拉取最新配置和镜像
git pull origin main
docker compose -f docker-compose.prod.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# 如需手动确认数据库迁移
docker exec -it rss_manager_backend alembic upgrade head
```

> 如果需要临时在服务器本地构建，可以使用 `docker-compose.prod.build.yml`：
> ```bash
> docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d --build
> ```

**反向代理部署：**

生产环境建议使用独立域名，例如 `https://rss.example.com`，由服务器上的 Nginx/Caddy 代理到本机 `127.0.0.1:5666`。项目内部的前端 Nginx 已经负责把 `/api/` 转发给后端容器，因此外层反向代理只需要代理前端入口。完整 Nginx、Caddy 和 HTTPS 示例见：[反向代理说明](docs/GITHUB_DOCKER_USAGE.md#7-使用-nginx-反向代理)。

### 方式二：开发环境（SQLite，无需 Docker）

适合本地开发调试，不支持定时抓取功能和 AI 语义搜索（会自动回退到关键词搜索）。

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

## AI 智能内容分析

AI 分析功能允许你使用自然语言查询订阅的文章内容，系统会通过语义搜索找到相关文章，并生成 AI 分析总结。

### 功能特点

- 🔍 **语义搜索**：基于 pgvector 向量数据库，理解查询意图而非简单关键词匹配
- 📊 **AI 分析总结**：自动生成主题分类、关键点提取、趋势识别
- 📈 **相关度排序**：按语义相似度排序，最相关的文章优先展示
- 📝 **查询历史**：保存最近 10 条查询，支持快速重新执行
- 🔄 **智能回退**：当语义搜索不可用时，自动回退到关键词搜索

### 使用方法

1. 在侧边栏点击「AI 分析」进入分析页面
2. 在搜索框输入自然语言查询，例如：
   - "Python 相关的技术文章"
   - "最近的 AI 发展趋势"
   - "前端框架对比"
3. 点击「分析」按钮，等待 AI 处理
4. 查看 AI 生成的分析总结和相关文章列表

### 技术要求

- **数据库**：需要使用 PostgreSQL + pgvector（生产环境 Docker 配置已包含）
- **AI 服务**：需要配置 OpenAI 或兼容的 AI 服务（用于生成 embedding 和分析）
- **注意**：SQLite 开发模式不支持语义搜索，会自动回退到关键词搜索

### 配置 Embedding 模型

1. 进入「设置 → AI 设置」
2. 在「Embedding 模型」区域选择 AI 渠道
3. 输入 embedding 模型名称（如 `text-embedding-3-small`）
4. 点击「保存 Embedding 配置」

常用 Embedding 模型：
- `text-embedding-3-small` - OpenAI 推荐，性价比高
- `text-embedding-3-large` - 更高精度
- `text-embedding-ada-002` - 旧版模型

### Embedding 生成

文章的向量嵌入（embedding）通过 Celery 后台任务异步生成：
- 需要先配置 Embedding 模型才能生成
- 批量生成任务：`generate_embeddings_batch`（通过 Celery 调用）
- embedding 生成失败不会影响文章保存，会自动回退到关键词搜索

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

## 注意事项

### 部署相关
- 项目可以安装在任意目录，没有路径限制
- 端口 5666 需要可用，如需修改请编辑 `docker-compose.prod.yml` 中的端口映射
- 后端容器启动时会自动执行数据库迁移，也可手动运行：`docker exec -it rss_manager_backend alembic upgrade head`
- 首个注册的用户将自动成为管理员

### 更新部署
- 修改代码后，先推送到 GitHub 并等待 Actions 构建镜像成功，再在服务器拉取最新镜像并重启：
  ```bash
  git pull origin main
  docker compose -f docker-compose.prod.yml --env-file .env.production pull
  docker compose -f docker-compose.prod.yml --env-file .env.production up -d
  ```
- 如果修改了 Celery 任务、RSS 抓取逻辑或定时任务逻辑，也按同一套流程更新；`backend`、`celery_worker`、`celery_beat` 会使用同一个后端镜像。
- 如需临时在服务器本地构建，可参考 [本地构建说明](docs/GITHUB_DOCKER_USAGE.md#14-需要在服务器本地构建时)。
- **数据库结构变更时**，必须执行迁移：
  ```bash
  docker exec -it rss_manager_backend alembic upgrade head
  ```

### 从旧版本升级（添加 AI 分析功能）
如果你是从不支持 AI 分析的旧版本升级，需要执行以下步骤：
```bash
# 1. 备份数据库（可选但推荐）
docker exec rss_manager_postgres pg_dump -U rss_manager rss_manager > backup.sql

# 2. 拉取最新代码
git pull origin main

# 3. 等 GitHub Actions 构建成功后，拉取镜像并启动
docker compose -f docker-compose.prod.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# 4. 执行数据库迁移（添加 embedding 列和查询历史表）
docker exec -it rss_manager_backend alembic upgrade head
```
> 数据不会丢失，pgvector 镜像与原 PostgreSQL 镜像完全兼容

### 安全建议
- 公网部署时务必修改默认密码（通过环境变量设置）
- 建议使用反向代理（如 Nginx）并配置 HTTPS
- 可以关闭注册功能（管理员在设置页面操作）

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
