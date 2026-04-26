#!/bin/bash
# Codex Session Patcher 安装脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$SCRIPT_DIR/web-common.sh"

echo "=== Codex Session Patcher 安装脚本 ==="

PYTHON_BIN="$(web_pick_python_bin || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "错误: 未找到可用的 Python 3.8+ 解释器"
    echo "已检查: python3 / python / python3.13 / python3.12 / python3.11 / python3.10 / python3.9 / python3.8 / py -3"
    exit 1
fi

echo "检测到 Python: $PYTHON_BIN ($(web_python_version_string "$PYTHON_BIN"))"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

MODULE_ENTRY="$PROJECT_DIR/codex_session_patcher/cli.py"
TARGET_PATH="$BIN_DIR/codex-patcher"

if [ ! -f "$MODULE_ENTRY" ]; then
    echo "错误: 未找到入口脚本 $MODULE_ENTRY"
    exit 1
fi

echo "安装路径: $TARGET_PATH"

printf -v ESCAPED_PROJECT_DIR '%q' "$PROJECT_DIR"
printf -v ESCAPED_SCRIPT_DIR '%q' "$SCRIPT_DIR"

cat > "$TARGET_PATH" << EOF
#!/bin/bash
set -euo pipefail

PROJECT_DIR=$ESCAPED_PROJECT_DIR
SCRIPT_DIR=$ESCAPED_SCRIPT_DIR

source "\$SCRIPT_DIR/web-common.sh"

PYTHON_BIN="\${CODEX_SESSION_PATCHER_PYTHON:-}"
if [ -z "\$PYTHON_BIN" ]; then
    PYTHON_BIN="\$(web_pick_python_bin || true)"
fi

if [ -z "\$PYTHON_BIN" ]; then
    echo "错误: 未找到可用的 Python 3.8+ 解释器" >&2
    exit 1
fi

export PYTHONPATH="\$PROJECT_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec "\$PYTHON_BIN" -m codex_session_patcher.cli "\$@"
EOF

chmod +x "$TARGET_PATH"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "警告: $BIN_DIR 不在 PATH 中"
    echo "请将以下内容添加到您的 shell 配置文件 (~/.bashrc 或 ~/.zshrc):"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "使用方法:"
echo "    codex-patcher --latest      # 清理最新会话"
echo "    codex-patcher --all         # 清理所有会话"
echo "    codex-patcher --web         # 启动 Web UI"
echo "    codex-patcher --help        # 查看帮助"
echo ""
