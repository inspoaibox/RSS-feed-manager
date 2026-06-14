# GitHub 构建镜像 + Docker Compose 部署完整说明

本文档说明如何从 GitHub 仓库安装 RSS Feed Manager，并使用 GitHub Actions 构建 Docker 镜像、发布到 GitHub Container Registry，再由服务器拉取镜像运行、反向代理和更新。

项目地址：[https://github.com/inspoaibox/RSS-feed-manager](https://github.com/inspoaibox/RSS-feed-manager)

## 1. 部署架构

当前生产部署采用“GitHub 构建，服务器拉取镜像”的方式：

```text
开发者 push 到 main
  |
  v
GitHub Actions
  |-- 构建 backend 镜像
  |-- 构建 frontend 镜像
  v
GitHub Container Registry: ghcr.io
  |
  | docker compose pull
  v
服务器 Docker Compose
  |-- postgres
  |-- redis
  |-- backend
  |-- celery_worker
  |-- celery_browser_worker
  |-- celery_beat
  |-- frontend
  v
Nginx / Caddy 反向代理到 127.0.0.1:5666
```

服务器不再默认执行 `docker compose ... up -d --build`。更新时应先等 GitHub Actions 构建成功，然后在服务器执行 `docker compose pull` 和 `docker compose up -d`。

## 2. GitHub Actions 构建结果

推送到 `main` 后，仓库的 GitHub Actions 会构建并发布两个镜像：

```text
ghcr.io/inspoaibox/rss-feed-manager-backend:latest
ghcr.io/inspoaibox/rss-feed-manager-frontend:latest
```

同时也会发布按提交固定的标签：

```text
ghcr.io/inspoaibox/rss-feed-manager-backend:sha-完整提交SHA
ghcr.io/inspoaibox/rss-feed-manager-frontend:sha-完整提交SHA
```

默认生产环境使用：

```env
RSS_MANAGER_IMAGE_TAG=latest
```

如果需要固定版本或回滚，可以把 `.env.production` 中的标签改为某次提交：

```env
RSS_MANAGER_IMAGE_TAG=sha-完整提交SHA
```

## 3. GHCR 镜像权限

如果 GHCR 包是公开的，服务器可以直接拉取镜像：

```bash
docker pull ghcr.io/inspoaibox/rss-feed-manager-frontend:latest
docker pull ghcr.io/inspoaibox/rss-feed-manager-backend:latest
```

如果服务器拉取时报错 `pull access denied`、`unauthorized` 或 `denied`，通常是 GHCR 包没有公开。处理方式二选一：

1. 在 GitHub 仓库页面进入 `Packages`，把对应 container package 的 visibility 改为 `Public`
2. 在服务器登录 GHCR 后再拉取私有镜像

服务器登录 GHCR：

```bash
echo "你的GitHubToken" | docker login ghcr.io -u 你的GitHub用户名 --password-stdin
```

Token 至少需要 `read:packages` 权限。公开项目推荐把 package 设为公开，部署最省事。

## 4. 准备服务器环境

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

如果是云服务器，请在安全组或防火墙中放行：

- `80/tcp`：HTTP，用于访问或申请证书
- `443/tcp`：HTTPS
- `5666/tcp`：仅在不使用反向代理、直接通过 `IP:5666` 访问时需要放行

使用反向代理后，建议只放行 `80` 和 `443`。

## 5. 拉取项目代码

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

确认当前分支：

```bash
git branch --show-current
```

正常应显示：

```text
main
```

## 6. 配置生产环境变量

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
RSS_MANAGER_IMAGE_TAG=latest
```

生成 `SECRET_KEY`：

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

如果使用域名和 HTTPS，例如 `https://rss.example.com`：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
RSS_MANAGER_IMAGE_TAG=latest
```

重要说明：

- 如果你暂时不创建 `.env.production`，可以省略命令里的 `--env-file .env.production`，Compose 会使用 `docker-compose.prod.yml` 中的默认值。
- `POSTGRES_PASSWORD` 和 `REDIS_PASSWORD` 首次启动后会写入 Docker 数据卷。后续直接修改密码可能导致旧数据库连接失败，修改前请先备份数据。
- `BASE_URL` 会影响 OAuth 回调等需要生成外部 URL 的功能，使用域名访问时应填写最终公网地址。
- `RSS_MANAGER_IMAGE_TAG` 默认使用 GitHub Actions 发布的 `latest` 镜像。

## 7. 启动生产服务

首次启动前，建议先拉取镜像：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production pull
```

启动服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

这个命令会启动：

- `rss_manager_postgres`：PostgreSQL + pgvector 数据库
- `rss_manager_redis`：Redis
- `rss_manager_backend`：FastAPI 后端
- `rss_manager_celery_worker`：普通后台任务 Worker
- `rss_manager_celery_browser_worker`：浏览器抓取 Worker，处理 Playwright/CloakBrowser 队列
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

## 8. 直接访问测试

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

## 9. 从服务器本地构建切换到 GitHub 构建镜像

如果之前服务器上使用的是本地构建命令：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

切换到 GitHub 镜像版本时，按以下步骤操作：

1. 先把代码提交并推送到 `main`
2. 到 GitHub 仓库的 `Actions` 页面确认 `Build and Publish Images` 成功
3. 在服务器拉取最新 compose 配置

```bash
cd RSS-feed-manager
git pull origin main
```

4. 确认 `.env.production` 中有镜像标签

```env
RSS_MANAGER_IMAGE_TAG=latest
```

5. 拉取 GitHub 构建好的镜像

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production pull
```

6. 用新镜像启动服务

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

也可以使用兼容旧更新流程的强制拉取 override：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d
```

7. 检查当前容器使用的镜像

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production images
```

正常应看到：

```text
ghcr.io/inspoaibox/rss-feed-manager-backend
ghcr.io/inspoaibox/rss-feed-manager-frontend
```

## 10. 使用 Nginx 反向代理

反向代理适合域名访问和 HTTPS 部署。假设你的域名是：

```text
rss.example.com
```

请先把域名 DNS 的 `A` 记录解析到服务器公网 IP。

### 10.1 推荐：只让本机访问 5666 端口

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

然后重启服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

这样外部用户不能直接访问 `服务器IP:5666`，只能通过反向代理访问。

### 10.2 Nginx HTTP 配置

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

### 10.3 Nginx HTTPS 配置

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

然后重启服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### 10.4 Nginx 子路径部署说明

不推荐把项目部署到子路径，例如：

```text
https://example.com/rss/
```

当前前端 API 使用 `/api/v1` 绝对路径，生产环境默认按域名根路径部署。推荐使用独立子域名：

```text
https://rss.example.com
```

## 11. 使用 Caddy 反向代理

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

重启服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

## 12. 更新到最新版本

更新前建议先备份数据库：

```bash
docker exec rss_manager_postgres pg_dump -U rss_manager rss_manager > rss_manager_backup_$(date +%F_%H-%M-%S).sql
```

更新流程：

1. 本地或 GitHub 上把代码合并到 `main`
2. 等 GitHub Actions 的 `Build and Publish Images` 成功
3. 在服务器执行：

```bash
cd RSS-feed-manager
git pull origin main
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d
```

如果服务器没有 `.env.production`，去掉命令中的 `--env-file .env.production`。

检查服务状态：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production ps
docker logs --tail 100 rss_manager_backend
```

确认数据库迁移：

```bash
docker exec -it rss_manager_backend alembic current
docker exec -it rss_manager_backend alembic upgrade head
```

更新完成后访问站点，确认可以登录、文章列表可以打开、订阅刷新功能正常。

## 13. 固定版本和回滚

如果 `latest` 出现问题，可以回滚到某个已发布提交镜像。

先在 GitHub Actions 成功记录里找到提交 SHA，然后修改 `.env.production`：

```env
RSS_MANAGER_IMAGE_TAG=sha-完整提交SHA
```

重新拉取并启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

恢复跟随最新版本时，再改回：

```env
RSS_MANAGER_IMAGE_TAG=latest
```

## 14. 需要在服务器本地构建时

正常生产部署不需要服务器本地构建。`docker-compose.prod.build.yml` 现在用于强制拉取 GHCR 镜像，兼容旧更新命令但不会触发本地构建。

如果 GitHub Actions 暂时不可用，或者你想在服务器上临时验证本地源码，可以使用专门的 local-build override 文件：

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.local-build.yml \
  --env-file .env.production \
  up -d --build
```

这会临时使用本地 `backend/Dockerfile` 和 `frontend/Dockerfile` 构建镜像。恢复 GitHub 镜像部署时，重新执行：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

## 15. 修改配置后的重启方式

修改 `.env.production` 后：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

如果修改的是镜像标签：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

## 16. 数据备份和恢复

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

## 17. 常用运维命令

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

查看浏览器抓取 Worker 日志：

```bash
docker logs -f rss_manager_celery_browser_worker
```

查看 Celery Beat 日志：

```bash
docker logs -f rss_manager_celery_beat
```

查看当前使用的镜像：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production images
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

## 18. 常见问题

### 18.1 GitHub Actions 成功了，但服务器 pull 不到镜像

先手动测试：

```bash
docker pull ghcr.io/inspoaibox/rss-feed-manager-frontend:latest
docker pull ghcr.io/inspoaibox/rss-feed-manager-backend:latest
```

如果提示无权限，请检查 GHCR package 是否公开，或在服务器执行 `docker login ghcr.io`。

### 18.2 服务器还是在本地构建

确认你没有额外加 `docker-compose.prod.local-build.yml`：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

如果兼容旧命令需要加 `docker-compose.prod.build.yml`，它现在只会强制拉取镜像：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d --build
```

确认 compose 配置中没有 `build:`，并且使用的是 `image`：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production config | grep -E 'ghcr.io|pull_policy|build:'
```

### 18.3 端口 5666 被占用

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

### 18.4 容器启动失败

查看服务状态和日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs backend
docker compose -f docker-compose.prod.yml --env-file .env.production logs frontend
```

### 18.5 数据库连接失败

检查 PostgreSQL 是否健康：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps postgres
docker logs --tail 100 rss_manager_postgres
```

常见原因：

- `.env.production` 中数据库用户名、密码、库名和已创建的数据卷不一致
- 首次启动时数据库还未完成初始化
- 修改过数据库密码但没有同步处理旧数据卷

### 18.6 RSS 抓取或自定义规则不执行

确认 Worker 和 Beat 正常：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps celery_worker celery_browser_worker celery_beat
docker logs -f rss_manager_celery_worker
docker logs -f rss_manager_celery_browser_worker
docker logs -f rss_manager_celery_beat
```

### 18.7 域名访问正常，但登录或 OAuth 回调异常

检查 `.env.production`：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

修改后重启：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### 18.8 Nginx 反向代理后接口 502

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

### 18.9 修改 `.env.production` 后不生效

执行：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

然后查看后端容器环境变量是否正确传入：

```bash
docker exec rss_manager_backend env | grep BASE_URL
docker exec rss_manager_backend env | grep CORS_ORIGINS
```

## 19. 卸载项目

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
