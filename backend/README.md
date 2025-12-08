# RSS Manager Backend

RSS 订阅管理器后端服务，基于 FastAPI 构建。

## 技术栈

- FastAPI
- SQLAlchemy 2.0
- Celery + Redis
- PostgreSQL / SQLite

## 开发

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload
```

## API 文档

启动服务后访问：http://localhost:8000/docs
