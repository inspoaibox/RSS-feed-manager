# Worker 配置动态管理实现方案

## 需求
将 Celery Worker 的配置参数从固定的 .env 文件改为可在后台设置页面动态调整，方便根据服务器性能灵活配置。

## 技术限制
- Docker 容器的 CPU 限制是在容器启动时设置的，不能运行时修改
- Celery Worker 的并发数 (--concurrency) 是启动参数，修改需要重启进程
- 真正生效需要：修改配置 → 重启容器

## 实现方案

### 方案 A：数据库 + 自动重启容器（推荐）

**优点**：
- 用户体验好，一键应用
- 配置持久化在数据库
- 历史配置可追溯

**缺点**：
- 需要给后端容器 Docker socket 权限（安全风险）
- 实现复杂度较高

**流程**：
1. 用户在后台修改配置并保存到数据库
2. 点击"应用配置"按钮
3. 后端读取数据库配置，写入 `.env.production`
4. 通过 Docker API 重启 `celery_worker` 和 `celery_browser_worker` 容器
5. 容器重启时读取新的环境变量

### 方案 B：数据库 + 手动重启提示（当前采用）

**优点**：
- 安全，不需要给后端容器特殊权限
- 实现简单
- 用户明确知道何时生效

**缺点**：
- 需要用户手动执行命令重启

**流程**：
1. 用户在后台修改配置并保存到数据库
2. 系统显示需要执行的命令
3. 用户登录服务器执行命令：
   ```bash
   docker compose --profile browser -f docker-compose.prod.yml --env-file .env.production restart celery_worker celery_browser_worker
   ```

### 方案 C：实时调整（技术上可行但不推荐）

通过 Celery 的控制命令动态调整：
```bash
# 动态调整并发数
celery -A app.tasks.celery_app control pool_grow 2
celery -A app.tasks.celery_app control pool_shrink 1
```

**缺点**：
- 无法修改 CPU 限制
- 重启后失效，需要配合持久化方案
- 不够直观

## 当前实现（方案 B）

### 1. 数据库设计
使用现有的 `system_settings` 表存储配置：

| key | value | description |
|-----|-------|-------------|
| worker_concurrency | 5 | 普通 Worker 并发数 |
| worker_max_tasks_per_child | 20 | 普通 Worker 子进程任务数 |
| worker_cpus | 1.0 | 普通 Worker CPU 限额 |
| browser_worker_concurrency | 3 | 浏览器 Worker 并发数 |
| browser_worker_max_tasks_per_child | 20 | 浏览器 Worker 子进程任务数 |
| browser_worker_cpus | 0 | 浏览器 Worker CPU 限额 |

### 2. 后端API
- `GET /api/system/settings`：返回当前配置（从环境变量读取当前值，从数据库读取待应用值）
- `PUT /api/system/settings`：保存新配置到数据库
- `POST /api/system/apply-worker-config`：生成应用命令并返回

### 3. 前端UI
在"系统设置"中新增"任务队列配置"页签：

```
[系统设置] -> [任务队列配置]

┌─ 普通 Worker 配置 ────────────────────┐
│ 并发数: [5]              (当前: 5)      │
│ 子进程任务数: [20]       (当前: 20)     │
│ CPU 限额: [1.0]          (当前: 1.0)    │
│                                         │
│ 提示: 0 表示不限制 CPU                  │
└─────────────────────────────────────────┘

┌─ 浏览器 Worker 配置 ──────────────────┐
│ 并发数: [3]              (当前: 3)      │
│ 子进程任务数: [20]       (当前: 20)     │
│ CPU 限额: [0]            (当前: 0)      │
└─────────────────────────────────────────┘

[保存配置] [应用配置]

应用步骤：
1. 保存配置到数据库
2. SSH 登录服务器执行：
   docker compose ... restart celery_worker celery_browser_worker
```

### 4. 配置优先级
1. **运行时值**（当前生效）：从环境变量读取，显示为"当前: X"
2. **数据库值**（待应用）：从数据库读取，显示在输入框中
3. **默认值**：硬编码的后备值

### 5. 配置同步机制
- 容器启动时，从 `.env.production` 读取环境变量
- 后端 API 从环境变量读取"当前值"
- 用户修改保存到数据库
- 需要手动重启容器使配置生效

## 未来优化（可选）

### 自动应用配置
如果需要一键应用，需要：

1. **给后端容器 Docker socket 权限**：
```yaml
# docker-compose.prod.yml
backend:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

2. **实现配置应用接口**：
```python
@router.post("/apply-worker-config")
async def apply_worker_config(admin: User = Depends(require_admin)):
    """Apply worker configuration from database to .env and restart containers."""
    # 1. 从数据库读取配置
    # 2. 写入 .env.production
    # 3. 通过 Docker API 重启容器
    # 4. 返回结果
```

3. **安全注意事项**：
- 仅限管理员访问
- 记录操作日志
- 限制可操作的容器名称
- 防止配置值注入攻击

## 测试场景

1. **修改普通 Worker 并发数**：
   - 保存配置：5 → 3
   - 重启容器
   - 验证：`docker exec rss_manager_celery_worker bash -c 'ps aux | grep celery'`
   - 应该看到 3 个 worker 进程

2. **修改 CPU 限额**：
   - 保存配置：1.0 → 2.0
   - 重启容器
   - 验证：`docker stats rss_manager_celery_worker`
   - CPU% 上限应该是 200%

3. **配置持久化**：
   - 修改并应用配置
   - 重启整个 Docker Compose
   - 验证配置仍然生效

## 配置建议

| 服务器规格 | 普通Worker并发 | CPU限额 | 浏览器Worker并发 | CPU限额 |
|-----------|---------------|---------|-----------------|---------|
| 1核2G     | 1             | 0.8     | 1               | 0.5     |
| 2核4G     | 2             | 1.5     | 2               | 1.0     |
| 4核8G     | 3             | 2.0     | 3               | 2.0     |
| 8核16G    | 5             | 4.0     | 5               | 3.0     |

## 参考命令

### 查看当前配置
```bash
# 查看环境变量
docker exec rss_manager_celery_worker env | grep WORKER

# 查看实际运行的进程数
docker exec rss_manager_celery_worker bash -c 'ps aux | grep -c "celery worker"'

# 查看 CPU 限制
docker inspect rss_manager_celery_worker | grep -A5 NanoCpus
```

### 重启 Worker
```bash
# 重启普通 Worker
docker restart rss_manager_celery_worker

# 重启浏览器 Worker
docker restart rss_manager_celery_browser_worker

# 同时重启两个
docker restart rss_manager_celery_worker rss_manager_celery_browser_worker
```

### 临时限制 CPU（不需要重启）
```bash
# 限制到 1 个 CPU
docker update --cpus=1.0 rss_manager_celery_worker

# 取消限制
docker update --cpus=0 rss_manager_celery_worker
```

---

**实施状态**: ✅ 方案 B 已实现  
**下一步**: 根据用户反馈决定是否实施方案 A 的自动重启功能
