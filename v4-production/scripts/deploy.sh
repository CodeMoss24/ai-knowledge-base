#!/usr/bin/env bash
# ============================================================
# deploy.sh — AI 知识库 V4 部署脚本
# ============================================================
# 用法：
#   ./scripts/deploy.sh              # 本地部署（docker-compose up）
#   ./scripts/deploy.sh build        # 仅构建镜像
#   ./scripts/deploy.sh push         # 构建并推送到镜像仓库
#   ./scripts/deploy.sh remote       # 远程服务器部署
#   ./scripts/deploy.sh stop         # 停止服务
#   ./scripts/deploy.sh logs         # 查看日志
# ============================================================

set -euo pipefail

# 配置
PROJECT_NAME="ai-knowledge-base"
IMAGE_NAME="${DOCKER_REGISTRY:-registry.example.com}/${PROJECT_NAME}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"
REMOTE_HOST="${DEPLOY_HOST:-}"
REMOTE_USER="${DEPLOY_USER:-deploy}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/ai-knowledge-base}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# 切换到项目根目录
cd "$(dirname "$0")/.."

# ----------------------------------------------------------
# 环境检查
# ----------------------------------------------------------
check_env() {
    log_info "检查部署环境..."

    # 检查 Docker
    if ! command -v docker &>/dev/null; then
        log_error "未安装 Docker，请先安装"
        exit 1
    fi

    # 检查 docker compose
    if docker compose version &>/dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        log_error "未安装 Docker Compose"
        exit 1
    fi

    # 检查 .env 文件
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            log_warn ".env 文件不存在，从 .env.example 复制模板"
            cp .env.example .env
            log_warn "请编辑 .env 文件填入实际配置后重新运行"
            exit 1
        else
            log_error "缺少 .env 和 .env.example 文件"
            exit 1
        fi
    fi

    # 创建数据目录
    mkdir -p knowledge/raw knowledge/articles data

    log_info "环境检查通过"
}

# ----------------------------------------------------------
# 构建镜像
# ----------------------------------------------------------
build() {
    log_info "构建 Docker 镜像: ${IMAGE_NAME}:${IMAGE_TAG}"

    docker build \
        -t "${IMAGE_NAME}:${IMAGE_TAG}" \
        -t "${IMAGE_NAME}:latest" \
        --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --build-arg VERSION="${IMAGE_TAG}" \
        .

    log_info "镜像构建完成"
    docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
}

# ----------------------------------------------------------
# 推送镜像
# ----------------------------------------------------------
push() {
    build

    log_info "推送镜像到仓库: ${IMAGE_NAME}:${IMAGE_TAG}"

    docker push "${IMAGE_NAME}:${IMAGE_TAG}"
    docker push "${IMAGE_NAME}:latest"

    log_info "镜像推送完成"
}

# ----------------------------------------------------------
# 本地部署
# ----------------------------------------------------------
deploy_local() {
    check_env

    log_info "本地部署 — docker compose up"

    ${COMPOSE_CMD} up -d --build --remove-orphans

    log_info "等待服务启动..."
    sleep 5

    # 检查服务状态
    ${COMPOSE_CMD} ps

    log_info "本地部署完成"
    log_info "OpenClaw 网关: http://localhost:${OPENCLAW_PORT:-3000}"
}

# ----------------------------------------------------------
# 远程部署
# ----------------------------------------------------------
deploy_remote() {
    if [ -z "${REMOTE_HOST}" ]; then
        log_error "未配置 DEPLOY_HOST 环境变量"
        exit 1
    fi

    push

    log_info "远程部署到 ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"

    # 同步配置文件到远程
    rsync -avz --exclude='knowledge/' --exclude='data/' --exclude='.git/' \
        ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

    # 远程执行 docker compose
    ssh "${REMOTE_USER}@${REMOTE_HOST}" << REMOTE_CMD
        cd ${REMOTE_DIR}
        docker compose pull
        docker compose up -d --remove-orphans
        docker compose ps
REMOTE_CMD

    log_info "远程部署完成"
}

# ----------------------------------------------------------
# 停止服务
# ----------------------------------------------------------
stop() {
    check_env
    log_info "停止所有服务..."
    ${COMPOSE_CMD} down
    log_info "服务已停止"
}

# ----------------------------------------------------------
# 查看日志
# ----------------------------------------------------------
show_logs() {
    check_env
    ${COMPOSE_CMD} logs -f --tail=100 "$@"
}

# ----------------------------------------------------------
# 主入口
# ----------------------------------------------------------
case "${1:-}" in
    build)
        build
        ;;
    push)
        push
        ;;
    remote)
        deploy_remote
        ;;
    stop)
        stop
        ;;
    logs)
        shift
        show_logs "$@"
        ;;
    *)
        deploy_local
        ;;
esac
