# 快速开始 - RSS Manager 桌面版打包

## 一键构建（推荐）

### Windows

```batch
build.bat
```

这个脚本会自动完成所有步骤。

## 手动构建

### 1. 安装依赖

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

### 2. 构建

```bash
cd desktop/build
python build_complete.py
```

### 3. 测试

```bash
cd ../dist/RSSManager
RSSManager.exe
```

## 构建输出

- **可执行文件**: `desktop/dist/RSSManager/RSSManager.exe`
- **安装程序**: `desktop/installer/output/RSSManager-Setup-1.0.0.exe`

## 文件结构

```
desktop/
├── backend/              # 桌面版后端
│   ├── app/             # 应用代码
│   ├── main_desktop.py  # 入口文件
│   └── requirements.txt # Python 依赖
├── frontend/            # 前端构建文件（自动生成）
├── frontend-patches/    # 前端补丁（移除认证）
├── build/               # 构建脚本
│   ├── build_complete.py
│   ├── patch_frontend.py
│   └── main.spec        # PyInstaller 配置
├── installer/           # 安装程序配置
│   └── setup.iss        # Inno Setup 脚本
├── dist/                # 构建输出（自动生成）
└── build.bat            # 一键构建脚本
```

## 主要变化

### 后端

- ✅ 移除用户认证系统
- ✅ 单用户模式（user_id = 1）
- ✅ 使用 APScheduler 替代 Celery
- ✅ 使用 SQLite 数据库
- ✅ 使用 PyWebView 创建桌面窗口
- ✅ 数据存储在 `%APPDATA%\RSSManager\`

### 前端

- ✅ 移除登录/注册页面
- ✅ 移除认证拦截器
- ✅ 自动以默认用户身份运行

### 功能保留

- ✅ RSS 订阅管理
- ✅ 文章阅读和收藏
- ✅ 分类管理
- ✅ 定时自动抓取
- ✅ 自定义抓取规则
- ✅ AI 翻译和摘要
- ✅ Playwright 浏览器模式
- ✅ OPML 导入导出
- ✅ WebDAV 备份
- ⚠️ AI 语义搜索（降级为关键词搜索）

## 下一步

1. 阅读 [BUILD_GUIDE.md](BUILD_GUIDE.md) 了解详细构建步骤
2. 阅读 [USER_GUIDE.md](USER_GUIDE.md) 了解用户使用说明
3. 运行 `build.bat` 开始构建

## 常见问题

### Q: 构建失败怎么办？

A: 检查：
- Python 3.11+ 已安装
- Node.js 18+ 已安装
- 所有依赖已正确安装
- 查看错误日志

### Q: 可执行文件太大？

A: 可以：
- 在 `main.spec` 中排除不需要的模块
- 启用 UPX 压缩
- 移除 Playwright（如果不需要浏览器模式）

### Q: 如何调试？

A: 
- 在 `main.spec` 中设置 `console=True` 查看日志
- 在 `config_desktop.py` 中设置 `DEBUG=True`
- 直接运行 `python desktop/backend/main_desktop.py`

### Q: 如何更新？

A: 
- 拉取最新代码
- 重新运行 `build.bat`
- 安装新版本会自动保留数据
