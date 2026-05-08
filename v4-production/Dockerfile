# ============================================================
# AI 知识库 V4 — 生产 Docker 镜像
# ============================================================
# 多阶段构建：构建层安装依赖，运行层只拷贝必要文件
# ============================================================

FROM python:3.12-slim AS builder

WORKDIR /build

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# 先拷贝依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# 运行层
# ============================================================
FROM python:3.12-slim

LABEL maintainer="AI Knowledge Base Team"
LABEL version="4.0"
LABEL description="AI 知识库 V4 生产版 — 采集、分析、分发、交互"

WORKDIR /app

# 从构建层拷贝已安装的依赖
COPY --from=builder /install /usr/local

# 拷贝项目文件
COPY workflows/ ./workflows/
COPY patterns/ ./patterns/
COPY pipeline/ ./pipeline/
COPY distribution/ ./distribution/
COPY bot/ ./bot/
COPY openclaw/ ./openclaw/
COPY scripts/ ./scripts/
COPY AGENTS.md .

# 创建数据目录（运行时通过 volume 挂载）
RUN mkdir -p /app/knowledge/raw /app/knowledge/articles /app/data

# 非 root 用户运行
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 默认入口：运行流水线 + 机器人
CMD ["python", "-m", "bot.knowledge_bot"]
