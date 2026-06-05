# GitHub + Docker 完整使用流程

本文档说明如何从 GitHub 仓库 `inspoaibox/RSS-feed-manager` 拉取代码，并使用 Docker Compose 构建、运行、更新和维护 RSS Feed Manager。

## 1. 准备环境

服务器需要安装：

- Git
- Docker Engine
- Docker Compose v2

检查版本：

```bash
git --version
docker --version
docker compose version
```

默认生产端口是 `5666`，请确认端口未被占用，并在防火墙或云服务器安全组中放行。

## 2. 从 GitHub 拉取项目

```bash
git clone https://github.com/inspoaibox/RSS-feed-manager.git
cd RSS-feed-manager
```

如果已经克隆过项目：

```bash
cd RSS-feed-manager
git pull origin main
```

## 3. 配置生产环境变量

复制示例文件：

```bash
cp .env.production.example .env.production
```

Windows PowerShell：

```powershell
Copy-Item .env.production.example .env.production
```

编辑 `.env.production`，至少修改以下值：

```env
POSTGRES_PASSWORD=请改成强密码
REDIS_PASSWORD=请改成强密码
SECRET_KEY=请改成至少32位随机字符串
CORS_ORIGINS=["http://你的服务器IP:5666"]
BASE_URL=http://你的服务器IP:5666
```

生成 `SECRET_KEY`：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

使用域名和 HTTPS 时：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

## 4. 构建并启动 Docker 服务

首次启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

查看容器状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

后端容器启动时会自动执行数据库迁移：

```bash
alembic upgrade head
```

如果需要手动确认迁移状态：

```bash
docker exec -it rss_manager_backend alembic current
docker exec -it rss_manager_backend alembic upgrade head
```

## 5. 访问系统

浏览器打开：

```text
http://服务器IP:5666
```

本机部署时：

```text
http://localhost:5666
```

首次注册的用户会成为管理员。管理员可以在「设置」中关闭注册、配置 AI 渠道、调整同步间隔和通知。

## 6. 常用运维命令

查看日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```

只看后端日志：

```bash
docker logs -f rss_manager_backend
```

重启服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

停止服务但保留数据：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

停止服务并删除数据库数据卷：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down -v
```

## 7. 从 GitHub 更新到最新版本

```bash
cd RSS-feed-manager
git pull origin main
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

更新完成后检查服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker logs --tail 100 rss_manager_backend
```

## 8. 数据备份和恢复

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

## 9. 反向代理建议

如果使用域名，建议用 Nginx、Caddy 或 Traefik 做 HTTPS 反向代理，代理到本机 `5666` 端口。

Nginx 示例：

```nginx
server {
    listen 80;
    server_name rss.example.com;

    location / {
        proxy_pass http://127.0.0.1:5666;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

域名部署后请同步更新 `.env.production`：

```env
CORS_ORIGINS=["https://rss.example.com"]
BASE_URL=https://rss.example.com
```

然后重建并重启：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 10. 常见问题

端口被占用：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

或者修改 `docker-compose.prod.yml` 中前端端口映射：

```yaml
ports:
  - "8080:80"
```

容器启动失败：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs backend
docker compose -f docker-compose.prod.yml --env-file .env.production logs frontend
```

数据库连接失败：

- 确认 `postgres` 容器为 healthy
- 确认 `.env.production` 中数据库用户名、密码、库名一致
- 执行 `docker compose -f docker-compose.prod.yml --env-file .env.production restart backend`

RSS 抓取或自定义规则不执行：

- 确认 `rss_manager_celery_worker` 和 `rss_manager_celery_beat` 正常运行
- 查看任务日志：

```bash
docker logs -f rss_manager_celery_worker
docker logs -f rss_manager_celery_beat
```

修改 `.env.production` 后不生效：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```
