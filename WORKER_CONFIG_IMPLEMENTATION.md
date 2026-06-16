# Worker 配置管理功能实现总结

## 实现完成时间
2026-06-16

## 功能概述
实现了在后台系统设置页面动态管理 Celery Worker 配置参数的功能，用户可以根据服务器性能灵活调整任务队列的并发数、子进程回收策略和 CPU 限额。

## 已实现的功能

### 1. 后端实现

#### 数据库存储
使用现有的 `system_settings` 表存储配置，新增以下配置项：

| 配置键 | 说明 | 默认值 |
|--------|------|--------|
| worker_concurrency | 普通 Worker 并发数 | 5 |
| worker_max_tasks_per_child | 普通 Worker 子进程最大任务数 | 20 |
| worker_cpus | 普通 Worker CPU 限额 | 1.0 |
| browser_worker_concurrency | 浏览器 Worker 并发数 | 3 |
| browser_worker_max_tasks_per_child | 浏览器 Worker 子进程最大任务数 | 20 |
| browser_worker_cpus | 浏览器 Worker CPU 限额 | 0 (不限制) |

#### API 接口
**文件**: `backend/app/api/v1/endpoints/system.py`

1. **GET /api/system/settings**
   - 返回当前配置（从环境变量读取运行时值，从数据库读取待应用值）
   - 响应包含 `worker_runtime` 和 `browser_worker_runtime` 对象

2. **PUT /api/system/settings**
   - 保存新配置到数据库
   - 接受 `worker_runtime` 和 `browser_worker_runtime` 参数

#### 配置读取逻辑
**文件**: `backend/app/services/browser_fetch_settings.py`

- `worker_runtime_settings()`: 从环境变量读取当前普通 Worker 配置
- `browser_worker_runtime_settings()`: 从环境变量读取当前浏览器 Worker 配置
- 配置优先级：数据库值（待应用）> 环境变量（当前运行）> 默认值

### 2. 前端实现

#### TypeScript 类型定义
**文件**: `frontend/src/pages/SettingsPage.tsx`

```typescript
interface WorkerRuntimeSettings {
  worker_concurrency: number
  worker_max_tasks_per_child: number
  worker_cpus: number
}

interface BrowserWorkerRuntimeSettings {
  browser_worker_concurrency: number
  browser_worker_max_tasks_per_child: number
  browser_worker_cpus: number
}
```

#### UI 组件
**文件**: `frontend/src/pages/SettingsPage.tsx`

在"系统设置" -> "任务队列"页签中实现：

1. **普通 Worker 配置表单**
   - 并发数输入框（范围：1-20）
   - 子进程最大任务数输入框（范围：1-200）
   - CPU 限额输入框（范围：0-16，步长0.1）
   - 每个字段下方显示"当前"运行值

2. **浏览器 Worker 配置表单**
   - 结构同上
   - 独立配置

3. **保存按钮**
   - 点击保存到数据库
   - 显示成功/失败提示

4. **重启提示**
   - 黄色警告框
   - 显示需要执行的 Docker 命令
   - 说明配置保存后需重启容器才能生效

### 3. Docker Compose 配置
**文件**: `docker-compose.prod.yml`

已支持从环境变量读取配置：

```yaml
celery_worker:
  cpus: ${WORKER_CPUS:-1.0}
  command: celery -A app.tasks.celery_app worker --concurrency=${WORKER_CONCURRENCY:-5} --max-tasks-per-child=${WORKER_MAX_TASKS_PER_CHILD:-20} ...
  environment:
    - WORKER_CONCURRENCY=${WORKER_CONCURRENCY:-5}
    - WORKER_MAX_TASKS_PER_CHILD=${WORKER_MAX_TASKS_PER_CHILD:-20}
    - WORKER_CPUS=${WORKER_CPUS:-1.0}

celery_browser_worker:
  cpus: ${BROWSER_WORKER_CPUS:-0}
  command: celery ... --concurrency=${BROWSER_WORKER_CONCURRENCY:-3} --max-tasks-per-child=${BROWSER_WORKER_MAX_TASKS_PER_CHILD:-20} ...
```

### 4. 环境变量示例
**文件**: `.env.production.example`

已添加所有 Worker 配置变量及说明。

## 使用流程

### 修改配置
1. 登录后台管理界面
2. 进入"系统设置" -> "任务队列"页签
3. 修改普通 Worker 或浏览器 Worker 的配置
4. 点击"保存配置"按钮
5. 配置保存到数据库

### 应用配置
配置保存后，需要 SSH 登录服务器执行以下命令重启 Worker 容器：

```bash
docker restart rss_manager_celery_worker rss_manager_celery_browser_worker
```

或者使用完整的 compose 命令：

```bash
docker compose --profile browser -f docker-compose.prod.yml --env-file .env.production restart celery_worker celery_browser_worker
```

### 验证配置
重启后，刷新系统设置页面，"当前"值应该更新为新配置。

## 配置建议

根据不同服务器规格的推荐配置：

| 服务器规格 | 普通Worker并发 | 普通Worker CPU | 浏览器Worker并发 | 浏览器Worker CPU |
|-----------|---------------|---------------|-----------------|-----------------|
| 1核2G     | 1             | 0.8           | 1               | 0.5             |
| 2核4G     | 2             | 1.5           | 2               | 1.0             |
| 4核8G     | 3             | 2.0           | 3               | 2.0             |
| 8核16G    | 5             | 4.0           | 5               | 3.0             |

### 配置说明

**并发数 (concurrency)**:
- 决定同时运行的 Worker 进程数
- 并发数越高，同时处理的任务越多
- 建议不超过 CPU 核心数

**子进程最大任务数 (max_tasks_per_child)**:
- 每个子进程处理多少任务后自动回收
- 用于释放长期运行后的残留内存
- 默认 20 对大多数场景适用

**CPU 限额 (cpus)**:
- 限制容器最多使用的 CPU 核心数
- 0 表示不限制
- 1.0 表示最多使用 1 个 CPU 核心
- 2.5 表示最多使用 2.5 个 CPU 核心

## 技术实现细节

### 配置优先级
1. **数据库配置**（最高优先级）
   - 用户在后台保存的配置
   - 等待重启后生效

2. **环境变量配置**
   - 从 `.env.production` 读取
   - 当前运行时的实际值

3. **默认值**（最低优先级）
   - 硬编码在代码中
   - 作为后备值

### 配置同步机制
```
┌─────────────┐
│  用户修改   │
│  前端表单   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   保存到    │
│  数据库     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ SSH 登录    │
│ 执行重启    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  容器重启   │
│  读取环境   │  (需手动将数据库值同步到 .env)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  新配置     │
│  生效       │
└─────────────┘
```

## 限制与注意事项

### 当前限制
1. **需要手动重启容器**
   - 配置保存后不会自动生效
   - 需要用户 SSH 登录执行重启命令

2. **配置不会自动同步到 .env**
   - 数据库中的配置值仅用于前端显示
   - 实际生效的是 `.env.production` 中的值
   - 用户需要手动同步或直接修改 `.env.production`

### 安全考虑
当前方案不需要给后端容器 Docker socket 权限，避免了以下风险：
- 容器逃逸风险
- 操作其他容器的风险
- 提权攻击风险

## 未来优化方向

### 自动应用配置（可选）
如果需要实现一键应用配置，需要：

1. **给后端容器 Docker socket 权限**
```yaml
backend:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

2. **实现自动重启接口**
```python
@router.post("/apply-worker-config")
async def apply_worker_config(admin: User = Depends(require_admin)):
    """从数据库读取配置，写入 .env.production，并重启容器"""
    # 1. 从数据库读取配置
    # 2. 更新 .env.production 文件
    # 3. 通过 Docker API 重启容器
    # 4. 返回操作结果
```

3. **安全加固**
- 限制可操作的容器名称白名单
- 记录所有配置变更和重启操作日志
- 防止配置值注入攻击

### 配置模板（可选）
预设几组配置模板，用户可一键应用：
- 轻量模式（低资源消耗）
- 均衡模式（推荐）
- 性能模式（高性能）

### 实时监控（可选）
- 显示当前 Worker 实际运行状态
- 显示队列堆积情况
- CPU/内存使用率实时图表

## 测试场景

### 场景 1：修改普通 Worker 并发数
1. 进入系统设置 -> 任务队列
2. 修改"普通 Worker 并发数"从 5 改为 3
3. 点击保存
4. SSH 执行：`docker restart rss_manager_celery_worker`
5. 验证：`docker exec rss_manager_celery_worker bash -c 'ps aux | grep celery'`
6. 应该看到 3 个 worker 进程

### 场景 2：修改 CPU 限额
1. 修改"普通 Worker CPU 限额"从 1.0 改为 2.0
2. 保存并重启
3. 验证：`docker stats rss_manager_celery_worker`
4. CPU% 上限应该是 200%

### 场景 3：查看当前运行值
1. 不修改任何配置
2. 页面上"当前"值应显示实际运行的配置
3. 表单输入框显示数据库中的值（如果存在）或运行值

## 相关文件清单

### 后端
- `backend/app/api/v1/endpoints/system.py` - API 接口
- `backend/app/services/browser_fetch_settings.py` - 配置读取
- `docker-compose.prod.yml` - Docker Compose 配置
- `.env.production.example` - 环境变量示例

### 前端
- `frontend/src/pages/SettingsPage.tsx` - UI 组件
- `frontend/src/types/index.ts` - TypeScript 类型（Feed 接口新增字段）

### 文档
- `WORKER_CONFIG_MANAGEMENT.md` - 设计方案文档
- `WORKER_CONFIG_IMPLEMENTATION.md` - 本文档

## 参考命令

### 查看当前配置
```bash
# 查看环境变量
docker exec rss_manager_celery_worker env | grep WORKER

# 查看实际运行的进程数
docker exec rss_manager_celery_worker bash -c 'ps aux | grep "celery worker"'

# 查看 CPU 限制
docker inspect rss_manager_celery_worker | grep -A5 NanoCpus
```

### 临时调整（不推荐）
```bash
# 临时限制 CPU（不需要重启，但重启后失效）
docker update --cpus=1.0 rss_manager_celery_worker

# 取消限制
docker update --cpus=0 rss_manager_celery_worker
```

### 查看容器资源使用
```bash
# 实时监控
docker stats rss_manager_celery_worker rss_manager_celery_browser_worker

# 查看 Celery 状态
docker exec rss_manager_celery_worker celery -A app.tasks.celery_app inspect active
docker exec rss_manager_celery_worker celery -A app.tasks.celery_app inspect stats
```

---

**实现状态**: ✅ 已完成  
**测试状态**: ⏳ 待部署后测试  
**文档状态**: ✅ 已完成
