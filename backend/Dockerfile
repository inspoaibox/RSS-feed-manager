FROM python:3.11-slim-bookworm

WORKDIR /app

# Improve reliability on slower package mirrors.
RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\n' > /etc/apt/apt.conf.d/80-retries

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（这层会被缓存，只有依赖变化才重新安装）
COPY pyproject.toml README.md ./

# 只安装依赖，不安装项目本身
RUN pip install --no-cache-dir --retries 5 --timeout 120 $(python -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(' '.join(d['project']['dependencies']))")

# 安装 Playwright 浏览器及系统依赖（利用缓存）
RUN playwright install --with-deps chromium

# 复制所有代码
COPY . .

# 安装项目本身（现在代码已经存在）
RUN pip install --no-cache-dir --retries 5 --timeout 120 -e .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000
