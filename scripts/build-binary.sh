#!/bin/bash
# 打包脚本 - 生成跨平台二进制文件

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="1.3.1"
DIST_DIR="dist"

source "$SCRIPT_DIR/web-common.sh"

echo "=== Codex Session Patcher 打包脚本 ==="
echo "版本: $VERSION"

PYTHON_BIN="$(web_pick_python_bin || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 未找到可用的 Python 3.8+ 解释器"
    echo "   已检查: python3 / python / python3.13 / python3.12 / python3.11 / python3.10 / python3.9 / python3.8 / py -3"
    exit 1
fi

echo "使用 Python: $PYTHON_BIN ($(web_python_version_string "$PYTHON_BIN"))"

if ! web_ensure_pip_available "$PYTHON_BIN"; then
    echo "❌ $PYTHON_BIN 缺少 pip，无法安装打包依赖"
    exit 1
fi

echo "清理旧构建..."
rm -rf build/ dist/ *.egg-info

echo "安装打包依赖..."
"$PYTHON_BIN" -m pip install pyinstaller

echo "构建 CLI 可执行文件..."
"$PYTHON_BIN" -m PyInstaller codex-patcher.spec --clean

# 重命名输出
if [ -d "dist/codex-patcher" ]; then
    echo "打包完成: dist/codex-patcher/"
    ls -la dist/codex-patcher/
fi

# 创建压缩包
echo "创建分发包..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
elif [[ "$OSTYPE" == "linux"* ]]; then
    PLATFORM="linux"
elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    PLATFORM="windows"
else
    PLATFORM="unknown"
fi

ARCHIVE_NAME="codex-patcher-${VERSION}-${PLATFORM}"
cd dist
if [ -d "codex-patcher" ]; then
    mv codex-patcher "$ARCHIVE_NAME"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        zip -r "${ARCHIVE_NAME}.zip" "$ARCHIVE_NAME"
    elif [[ "$OSTYPE" == "linux"* ]]; then
        tar -czvf "${ARCHIVE_NAME}.tar.gz" "$ARCHIVE_NAME"
    elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        # Windows 下用 7z 或 zip
        zip -r "${ARCHIVE_NAME}.zip" "$ARCHIVE_NAME"
    fi
    echo "分发包已创建: dist/${ARCHIVE_NAME}.zip (或 .tar.gz)"
fi
cd ..

echo "=== 打包完成 ==="
