#!/bin/bash
# Codex Session Patcher 安装脚本

set -e

echo "=== Codex Session Patcher 安装脚本 ==="

# 检测 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "检测到 Python 版本: $PYTHON_VERSION"

# 检查 Python 版本是否 >= 3.8
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "错误: 需要 Python 3.8 或更高版本"
    exit 1
fi

# 创建 bin 目录
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

# 创建符号链接或复制文件
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/codex_patcher.py"
TARGET_PATH="$BIN_DIR/codex-patcher"

echo "安装路径: $TARGET_PATH"

# 使脚本可执行
chmod +x "$SCRIPT_PATH"

# 创建启动脚本
cat > "$TARGET_PATH" << EOF
#!/bin/bash
python3 "$SCRIPT_PATH" "\$@"
EOF

chmod +x "$TARGET_PATH"

# 检查 PATH
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
echo "    codex-patcher              # 执行基本清洗"
echo "    codex-patcher --auto-resume # 清洗后自动 resume"
echo "    codex-patcher --help        # 查看帮助"
echo ""
