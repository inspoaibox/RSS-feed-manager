# User-Agent 池功能实现总结

## 实现时间
2026-06-16

## 功能概述
将单一固定的 User-Agent 升级为 User-Agent 池，支持添加多个 UA 并随机轮换，避免被网站识别为爬虫。

## 实现的功能

### 1. User-Agent 池
- **添加多个 UA**：可以添加/删除多个 User-Agent
- **随机轮换**：开关控制每次抓取是否随机选择 UA
- **预设模板**：提供 7 个常用浏览器 UA 快速添加
- **后备 UA**：当 UA 池为空时使用的默认 UA

### 2. 预设 UA 模板
```
✓ Chrome Windows
✓ Chrome macOS
✓ Firefox Windows
✓ Safari macOS
✓ Edge Windows
✓ iPhone Safari
✓ Android Chrome
```

### 3. 后端实现

**文件**: `backend/app/services/browser_fetch_settings.py`

新增字段：
- `user_agent_pool: list[str]` - UA 池（存储为 JSON 数组）
- `user_agent_rotate: bool` - 是否随机轮换

**文件**: `backend/app/api/v1/endpoints/system.py`

修改 `setting_value_to_string` 函数，支持序列化列表为 JSON。

### 4. 前端实现

**文件**: `frontend/src/pages/SettingsPage.tsx`

**UI 组件**：
1. **随机轮换开关**
   - 复选框控制是否启用随机选择

2. **UA 列表管理**
   - 每个 UA 一行，可编辑
   - 删除按钮（垃圾桶图标）

3. **添加按钮**
   - "添加自定义 UA" 按钮

4. **快速添加模板**
   - 7 个预设模板按钮
   - 点击即可添加到 UA 池

5. **后备 UA**
   - 文本框，当 UA 池为空时使用

### 5. 数据存储

**数据库**: `system_settings` 表

| key | value | 示例 |
|-----|-------|------|
| user_agent_pool | JSON 数组 | `["UA1", "UA2", "UA3"]` |
| user_agent_rotate | 布尔值 | `true` 或 `false` |
| user_agent | 字符串 | `Mozilla/5.0 ...` |

## 使用场景

### 场景 1：避免被封禁
某些网站会检测固定的 User-Agent，将其识别为爬虫。使用 UA 池并开启随机轮换，每次抓取使用不同的 UA，降低被识别的风险。

### 场景 2：模拟不同设备
添加移动端和桌面端的 UA，测试网站在不同设备上的响应。

### 场景 3：绕过反爬虫
配合代理池使用，每次请求使用不同的 IP + UA 组合，更难被追踪。

## 部署步骤

### 1. 提交代码
```bash
git add backend/app/services/browser_fetch_settings.py
git add backend/app/api/v1/endpoints/system.py
git add frontend/src/pages/SettingsPage.tsx
git commit -m "实现 User-Agent 池功能"
git push
```

### 2. 服务器更新
```bash
# 拉取最新镜像
docker compose --profile browser -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production pull

# 重启服务
docker compose --profile browser -f docker-compose.prod.yml -f docker-compose.prod.build.yml --env-file .env.production up -d
```

**注意**：此功能**不需要数据库迁移**，直接重启服务即可。

### 3. 配置 UA 池
1. 登录后台管理
2. 进入"系统设置" -> "浏览器抓取"
3. 在 "User-Agent 池" 部分：
   - 点击预设模板快速添加常用 UA
   - 或点击"添加自定义 UA"手动输入
   - 勾选"随机轮换 User-Agent"开关
4. 点击"保存浏览器抓取设置"

## 使用示例

### 示例 1：添加常用 UA
1. 点击 "Chrome Windows" 按钮
2. 点击 "Safari macOS" 按钮
3. 点击 "iPhone Safari" 按钮
4. 勾选 "随机轮换 User-Agent"
5. 保存

现在每次浏览器抓取会在这 3 个 UA 中随机选择一个。

### 示例 2：自定义 UA
1. 点击 "添加自定义 UA"
2. 输入自定义的 User-Agent 字符串
3. 保存

### 示例 3：只使用后备 UA（关闭 UA 池）
1. 删除 UA 池中的所有 UA
2. 取消勾选 "随机轮换 User-Agent"
3. 在 "后备 User-Agent" 输入固定的 UA
4. 保存

## 技术实现细节

### UA 池使用逻辑
```python
def get_user_agent():
    if user_agent_rotate and user_agent_pool:
        # 随机选择 UA 池中的一个
        return random.choice(user_agent_pool)
    elif user_agent_pool:
        # 不随机，但 UA 池不为空，使用第一个
        return user_agent_pool[0]
    else:
        # UA 池为空，使用后备 UA
        return user_agent
```

### 数据序列化
- **保存**：列表 → JSON 字符串 → 数据库
- **读取**：数据库 → JSON 字符串 → 解析为列表

### 前端状态管理
UA 池存储在 `browserFetchSettings.user_agent_pool` 数组中，通过 `updateBrowserFetchSetting` 函数统一更新。

## 注意事项

### 1. UA 池为空的情况
如果 UA 池为空且未设置后备 UA，系统会使用默认的 Chrome UA。

### 2. 随机性
每次抓取随机选择，不保证均匀分布。如果需要轮询（round-robin），需要额外实现。

### 3. 性能影响
随机选择 UA 的开销极小，几乎无性能影响。

### 4. 与代理池配合
UA 池和代理池是独立的，可以同时使用。建议：
- 开启代理池轮询
- 开启 UA 池随机轮换
- 每次请求使用不同的 IP + UA 组合

## 未来优化方向

### 短期
- [ ] UA 池导入/导出功能
- [ ] UA 池模板库（在线更新）
- [ ] UA 使用统计

### 中期
- [ ] 轮询模式（round-robin）
- [ ] 根据网站自动选择 UA
- [ ] UA 有效性检测

### 长期
- [ ] 基于机器学习的 UA 选择
- [ ] 与指纹库集成
- [ ] 完整的浏览器指纹伪装

## 相关文件

### 后端
- `backend/app/services/browser_fetch_settings.py` - UA 池数据结构和解析
- `backend/app/api/v1/endpoints/system.py` - UA 池保存接口

### 前端
- `frontend/src/pages/SettingsPage.tsx` - UA 池管理界面

### 文档
- `UA_POOL_IMPLEMENTATION.md` - 本文档

---

**实现状态**: ✅ 已完成  
**测试状态**: ⏳ 待部署验证  
**文档状态**: ✅ 已完成

**开发者**: Claude Code  
**完成时间**: 2026-06-16
