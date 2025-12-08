FROM python:3.11-slim

WORKDIR /app

# 使用阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（这层会被缓存，只有依赖变化才重新安装）
COPY pyproject.toml README.md ./

# 只安装依赖，不安装项目本身
RUN pip install --no-cache-dir $(python -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(' '.join(d['project']['dependencies']))")

# 安装 Playwright 浏览器（利用缓存）
RUN playwright install chromium

# 复制所有代码
COPY . .

# 安装项目本身（现在代码已经存在）
RUN pip install --no-cache-dir -e .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000
