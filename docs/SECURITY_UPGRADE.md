# 安全修复与升级

本次修复覆盖认证撤销、文章和推送的用户隔离、HTML 与外链消毒、抓取及重定向的公网地址校验、浏览器安全代理、OAuth Cookie、加密备份，以及依赖锁定、测试与构建门禁。

## 升级部署

1. 先备份 PostgreSQL 数据卷或执行数据库备份。新备份需要 12–256 个字符的密码，密码不存入数据库；旧版明文 JSON 仍可导入。
2. `.env.production` 必须配置 `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、随机 `SECRET_KEY`（至少 32 字符）、HTTPS `BASE_URL` 和对应的 `CORS_ORIGINS`。示例占位密钥会被拒绝。现有数据库和 Redis 卷的密码必须与实际服务一致；修改应用变量不会自动修改已有服务密码。
3. 生产入口现在绑定 `127.0.0.1:5666`，通过 HTTPS 反向代理访问。生产认证 Cookie 始终使用 Secure/HttpOnly；直接用服务器 IP 的 HTTP 页面不能维持登录。开发环境仍可使用 localhost HTTP。
4. 拉取新镜像后执行 `docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d`；浏览器模式加 `--profile browser`。后端先迁移、通过数据库/Redis健康检查，Worker、Beat 和前端随后启动。
5. 确认 `alembic current` 已到当前版本 `043`。其中 `039` 迁移会删除旧版本留下的跨用户推送记录和不属于订阅者的 Feed/分类通知规则，并将重复设备端点保留为最后注册的账户；`040` 增加用户独立配置的外部通知；`041` 增加通知频道限速和独立失败次数，保留配置、规则与历史；`042` 停用 Mc-Translation 订阅源和规则的翻译设置，清除相关排队状态，保留原文和已保存的译文，不自动改用其他渠道。普通文章、合法通知订阅与阅读状态不受清理影响。迁移回退不能恢复这些违规记录，请保留升级前备份。
6. 如果之前使用公开默认 JWT 密钥，升级时替换成随机密钥，所有账户重新登录。已经暴露过的密码或 API Key 应在相应服务轮换。

旧库的浏览器设备唯一约束可能使用自动生成的名称、独立唯一索引，或已经约束为全局唯一。`039` 迁移会按实际约束列识别并调整，兼容缺少 `uq_user_endpoint` 的数据库。若旧镜像在这一步报 `constraint "uq_user_endpoint" ... does not exist`，后端会在启动前反复重启，需要应用包含此兼容修复的迁移脚本；不要通过跳过 `039` 的版本标记绕开安全清理。

修复后的迁移会统一约束名称，保留无关索引，并支持重复执行、升级和回退。发布镜像前，CI 除新安装检查外，还在 pgvector PostgreSQL 中检查多种旧约束结构及 `038 → head` 升级；这些检查失败时不会发布镜像。PostgreSQL 回归通过 `MIGRATION_TEST_DATABASE_URL` 显式连接专用测试服务，每个用例创建和销毁独立随机数据库；不要使用生产数据库地址运行测试。

`docker-compose.prod.build.yml` 只设置拉取已发布镜像的策略，其中没有本地构建配置；加 `--build` 也不会把服务器工作目录的修复代码装入该镜像。部署本地源代码修复时，应使用 `docker-compose.prod.local-build.yml`，或先发布修复后的镜像。

从镜像部署本次修复时，先提交源码并等待 GitHub Actions 全部成功，再在服务器拉取对应提交。可以在当前 Shell 设置 `export RSS_MANAGER_IMAGE_TAG="sha-$(git rev-parse HEAD)"`，使后端、前端和浏览器 Worker 使用同一提交对应的镜像，避免升级期间拉到不一致的 `latest`。

下面是已运行浏览器 Worker 的服务器手动升级步骤。先确认本次源码修复已经推送到 `main`，且该提交的全部镜像发布成功；脚本只在镜像拉取成功后停止应用服务，随后备份、迁移并启动服务。PostgreSQL、Redis 数据卷会继续使用。示例备份使用本项目数据库 `rss_manager` 及数据库用户 `rss_manager`，自定义数据库名的部署应相应调整。

```bash
bash <<'RSS_UPGRADE'
set -euo pipefail
cd /root/RSS-feed-manager
git pull --ff-only origin main
export RSS_MANAGER_IMAGE_TAG="sha-$(git rev-parse HEAD)"

dc() {
  docker compose --env-file .env.production --profile browser \
    -f docker-compose.prod.yml -f docker-compose.prod.build.yml "$@"
}

dc pull
dc stop backend celery_worker celery_beat celery_browser_worker

umask 077
mkdir -p /root/rss-backups
rss_backup="/root/rss-backups/before-upgrade-$(TZ=Asia/Singapore date +%Y%m%d-%H%M%S).dump"
docker exec rss_manager_postgres pg_dump -U rss_manager -d rss_manager -Fc > "$rss_backup"
test -s "$rss_backup"
docker exec -i rss_manager_postgres pg_restore --list < "$rss_backup" > /dev/null

dc run --rm --no-deps --pull never -T backend alembic upgrade head < /dev/null
dc up -d --pull never
dc ps
dc exec -T backend alembic current
printf '数据库备份：%s\n' "$rss_backup"
RSS_UPGRADE
```

未启用浏览器 Worker 的部署可去掉 `--profile browser` 及 `dc stop` 中的 `celery_browser_worker`。如需排查启动问题，执行 `docker logs --tail 120 rss_manager_backend`。

## 认证与兼容性

- 浏览器只在内存保存短期访问令牌，刷新令牌由 HttpOnly Cookie 保存。旧 `localStorage` 凭据在启动时清除。刷新请求发送空 JSON 和 Cookie，响应仅包含访问令牌。
- 登录/注册成功响应不再向 JavaScript 返回刷新令牌。调用这些接口的外部客户端应保留服务端 Cookie；旧刷新请求正文暂时仍接受 `refresh_token`，但新客户端应迁移到 Cookie。
- 修改密码或停用账户立即撤销旧访问令牌。退出登录也撤销该账户已有会话，并移除该账户的浏览器推送设备登记；其他已登录设备需要重新登录。
- OAuth 状态由十分钟有效的签名 Cookie 绑定浏览器，支持多个 API 进程。回调 URL 不含令牌，不会按邮箱自动绑定既有账户。已有密码账户继续使用原登录方式。
- 共享 Argos 语言包的安装/删除现在需要管理员权限。

## 抓取和备份

Mc-Translation 已下线：设置页、翻译方式选项及远程调用接口已移除。旧备份中的 Mc-Translation 配置恢复为“关闭翻译”，不会恢复旧密钥或自动选择付费 AI。历史数据库中的旧凭据列仅保留为未使用数据，应用不再读取或导出它们；回退 `042` 也不会自动重新启用旧渠道。

HTTP 请求在每次重定向重新验证目标并连接已验证 IP；TLS 保留原站点名称验证。跨站重定向不会转发抓取 Cookie 或 Authorization。浏览器和 WebDAV 通过本地代理校验并固定连接地址，拒绝环回、内网、链路本地和保留地址。开发环境确需内网源时可配置 `ALLOW_PRIVATE_FETCH_URLS=true`，生产环境禁止该开关。

备份使用 scrypt + AES-GCM，包含 API Key、Cookie、代理和 WebDAV 密码的内容均在导出前加密。导出接口改为 `POST /api/v1/backup/export`，JSON 正文为 `{"passphrase":"你的备份密码"}`。本地导入通过表单传递 `file` 与 `passphrase`，WebDAV 上传/恢复通过 JSON 传递密码。默认导入上限为 10 MiB，可用 `MAX_IMPORT_BYTES` 配置；反向代理的上传限制需同步调整。

Embedding 任务只能由创建者查看和取消，任务归属保存于 Redis。升级前没有登记归属的旧任务不再暴露。取消采用批次间停止，正在进行的 API 调用可能需要等待超时，已完成的批次保留。

## AI 翻译用量与续翻

`043` 增加请求用量记录、分段完成记录、文章重译版本及用户翻译限额。部署时同时更新后端和 Worker。默认每次输入预算为 12000、输出上限为 4096、单篇累计预算为 100000 token，单篇最多发送 32 次请求；每月额度默认不限制，可在 AI 设置中调整。预算只覆盖 AI 翻译和“模型翻译测试”，不覆盖整理、分析、Embedding、Google 或 Argos 翻译。

输入预算采用 UTF-8 字节数与消息开销的保守估算，发送前同时预留输出上限；实际用量以服务商返回的 `usage` 为准。缓存和推理 token 属于总量的明细，不会重复累加。没有用量回执的请求显示“未返回”，保留估算预算占用；本系统无法保证兼容渠道的计费规则、隐藏开销或输出限制行为，金额以渠道账单为准。每月预算按 UTC 自然月统计，已完成的分段读取不会再占用预算。

自动翻译按订阅源选择的范围判断是否完成。“翻译正文”只补缺少的译文，成功的标题与分段写入数据库，任务失败、进程重启或预算调整后可以续翻。截断后只允许拆成更小的分段；短文本仍被截断会停止并提示提高输出上限。超时或响应损坏时无法确认服务商是否已处理，系统会阻止自动重发；核对账单后，可点击“重试未确认分段（可能重复计费）”，已经成功的分段会继续复用。

“重新翻译”会创建新的翻译版本，明确重新生成内容。接口参数 `force_full=true` 表示补全标题和正文，`retranslate=true` 才表示重译。旧 `/ai/translate/{article_id}` 接口现在复用同一个后台队列，返回 `translation_status` 和当前译文，调用方应按状态轮询文章，不应把排队响应视为完成。`retry_unknown=true` 显式重试未确认分段，同时保留旧请求的预算占用。

渠道连接测试只读取模型列表，不调用生成接口。模型旁的“测试翻译（计费）”使用短文本并限制最多 256 输出 token，受翻译预算约束。OpenAI 渠道默认使用 `max_completion_tokens`，其他兼容渠道默认使用 `max_tokens`；可在渠道编辑中按服务商要求选择，程序不会自动移除输出限制重试。参数说明参考 [OpenAI Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。

翻译预算、翻译范围及渠道兼容参数随备份保存。请求用量历史和分段缓存保留在当前数据库，不包含在可导出的备份中；恢复到新的数据库时不能据此核对恢复前的账单或接续当时未完成的分段。已经保存到文章上的译文会保留。升级前的历史请求没有用量回执，界面不会把它们推算成实际用量。

## 构建与验证

后端使用 `uv.lock`，Linux Torch 固定使用 CPU 包；Docker 和 CI 使用冻结依赖。前端使用 `npm ci`，设置页和各路由按需加载。CI 必须先通过前后端测试、Lint、构建、npm 依赖审计和 PostgreSQL 迁移检查，才能发布镜像。

```powershell
# 后端（已有 venv 也可直接调用其 python/ruff）
cd backend
uv sync --frozen --extra dev --python 3.11
uv run --frozen ruff check app
uv run --frozen ruff format --check app
uv run --frozen pytest -q

# 前端
cd ../frontend
npm ci
npm run lint
npm test -- --run
npm run build
npm audit --registry=https://registry.npmjs.org
```

本次本地检查另外使用独立 Python 3.11 环境验证锁定的核心依赖；该环境不安装 Argos/Torch 等本地翻译运行库，外部 OAuth、AI 和推送使用测试替身。本机 Docker daemon 和内置浏览器未连接，所以生产容器、PostgreSQL全迁移链及真实外部服务联调由后续 CI/部署验证完成。

## 仓库与历史

SDK、Gradle缓存、桌面构建/发布产物、安装包、临时第三方 wheel、数据库备份和源码备份已取消 Git 跟踪并加到忽略规则，本地文件保留。当前改动包含这些取消跟踪的暂存删除。

历史提交仍包含旧数据库备份与构建产物，普通提交无法清除。`scripts/preview_clean_history.ps1` 会在新镜像仓库中生成清理预览，原仓库、工作区和远端都不修改。先提交本次修复，再生成预览；审核完成后才能安排远端历史替换、协作者重新克隆及凭据轮换。远端历史替换会改变提交 ID，需要单独确认。
