@echo off
REM Windows 打包脚本 - 生成 exe 可执行文件

setlocal
set VERSION=1.3.1
set DIST_DIR=dist
set PYTHON_BIN=

echo === Codex Session Patcher 打包脚本 ===
echo 版本: %VERSION%

if not defined PYTHON_BIN (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
        if not errorlevel 1 set PYTHON_BIN=python
    )
)

if not defined PYTHON_BIN (
    where python3 >nul 2>nul
    if not errorlevel 1 (
        python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
        if not errorlevel 1 set PYTHON_BIN=python3
    )
)

if not defined PYTHON_BIN (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
        if not errorlevel 1 set PYTHON_BIN=py -3
    )
)

if not defined PYTHON_BIN (
    echo ERROR: No compatible Python 3.8+ interpreter found.
    echo Checked: python, python3, then py -3
    exit /b 1
)

echo 使用 Python: %PYTHON_BIN%

%PYTHON_BIN% -m pip --version >nul 2>nul
if errorlevel 1 %PYTHON_BIN% -m ensurepip --upgrade >nul 2>nul

%PYTHON_BIN% -m pip --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: %PYTHON_BIN% is missing pip and ensurepip could not enable it.
    exit /b 1
)

REM 清理旧构建
echo 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.egg-info rmdir /s /q *.egg-info

REM 安装依赖
echo 安装打包依赖...
%PYTHON_BIN% -m pip install pyinstaller

REM 构建 CLI 版本
echo 构建 CLI 可执行文件...
%PYTHON_BIN% -m PyInstaller codex-patcher.spec --clean

REM 重命名输出
if exist dist\codex-patcher (
    echo 打包完成: dist\codex-patcher\
    dir dist\codex-patcher
)

REM 创建压缩包
set ARCHIVE_NAME=codex-patcher-%VERSION%-windows
cd dist
if exist codex-patcher (
    rename codex-patcher %ARCHIVE_NAME%
    REM 使用 PowerShell 创建 zip
    powershell Compress-Archive -Path %ARCHIVE_NAME% -DestinationPath %ARCHIVE_NAME%.zip
    echo 分发包已创建: dist\%ARCHIVE_NAME%.zip
)
cd ..

echo === 打包完成 ===
