FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

WORKDIR /app

# Improve reliability on slower package mirrors.
RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\n' > /etc/apt/apt.conf.d/80-retries

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（这层会被缓存，只有依赖变化才重新安装）
COPY pyproject.toml uv.lock README.md ./

# Argos Translate depends on stanza, which depends on torch. The default PyPI
# Linux torch wheel pulls CUDA/NVIDIA packages and makes the backend image huge.
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"

# 复制所有代码
COPY . .

# 安装项目本身（现在代码已经存在）
RUN uv sync --frozen --no-dev

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000
