# RSS Manager 桌面版构建指南

## 环境要求

### 必需软件

1. **Python 3.11+**
   - 下载：https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"

2. **Node.js 18+**
   - 下载：https://nodejs.org/
   - 推荐使用 LTS 版本

3. **Git**（可选，用于克隆代码）
   - 下载：https://git-scm.com/

4. **Inno Setup**（可选，用于创建安装程序）
   - 下载：https://jrsoftware.org/isdl.php

### Python 依赖

```bash
cd desktop/backend
pip install -r requirements.txt
```

### 依赖列表

创建 `desktop/backend/requirements.txt`：

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.25
alembic>=1.13.1
aiosqlite>=0.19.0
pydantic[email]>=2.5.3
pydantic-settings>=2.1.0
httpx>=0.26.0
feedparser>=6.0.10
beautifulsoup4>=4.12.3
lxml>=5.1.0
newspaper3k>=0.2.8
openai>=1.10.0
google-generativeai>=0.3.2
playwright>=1.40.0
python-dateutil>=2.8.2
webdavclient3>=3.14.6
apscheduler>=3.10.4
pywebview[cef]>=4.4.1
pyinstaller>=6.3.0
```

## 构建步骤

### 方式一：自动构建（推荐）

```bash
cd desktop/build
python build_complete.py
```

这个脚本会自动完成：
1. 修补前端代码（移除认证）
2. 构建前端静态文件
3. 复制后端文件
4. 安装 Playwright 浏览器
5. 使用 PyInstaller 打包
6. 恢复原始前端代码

### 方式二：手动构建

#### 1. 构建前端

```bash
cd frontend
npm install
npm run build
```

#### 2. 修补前端代码

```bash
cd desktop/build
python patch_frontend.py
```

#### 3. 重新构建前端

```bash
cd frontend
npm run build
```

#### 4. 复制前端构建文件

```bash
# 复制 frontend/dist 到 desktop/frontend
xcopy /E /I /Y frontend\dist desktop\frontend
```

#### 5. 复制后端文件

```bash
# 复制 backend/app 到 desktop/backend/app
xcopy /E /I /Y backend\app desktop\backend\app
```

#### 6. 安装 Playwright

```bash
python -m playwright install chromium
```

#### 7. 使用 PyInstaller 打包

```bash
cd desktop/build
pyinstaller main.spec --clean
```

#### 8. 恢复前端代码

```bash
cd desktop/build
python patch_frontend.py restore
```

## 构建输出

构建完成后，可执行文件位于：
```
desktop/dist/RSSManager/RSSManager.exe
```

## 创建安装程序

### 使用 Inno Setup

1. 打开 Inno Setup Compiler
2. 打开文件：`desktop/installer/setup.iss`
3. 点击 Build → Compile
4. 安装程序将生成在：`desktop/installer/output/`

### 命令行编译

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" desktop\installer\setup.iss
```

## 测试

### 测试可执行文件

```bash
cd desktop\dist\RSSManager
RSSManager.exe
```

### 测试安装程序

运行生成的安装程序：
```bash
desktop\installer\output\RSSManager-Setup-1.0.0.exe
```

## 常见问题

### 1. PyInstaller 打包失败

**问题**：找不到某些模块

**解决**：在 `main.spec` 的 `hiddenimports` 中添加缺失的模块

### 2. Playwright 浏览器未找到

**问题**：运行时提示找不到浏览器

**解决**：
```bash
python -m playwright install chromium
```

### 3. 前端静态文件未加载

**问题**：打开窗口显示空白

**解决**：检查 `desktop/frontend` 目录是否包含构建文件

### 4. 数据库初始化失败

**问题**：首次运行时数据库错误

**解决**：确保 `%APPDATA%\RSSManager` 目录有写入权限

## 文件大小优化

### 减小可执行文件大小

1. **排除不需要的模块**

在 `main.spec` 中添加到 `excludes`：
```python
excludes=[
    'celery',
    'redis',
    'psycopg2',
    'asyncpg',
    'pgvector',
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
]
```

2. **使用 UPX 压缩**

```python
upx=True,
upx_exclude=[],
```

3. **移除调试信息**

```python
debug=False,
strip=True,
```

### 预期文件大小

- 未压缩：~300-400 MB
- UPX 压缩后：~150-250 MB
- 安装程序：~100-150 MB（LZMA2 压缩）

## 发布清单

- [ ] 构建可执行文件
- [ ] 测试所有功能
- [ ] 创建安装程序
- [ ] 测试安装/卸载
- [ ] 准备 README 和用户文档
- [ ] 创建 GitHub Release
- [ ] 上传安装程序

## 自动化构建

可以创建批处理文件 `build.bat`：

```batch
@echo off
echo Building RSS Manager Desktop...
cd desktop\build
python build_complete.py
if %errorlevel% neq 0 exit /b %errorlevel%

echo Creating installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ..\installer\setup.iss
if %errorlevel% neq 0 exit /b %errorlevel%

echo Build completed successfully!
pause
```
