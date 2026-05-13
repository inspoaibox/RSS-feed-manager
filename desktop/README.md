# RSS Manager 桌面版 🖥️

> 将 RSS Manager 打包为 Windows 桌面应用程序

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)

## ✨ 特性

- 🚀 **一键安装** - 无需配置，开箱即用
- 💾 **本地数据** - 所有数据存储在本地，隐私安全
- 🔄 **自动同步** - 后台自动抓取订阅源更新
- 🤖 **AI 功能** - 支持文章翻译和摘要
- 📦 **单文件** - 打包为单个可执行文件
- 🎨 **原生窗口** - 使用 PyWebView 创建原生桌面窗口

## 🆚 与 Web 版对比

| 特性 | Web 版 | 桌面版 |
|------|--------|--------|
| 部署方式 | Docker / 手动配置 | 一键安装 |
| 用户系统 | 多用户 + 认证 | 单用户（无需登录） |
| 数据库 | PostgreSQL | SQLite |
| 任务队列 | Celery + Redis | APScheduler |
| 访问方式 | 浏览器 | 桌面窗口 |
| 语义搜索 | ✅ pgvector | ❌ 关键词搜索 |
| 适用场景 | 团队/服务器 | 个人/本地 |

## 🚀 快速开始

### 方式一：使用安装程序（推荐）

1. 下载 `RSSManager-Setup-1.0.0.exe`
2. 双击运行安装程序
3. 完成安装后启动应用

### 方式二：从源码构建

```batch
# 克隆项目
git clone <your-repo>
cd rss-manager

# 运行一键构建
desktop\build.bat
```

构建完成后：
- 可执行文件：`desktop\dist\RSSManager\RSSManager.exe`
- 安装程序：`desktop\installer\output\RSSManager-Setup-1.0.0.exe`

## 📖 文档

- [快速开始](QUICK_START.md) - 5 分钟上手
- [构建指南](BUILD_GUIDE.md) - 详细构建步骤
- [用户手册](USER_GUIDE.md) - 功能使用说明
- [架构说明](ARCHITECTURE.md) - 技术架构详解
- [待办事项](TODO.md) - 开发计划

## 🏗️ 架构

### 核心变化

桌面版相比 Web 版的主要调整：

1. **移除用户系统** → 单用户模式（user_id = 1）
2. **移除认证** → 无需登录注册
3. **Celery + Redis** → APScheduler（内置定时任务）
4. **PostgreSQL** → SQLite（本地数据库）
5. **浏览器访问** → PyWebView 桌面窗口

### 技术栈

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

### 目录结构

```
desktop/
├── backend/              # 桌面版后端
│   ├── app/
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
└── build.bat            # 一键构建脚本
```

## 🔧 构建要求

### 必需软件

- **Python 3.11+** - [下载](https://www.python.org/downloads/)
- **Node.js 18+** - [下载](https://nodejs.org/)
- **Git** - [下载](https://git-scm.com/)（可选）

### 可选软件

- **Inno Setup** - [下载](https://jrsoftware.org/isdl.php)（创建安装程序）

### 安装依赖

```bash
# Python 依赖
cd desktop/backend
pip install -r requirements.txt

# 前端依赖
cd ../../frontend
npm install

# Playwright 浏览器
python -m playwright install chromium
```

## 📦 构建流程

### 自动构建（推荐）

```batch
desktop\build.bat
```

### 手动构建

```bash
# 1. 构建前端
cd frontend
npm run build

# 2. 应用前端补丁
cd ../desktop/build
python patch_frontend.py

# 3. 重新构建前端
cd ../../frontend
npm run build

# 4. 打包可执行文件
cd ../desktop/build
pyinstaller main.spec --clean

# 5. 恢复前端
python patch_frontend.py restore

# 6. 创建安装程序（可选）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ../installer/setup.iss
```

## 💾 数据存储

所有数据存储在用户目录：

```
%APPDATA%\RSSManager\
├── rss_manager.db    # SQLite 数据库
└── logs/             # 日志文件
```

## 🎯 功能清单

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
- 通知管理

### 功能调整 ⚠️

- **AI 语义搜索** → 降级为关键词搜索（SQLite 不支持 pgvector）
- **多用户** → 单用户模式
- **远程访问** → 仅本地访问

## 📊 性能指标

- **包体积**: ~150-250 MB（压缩后）
- **启动时间**: 3-5 秒
- **内存占用**: 200-500 MB
- **CPU 占用**: 空闲时 < 5%

## 🐛 已知问题

1. **Playwright 包体积大** - Chromium 浏览器约 200MB
2. **首次启动较慢** - 需要初始化数据库
3. **SQLite 限制** - 不支持向量搜索，并发性能较低

## 🔮 未来计划

- [ ] macOS 版本
- [ ] Linux 版本
- [ ] 系统托盘支持
- [ ] 自动更新功能
- [ ] 离线 AI 模型
- [ ] 本地向量搜索

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE.txt](LICENSE.txt)

## 🙏 致谢

基于 [RSS Manager](../README.md) Web 版改造

---

**开始构建**: 阅读 [QUICK_START.md](QUICK_START.md)  
**遇到问题**: 查看 [BUILD_GUIDE.md](BUILD_GUIDE.md)  
**了解更多**: 查看 [ARCHITECTURE.md](ARCHITECTURE.md)
