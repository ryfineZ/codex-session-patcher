#!/bin/bash
# Codex Session Patcher Web UI 启动脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/web/frontend"
FRONTEND_DIST_DIR="$FRONTEND_DIR/dist"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"

source "$SCRIPT_DIR/web-common.sh"

echo "🚀 Codex Session Patcher Web UI"
echo "================================"

PYTHON_BIN="$(web_pick_python_bin || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 未找到可用的 Python 3.8+ 解释器"
    echo "   已检查: python3 / python / python3.13 / python3.12 / python3.11 / python3.10 / python3.9 / python3.8 / py -3"
    exit 1
fi

echo "🐍 使用 Python: $PYTHON_BIN ($(web_python_version_string "$PYTHON_BIN"))"

if web_python_deps_need_install "$PYTHON_BIN"; then
    if ! web_ensure_pip_available "$PYTHON_BIN"; then
        echo "❌ $PYTHON_BIN 缺少 pip，无法安装 Web 依赖"
        exit 1
    fi

    echo "📦 安装 Python Web 依赖..."
    cd "$PROJECT_DIR"
    "$PYTHON_BIN" -m pip install -e ".[web]" -q
    web_mark_python_deps_installed
else
    echo "📦 Python Web 依赖已就绪，跳过安装"
fi

NEED_FRONTEND_BUILD=0
NEED_FRONTEND_DEPS_INSTALL=0

if web_frontend_build_need_run "$PYTHON_BIN"; then
    NEED_FRONTEND_BUILD=1
fi

if [ "$NEED_FRONTEND_BUILD" -eq 1 ] && web_frontend_deps_need_install "$PYTHON_BIN"; then
    NEED_FRONTEND_DEPS_INSTALL=1
fi

if [ "$NEED_FRONTEND_DEPS_INSTALL" -eq 1 ] || [ "$NEED_FRONTEND_BUILD" -eq 1 ]; then
    if ! command -v node >/dev/null 2>&1; then
        echo "❌ Node.js 未安装，请先安装 Node.js"
        exit 1
    fi

    if ! command -v npm >/dev/null 2>&1; then
        echo "❌ npm 未安装，请先安装 npm"
        exit 1
    fi
fi

if [ "$NEED_FRONTEND_BUILD" -eq 0 ]; then
    echo "📦 前端构建产物已就绪，跳过前端依赖安装"
elif [ "$NEED_FRONTEND_DEPS_INSTALL" -eq 1 ]; then
    echo "📦 安装前端依赖..."
    cd "$FRONTEND_DIR"
    npm install
    web_mark_frontend_deps_installed
else
    echo "📦 前端依赖已就绪，跳过安装"
fi

if [ "$NEED_FRONTEND_BUILD" -eq 1 ]; then
    echo "🔨 构建前端..."
    cd "$FRONTEND_DIR"
    npm run build
else
    echo "🔨 前端构建产物已是最新，跳过构建"
fi

echo "🌐 启动服务..."
echo ""
echo "访问地址: http://$HOST:$PORT"
echo "按 Ctrl+C 停止服务"
echo ""

cd "$PROJECT_DIR"
exec "$PYTHON_BIN" -m uvicorn web.backend.main:app --host "$HOST" --port "$PORT"
