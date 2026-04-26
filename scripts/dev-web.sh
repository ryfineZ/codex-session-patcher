#!/bin/bash
# 开发模式启动（前后端分离，支持热更新）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/web/frontend"
FRONTEND_DIST_DIR="$FRONTEND_DIR/dist"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

source "$SCRIPT_DIR/web-common.sh"

echo "🚀 Codex Session Patcher Web UI (开发模式)"
echo "=========================================="

PYTHON_BIN="$(web_pick_python_bin || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 未找到可用的 Python 3.8+ 解释器"
    echo "   已检查: python3 / python / python3.13 / python3.12 / python3.11 / python3.10 / python3.9 / python3.8 / py -3"
    exit 1
fi

echo "🐍 使用 Python: $PYTHON_BIN ($(web_python_version_string "$PYTHON_BIN"))"

if ! command -v node >/dev/null 2>&1; then
    echo "❌ Node.js 未安装"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "❌ npm 未安装"
    exit 1
fi

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

if web_frontend_deps_need_install "$PYTHON_BIN"; then
    echo "📦 安装前端依赖..."
    cd "$FRONTEND_DIR"
    npm install
    web_mark_frontend_deps_installed
else
    echo "📦 前端依赖已就绪，跳过安装"
fi

FRONTEND_PORT="$(web_find_available_port "$FRONTEND_PORT" "$FRONTEND_HOST" "$PYTHON_BIN")"

echo "🔧 启动后端服务 (端口 ${BACKEND_PORT})..."
cd "$PROJECT_DIR"
"$PYTHON_BIN" -m uvicorn web.backend.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

sleep 2

echo "🎨 启动前端开发服务器 (端口 ${FRONTEND_PORT})..."
cd "$FRONTEND_DIR"
BACKEND_HOST="$BACKEND_HOST" BACKEND_PORT="$BACKEND_PORT" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

echo ""
echo "✅ 服务已启动"
echo "   前端: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "   后端: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "   API 文档: http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "echo '停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
