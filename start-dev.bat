@echo off
echo 启动 RSS 订阅管理器开发环境...

:: 启动后端
start "RSS Backend" cmd /k "cd backend && .\venv\Scripts\activate && uvicorn app.main:app --reload"

:: 等待后端启动
timeout /t 3 /nobreak > nul

:: 启动前端
start "RSS Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo 后端: http://localhost:8000
echo 前端: http://localhost:5173
echo API文档: http://localhost:8000/docs
