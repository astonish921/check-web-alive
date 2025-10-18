#!/bin/bash

# Linux 运行脚本
set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$PROJECT_ROOT/check-web-alive.py"
EXE_PATH="$PROJECT_ROOT/dist/check-web-alive"

# 检查是否存在可执行文件（优先使用）
if [ -f "$EXE_PATH" ]; then
    echo "找到可执行文件，使用可执行文件模式"
    chmod +x "$EXE_PATH"
    echo "启动 Check Web Alive 监控程序..."
    echo "可执行文件: $EXE_PATH"
    echo "按 Ctrl+C 停止程序"
    echo ""
    exec "$EXE_PATH"
elif [ -f "$PYTHON_SCRIPT" ]; then
    echo "使用 Python 脚本模式"
    echo "启动 Check Web Alive 监控程序..."
    echo "Python 脚本: $PYTHON_SCRIPT"
    echo "按 Ctrl+C 停止程序"
    echo ""
    exec python3 "$PYTHON_SCRIPT"
else
    echo "错误: 未找到可执行文件或 Python 脚本"
    echo "请确保以下文件之一存在:"
    echo "  - $EXE_PATH (使用 PyInstaller 生成)"
    echo "  - $PYTHON_SCRIPT"
    exit 1
fi
