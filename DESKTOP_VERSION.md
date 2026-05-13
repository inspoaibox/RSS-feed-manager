# 🖥️ RSS Manager 桌面版

> 将 RSS Manager 打包为 Windows 桌面应用程序

## 📦 桌面版说明

桌面版是 RSS Manager 的独立 Windows 应用程序版本，具有以下特点：

- ✅ **一键安装** - 无需配置 Docker 或数据库
- ✅ **单用户模式** - 无需注册登录，安装即用
- ✅ **本地数据** - 所有数据存储在本地，隐私安全
- ✅ **自动同步** - 后台自动抓取订阅源更新
- ✅ **完整功能** - 保留 Web 版的所有核心功能

## 🚀 快速开始

### 使用安装程序（推荐）

1. 下载 `RSSManager-Setup-1.0.0.exe`
2. 双击运行安装程序
3. 完成安装后启动应用

### 从源码构建

```batch
# 在项目根目录执行
desktop\build.bat
```

构建完成后：
- 可执行文件：`desktop\dist\RSSManager\RSSManager.exe`
- 安装程序：`desktop\installer\output\RSSManager-Setup-1.0.0.exe`

## 📚 完整文档

所有桌面版相关文档都在 `desktop/` 目录：

### 开始使用
- [README.md](desktop/README.md) - 项目说明
- [QUICK_START.md](desktop/QUICK_START.md) - 快速开始（5 分钟）
- [BUILD_GUIDE.md](desktop/BUILD_GUIDE.md) - 详细构建指南

### 深入了解
- [ARCHITECTURE.md](desktop/ARCHITECTURE.md) - 架构设计
- [USER_GUIDE.md](desktop/USER_GUIDE.md) - 用户手册
- [CHECKLIST.md](desktop/CHECKLIST.md) - 构建检查清单

### 其他资源
- [SUMMARY.md](desktop/SUMMARY.md) - 方案总结
- [FINAL_SUMMARY.md](desktop/FINAL_SUMMARY.md) - 最终总结
- [TODO.md](desktop/TODO.md) - 待办事项
- [ICON_README.md](desktop/ICON_README.md) - 图标制作

## 🆚 版本对比

| 特性 | Web 版 | 桌面版 |
|------|--------|--------|
| 部署方式 | Docker / 手动配置 | 一键安装 |
| 用户系统 | 多用户 + JWT 认证 | 单用户（无需登录） |
| 数据库 | PostgreSQL | SQLite |
| 任务队列 | Celery + Redis | APScheduler |
| 访问方式 | 浏览器 | 桌面窗口 |
| 语义搜索 | ✅ pgvector | ❌ 关键词搜索 |
| 适用场景 | 团队/服务器 | 个人/本地 |

## 🎯 核心功能

### 完全支持 ✅

- RSS/Atom 订阅管理
- 文章阅读（已读/未读、收藏）
- 分类管理
- 定时自动抓取
- 自定义抓取规则
- AI 翻译和摘要
- Playwright 浏览器模式
- OPML 导入导出
- WebDAV 备份恢复

### 功能调整 ⚠️

- **AI 语义搜索** → 降级为关键词搜索（SQLite 不支持 pgvector）

## 📋 构建要求

### 必需软件

- Python 3.11+
- Node.js 18+
- Git（可选）

### 可选软件

- Inno Setup（创建安装程序）

## 🏗️ 目录结构

```
desktop/
├── backend/              # 桌面版后端
│   ├── app/             # 应用代码
│   │   ├── core/        # 核心配置（单用户模式）
│   │   ├── api/         # API 端点（移除 auth）
│   │   ├── scheduler/   # APScheduler 定时任务
│   │   └── services/    # 业务逻辑
│   ├── main_desktop.py  # 桌面版入口
│   └── requirements.txt # Python 依赖
├── frontend-patches/    # 前端补丁（移除认证）
├── build/               # 构建脚本
│   ├── build.py         # 主构建脚本
│   ├── main.spec        # PyInstaller 配置
│   └── patch_frontend.py # 前端补丁工具
├── installer/           # 安装程序配置
│   └── setup.iss        # Inno Setup 脚本
└── *.md                 # 11 个详细文档
```

## 📊 项目统计

- **代码文件**: 24 个（Python + TypeScript + 配置）
- **文档文件**: 12 个（Markdown）
- **总文件数**: 36 个
- **代码行数**: ~2000+ 行

## 🎓 技术栈

**后端**：
- FastAPI - Web 框架
- SQLAlchemy + SQLite - 数据库
- APScheduler - 定时任务
- PyWebView - 桌面窗口
- PyInstaller - 打包工具

**前端**：
- React + TypeScript
- Vite - 构建工具
- TailwindCSS - 样式

## 💡 设计亮点

1. **单用户模式** - 通过依赖注入优雅实现
2. **前端补丁系统** - 自动应用和恢复
3. **一键构建** - 完全自动化的构建流程
4. **完整文档** - 12 个详细的 Markdown 文档

## 🔮 未来计划

- [ ] macOS 版本
- [ ] Linux 版本
- [ ] 系统托盘支持
- [ ] 自动更新功能
- [ ] 离线 AI 模型

## 📞 获取帮助

1. 查看 `desktop/` 目录下的文档
2. 提交 GitHub Issue
3. 参与 GitHub Discussions

## 📄 许可证

MIT License - 详见 [desktop/LICENSE.txt](desktop/LICENSE.txt)

---

**立即开始**: 查看 [desktop/QUICK_START.md](desktop/QUICK_START.md)  
**详细指南**: 查看 [desktop/BUILD_GUIDE.md](desktop/BUILD_GUIDE.md)  
**架构设计**: 查看 [desktop/ARCHITECTURE.md](desktop/ARCHITECTURE.md)
