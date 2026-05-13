@echo off
chcp 65001 >nul
echo ============================================================
echo   RSS Manager Desktop - 自动构建脚本
echo ============================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [1/5] 检查依赖...
cd desktop\backend
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 安装 Python 依赖失败
    pause
    exit /b 1
)

echo.
echo [2/5] 安装 Playwright 浏览器...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo [警告] Playwright 安装失败，浏览器模式可能不可用
)

echo.
echo [3/5] 构建前端...
cd ..\..\frontend
call npm install
if %errorlevel% neq 0 (
    echo [错误] 安装前端依赖失败
    pause
    exit /b 1
)

echo.
echo [4/5] 运行完整构建...
cd ..\desktop\build
python build_complete.py
if %errorlevel% neq 0 (
    echo [错误] 构建失败
    pause
    exit /b 1
)

echo.
echo [5/5] 创建安装程序...
set INNO_SETUP="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %INNO_SETUP% (
    %INNO_SETUP% ..\installer\setup.iss
    if %errorlevel% equ 0 (
        echo.
        echo ============================================================
        echo   构建完成！
        echo ============================================================
        echo.
        echo 可执行文件: desktop\dist\RSSManager\RSSManager.exe
        echo 安装程序: desktop\installer\output\RSSManager-Setup-1.0.0.exe
        echo.
    ) else (
        echo [警告] 创建安装程序失败
    )
) else (
    echo [警告] 未找到 Inno Setup，跳过创建安装程序
    echo 可执行文件: desktop\dist\RSSManager\RSSManager.exe
)

pause
