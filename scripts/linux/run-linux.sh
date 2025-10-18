#!/bin/bash

# Linux 运行脚本
set -e

# 应用配置变量（可根据需要修改）
APP_NAME="${APP_NAME:-check-web-alive}"
APP_PYTHON_SCRIPT="${APP_PYTHON_SCRIPT:-check-web-alive.py}"

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
PYTHON_SCRIPT="$PROJECT_ROOT/${APP_PYTHON_SCRIPT}"

# 检查是否存在 Python 脚本
if [ -f "$PYTHON_SCRIPT" ]; then
    echo "启动 ${APP_NAME} 监控程序..."
    echo "Python 脚本: $PYTHON_SCRIPT"
    echo "按 Ctrl+C 停止程序"
    echo ""
    exec python3 "$PYTHON_SCRIPT"
else
    echo "错误: 未找到 Python 脚本"
    echo "请确保以下文件存在:"
    echo "  - $PYTHON_SCRIPT"
    exit 1
fi
