# GitHub + Docker 安装、构建、反向代理与更新完整说明

本文档说明如何从 GitHub 仓库安装 RSS Feed Manager，并在服务器上使用 Docker Compose 构建、运行、反向代理、更新和维护。

项目地址：[https://github.com/inspoaibox/RSS-feed-manager](https://github.com/inspoaibox/RSS-feed-manager)

## 1. 部署架构

生产环境推荐使用 `docker-compose.prod.yml` 一键启动所有服务。

```text
公网用户
  |
  | HTTPS / HTTP
  v
服务器 Nginx / Caddy 反向代理
  |
  | http://127.0.0.1:5666
  v
frontend 容器内置 Nginx
  |-- 静态前端页面
  |-- /api/ 代理到 backend:8000
  |
  +--> backend 容器 FastAPI
       |
       +--> PostgreSQL + pgvector
       +--> Redis
       +--> Celery Worker / Beat
```

外层反向代理只需要代理到宿主机 `5666` 端口。项目内部的前端 Nginx 已经负责把 `/api/` 转发给后端容器，不需要把后端 `8000` 端口暴露到公网。

## 2. 准备服务器环境

服务器需要安装：

- Git
- Docker Engine
- Docker Compose v2
- 可选：Nginx、Caddy 或其他反向代理服务

检查版本：

```bash
git --version
docker --version
docker compose version
```

建议系统：

- Ubuntu 22.04 / 24.04
- Debian 12
- 其他支持 Docker Compose v2 的 Linux 发行版

如果是云服务器，请在安全组或防火墙中放行：

- `80/tcp`：HTTP，用于访问或申请证书
- `443/tcp`：HTTPS
- `5666/tcp`：仅在不使用反向代理、直接通过 `IP:5666` 访问时需要放行

使用反向代理后，建议只放行 `80` 和 `443`，不要把 `5666` 暴露到公网。

## 3. 拉取项目代码

首次安装：

```bash
git clone https://github.com/inspoaibox/RSS-feed-manager.git
cd RSS-feed-manager
```

如果已经克隆过：

```bash
cd RSS-feed-manager
git pull origin main
```

建议确认当前分支：

```bash
git branch --show-current
```

正常应显示：

```text
main
```

## 4. 配置生产环境变量

复制生产环境示例文件：

```bash
cp .env.production.example .env.production
```

Windows PowerShell：

```powershell
Copy-Item .env.production.example .env.production
```

编辑 `.env.production`：

```bash
nano .env.production
```

至少修改以下配置：

```env
POSTGRES_PASSWORD=请改成强数据库密码
REDIS_PASSWORD=请改成强Redis密码
SECRET_KEY=请改成至少32位随机字符串
CORS_ORIGINS=["http://你的服务器IP:5666"]
BASE_URL=http://你的服务器IP:5666
```

生成 `SECRET_KEY`：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

如果使用域名和 HTTPS，例如 `https://rss.example.com`：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

如果需要同时允许多个访问地址：

```env
CORS_ORIGINS=["https://rss.example.com","http://服务器IP:5666"]
```

重要说明：

- `POSTGRES_PASSWORD` 和 `REDIS_PASSWORD` 首次启动后会写入 Docker 数据卷。后续直接修改密码可能导致旧数据库连接失败，修改前请先备份数据。
- `BASE_URL` 会影响 OAuth 回调等需要生成外部 URL 的功能，使用域名访问时应填写最终公网地址。
- 公网部署时不要继续使用示例里的默认密码和默认密钥。

## 5. 构建并启动服务

首次构建并启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

这个命令会构建并启动：

- `rss_manager_postgres`：PostgreSQL + pgvector 数据库
- `rss_manager_redis`：Redis
- `rss_manager_backend`：FastAPI 后端
- `rss_manager_celery_worker`：后台任务 Worker
- `rss_manager_celery_beat`：定时任务调度器
- `rss_manager_frontend`：前端 Nginx 与静态文件

查看容器状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

查看启动日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```

后端容器启动时会自动执行数据库迁移：

```bash
alembic upgrade head
```

如需手动检查或重新执行迁移：

```bash
docker exec -it rss_manager_backend alembic current
docker exec -it rss_manager_backend alembic upgrade head
```

## 6. 直接访问测试

如果暂时不配置反向代理，可以直接访问：

```text
http://服务器IP:5666
```

本机部署时：

```text
http://localhost:5666
```

也可以在服务器上用命令测试：

```bash
curl -I http://127.0.0.1:5666
```

首次注册的用户会自动成为管理员。管理员可以在「设置」中关闭注册、配置 AI 渠道、调整同步间隔和通知。

## 7. 使用 Nginx 反向代理

反向代理适合域名访问和 HTTPS 部署。假设你的域名是：

```text
rss.example.com
```

请先把域名 DNS 的 `A` 记录解析到服务器公网 IP。

### 7.1 推荐：只让本机访问 5666 端口

如果只通过 Nginx/Caddy 对外提供访问，可以把 `docker-compose.prod.yml` 中前端端口映射从：

```yaml
ports:
  - "5666:80"
```

改成：

```yaml
ports:
  - "127.0.0.1:5666:80"
```

然后重建启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

这样外部用户不能直接访问 `服务器IP:5666`，只能通过反向代理访问。

### 7.2 Nginx HTTP 配置

创建站点配置：

```bash
sudo nano /etc/nginx/sites-available/rss-feed-manager
```

写入以下内容，并把 `rss.example.com` 改成你的域名：

```nginx
server {
    listen 80;
    server_name rss.example.com;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:5666;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/rss-feed-manager /etc/nginx/sites-enabled/rss-feed-manager
sudo nginx -t
sudo systemctl reload nginx
```

访问：

```text
http://rss.example.com
```

### 7.3 Nginx HTTPS 配置

如果使用 Certbot 申请证书：

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d rss.example.com
```

Certbot 通常会自动修改 Nginx 配置并启用 HTTPS。完成后访问：

```text
https://rss.example.com
```

确认自动续期：

```bash
sudo certbot renew --dry-run
```

HTTPS 可用后，请同步修改 `.env.production`：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

然后重建并重启服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

### 7.4 Nginx 子路径部署说明

不推荐把项目部署到子路径，例如：

```text
https://example.com/rss/
```

当前前端 API 使用 `/api/v1` 绝对路径，生产环境默认按域名根路径部署。推荐使用独立子域名：

```text
https://rss.example.com
```

## 8. 使用 Caddy 反向代理

Caddy 可以自动申请和续期 HTTPS 证书。安装 Caddy 后编辑：

```bash
sudo nano /etc/caddy/Caddyfile
```

写入：

```caddyfile
rss.example.com {
    reverse_proxy 127.0.0.1:5666
}
```

重载 Caddy：

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

然后在 `.env.production` 中配置：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

重建并重启：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 9. 更新到最新版本

更新前建议先备份数据库：

```bash
docker exec rss_manager_postgres pg_dump -U rss_manager rss_manager > rss_manager_backup_$(date +%F_%H-%M-%S).sql
```

拉取最新代码并重建：

```bash
cd RSS-feed-manager
git pull origin main
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

检查服务状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker logs --tail 100 rss_manager_backend
```

确认数据库迁移：

```bash
docker exec -it rss_manager_backend alembic current
docker exec -it rss_manager_backend alembic upgrade head
```

更新完成后访问站点，确认可以登录、文章列表可以打开、订阅刷新功能正常。

## 10. 只更新某一类服务

推荐大多数情况下直接重建所有服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

如果你明确只修改了前端：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build frontend
```

如果你修改了后端 API：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build backend
```

如果你修改了 Celery 任务、RSS 抓取逻辑、定时任务逻辑，必须同时重建并重启：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build backend celery_worker celery_beat
```

如果只重建后端后发现前端访问 API 异常，可以重启前端容器刷新容器内 Nginx 的上游解析：

```bash
docker restart rss_manager_frontend
```

## 11. 修改配置后的重启方式

修改 `.env.production` 后，推荐执行：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

如果只修改了不影响镜像构建的环境变量，也可以：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

但为了减少配置未生效的排查成本，生产更新时推荐使用 `--build`。

## 12. 数据备份和恢复

备份 PostgreSQL：

```bash
docker exec rss_manager_postgres pg_dump -U rss_manager rss_manager > rss_manager_backup.sql
```

如果 `.env.production` 中修改了数据库用户或库名，请替换命令中的 `rss_manager`。

恢复备份：

```bash
cat rss_manager_backup.sql | docker exec -i rss_manager_postgres psql -U rss_manager rss_manager
```

Windows PowerShell 恢复：

```powershell
Get-Content rss_manager_backup.sql | docker exec -i rss_manager_postgres psql -U rss_manager rss_manager
```

也可以在应用的「设置 -> 备份恢复」中导出或导入配置。

## 13. 常用运维命令

查看全部日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```

查看后端日志：

```bash
docker logs -f rss_manager_backend
```

查看 Celery Worker 日志：

```bash
docker logs -f rss_manager_celery_worker
```

查看 Celery Beat 日志：

```bash
docker logs -f rss_manager_celery_beat
```

重启所有服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

停止服务但保留数据：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

停止服务并删除数据库、Redis 数据卷：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down -v
```

清理未使用镜像：

```bash
docker image prune
```

## 14. 常见问题

### 14.1 端口 5666 被占用

查看占用：

```bash
sudo ss -lntp | grep 5666
```

可以修改 `docker-compose.prod.yml` 中的端口映射，例如改为 `8080`：

```yaml
ports:
  - "8080:80"
```

使用反向代理时，也要同步把代理地址改为：

```nginx
proxy_pass http://127.0.0.1:8080;
```

### 14.2 容器启动失败

查看服务状态和日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs backend
docker compose -f docker-compose.prod.yml --env-file .env.production logs frontend
```

### 14.3 数据库连接失败

检查 PostgreSQL 是否健康：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps postgres
docker logs --tail 100 rss_manager_postgres
```

常见原因：

- `.env.production` 中数据库用户名、密码、库名和已创建的数据卷不一致
- 首次启动时数据库还未完成初始化
- 修改过数据库密码但没有同步处理旧数据卷

### 14.4 RSS 抓取或自定义规则不执行

确认 Worker 和 Beat 正常：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps celery_worker celery_beat
docker logs -f rss_manager_celery_worker
docker logs -f rss_manager_celery_beat
```

如果修改过抓取相关代码，请重建：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build backend celery_worker celery_beat
```

### 14.5 域名访问正常，但登录或 OAuth 回调异常

检查 `.env.production`：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

修改后重启：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

### 14.6 Nginx 反向代理后接口 502

先确认本机端口可访问：

```bash
curl -I http://127.0.0.1:5666
```

再检查 Nginx 配置：

```bash
sudo nginx -t
sudo journalctl -u nginx --no-pager -n 100
```

如果 `docker-compose.prod.yml` 里把端口改成了其他值，Nginx 的 `proxy_pass` 也必须同步修改。

### 14.7 修改 `.env.production` 后不生效

执行：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

然后查看后端容器环境变量是否正确传入：

```bash
docker exec rss_manager_backend env | grep BASE_URL
docker exec rss_manager_backend env | grep CORS_ORIGINS
```

## 15. 卸载项目

停止并删除容器，但保留数据卷：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

彻底删除容器和数据卷：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down -v
```

删除项目目录：

```bash
cd ..
rm -rf RSS-feed-manager
```

执行 `down -v` 会删除数据库和 Redis 数据，请确认已经备份。
