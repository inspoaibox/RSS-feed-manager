# 安全修复与升级

本次修复覆盖认证撤销、文章和推送的用户隔离、HTML 与外链消毒、抓取及重定向的公网地址校验、浏览器安全代理、OAuth Cookie、加密备份，以及依赖锁定、测试与构建门禁。

## 升级部署

1. 先备份 PostgreSQL 数据卷或执行数据库备份。新备份需要 12–256 个字符的密码，密码不存入数据库；旧版明文 JSON 仍可导入。
2. `.env.production` 必须配置 `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、随机 `SECRET_KEY`（至少 32 字符）、HTTPS `BASE_URL` 和对应的 `CORS_ORIGINS`。示例占位密钥会被拒绝。现有数据库和 Redis 卷的密码必须与实际服务一致；修改应用变量不会自动修改已有服务密码。
3. 生产入口现在绑定 `127.0.0.1:5666`，通过 HTTPS 反向代理访问。生产认证 Cookie 始终使用 Secure/HttpOnly；直接用服务器 IP 的 HTTP 页面不能维持登录。开发环境仍可使用 localhost HTTP。
4. 拉取新镜像后执行 `docker compose -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d`；浏览器模式加 `--profile browser`。后端先迁移、通过数据库/Redis健康检查，Worker、Beat 和前端随后启动。
5. 确认 `alembic current` 已到当前版本 `041`。其中 `039` 迁移会删除旧版本留下的跨用户推送记录和不属于订阅者的 Feed/分类通知规则，并将重复设备端点保留为最后注册的账户；`040` 增加用户独立配置的外部通知；`041` 增加通知频道限速和独立失败次数，保留配置、规则与历史。普通文章、合法通知订阅与阅读状态不受清理影响。迁移回退不能恢复这些违规记录，请保留升级前备份。
6. 如果之前使用公开默认 JWT 密钥，升级时替换成随机密钥，所有账户重新登录。已经暴露过的密码或 API Key 应在相应服务轮换。

## 认证与兼容性

- 浏览器只在内存保存短期访问令牌，刷新令牌由 HttpOnly Cookie 保存。旧 `localStorage` 凭据在启动时清除。刷新请求发送空 JSON 和 Cookie，响应仅包含访问令牌。
- 登录/注册成功响应不再向 JavaScript 返回刷新令牌。调用这些接口的外部客户端应保留服务端 Cookie；旧刷新请求正文暂时仍接受 `refresh_token`，但新客户端应迁移到 Cookie。
- 修改密码或停用账户立即撤销旧访问令牌。退出登录也撤销该账户已有会话，并移除该账户的浏览器推送设备登记；其他已登录设备需要重新登录。
- OAuth 状态由十分钟有效的签名 Cookie 绑定浏览器，支持多个 API 进程。回调 URL 不含令牌，不会按邮箱自动绑定既有账户。已有密码账户继续使用原登录方式。
- 共享 Argos 语言包的安装/删除现在需要管理员权限。

## 抓取和备份

HTTP 请求在每次重定向重新验证目标并连接已验证 IP；TLS 保留原站点名称验证。跨站重定向不会转发抓取 Cookie 或 Authorization。浏览器和 WebDAV 通过本地代理校验并固定连接地址，拒绝环回、内网、链路本地和保留地址。开发环境确需内网源时可配置 `ALLOW_PRIVATE_FETCH_URLS=true`，生产环境禁止该开关。

备份使用 scrypt + AES-GCM，包含 API Key、Cookie、代理和 WebDAV 密码的内容均在导出前加密。导出接口改为 `POST /api/v1/backup/export`，JSON 正文为 `{"passphrase":"你的备份密码"}`。本地导入通过表单传递 `file` 与 `passphrase`，WebDAV 上传/恢复通过 JSON 传递密码。默认导入上限为 10 MiB，可用 `MAX_IMPORT_BYTES` 配置；反向代理的上传限制需同步调整。

Embedding 任务只能由创建者查看和取消，任务归属保存于 Redis。升级前没有登记归属的旧任务不再暴露。取消采用批次间停止，正在进行的 API 调用可能需要等待超时，已完成的批次保留。

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
