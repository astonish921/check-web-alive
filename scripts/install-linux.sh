#!/bin/bash

# Linux 安装脚本
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
INSTALL_DIR="/opt/check-web-alive"
SERVICE_NAME="check-web-alive"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}开始安装 Check Web Alive 监控程序...${NC}"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行此脚本${NC}"
    echo "使用: sudo $0"
    exit 1
fi

# 检查是否存在 Python 脚本
if [ ! -f "$PROJECT_ROOT/check-web-alive.py" ]; then
    echo -e "${RED}错误: 未找到 Python 脚本 check-web-alive.py${NC}"
    exit 1
fi

# 检查是否存在可执行文件（优先使用）
if [ -f "$PROJECT_ROOT/dist/check-web-alive" ]; then
    USE_EXECUTABLE=true
    echo -e "${GREEN}找到可执行文件，将使用可执行文件模式${NC}"
else
    USE_EXECUTABLE=false
    echo -e "${YELLOW}未找到可执行文件，将使用 Python 脚本模式${NC}"
fi

# 创建安装目录
echo -e "${YELLOW}创建安装目录: $INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR"

# 复制文件
if [ "$USE_EXECUTABLE" = true ]; then
    echo -e "${YELLOW}复制可执行文件...${NC}"
    if [ "$PROJECT_ROOT/dist/check-web-alive" != "$INSTALL_DIR/check-web-alive" ]; then
        cp "$PROJECT_ROOT/dist/check-web-alive" "$INSTALL_DIR/"
    else
        echo -e "${YELLOW}文件已在目标位置，跳过复制${NC}"
    fi
    chmod +x "$INSTALL_DIR/check-web-alive"
else
    echo -e "${YELLOW}复制 Python 脚本...${NC}"
    if [ "$PROJECT_ROOT/check-web-alive.py" != "$INSTALL_DIR/check-web-alive.py" ]; then
        cp "$PROJECT_ROOT/check-web-alive.py" "$INSTALL_DIR/"
    else
        echo -e "${YELLOW}文件已在目标位置，跳过复制${NC}"
    fi
    chmod +x "$INSTALL_DIR/check-web-alive.py"
fi

# 复制配置文件（如果存在）
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}复制配置文件...${NC}"
    if [ "$PROJECT_ROOT/.env" != "$INSTALL_DIR/.env" ]; then
        cp "$PROJECT_ROOT/.env" "$INSTALL_DIR/"
    else
        echo -e "${YELLOW}配置文件已在目标位置，跳过复制${NC}"
    fi
fi

# 复制 requirements.txt（Python 模式需要）
if [ "$USE_EXECUTABLE" = false ]; then
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        echo -e "${YELLOW}复制依赖文件...${NC}"
        if [ "$PROJECT_ROOT/requirements.txt" != "$INSTALL_DIR/requirements.txt" ]; then
            cp "$PROJECT_ROOT/requirements.txt" "$INSTALL_DIR/"
        else
            echo -e "${YELLOW}依赖文件已在目标位置，跳过复制${NC}"
        fi
    fi
fi

# 创建日志目录
echo -e "${YELLOW}创建日志目录...${NC}"
mkdir -p "$INSTALL_DIR/logs"
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# 安装 systemd 服务
echo -e "${YELLOW}安装 systemd 服务...${NC}"
if [ "$USE_EXECUTABLE" = true ]; then
    # 使用可执行文件
    sed "s|ExecStart=.*|ExecStart=$INSTALL_DIR/check-web-alive|" "$SCRIPT_DIR/check-web-alive.service" > "$SERVICE_FILE"
else
    # 使用 Python 脚本
    sed "s|ExecStart=.*|ExecStart=/usr/bin/python3 $INSTALL_DIR/check-web-alive.py|" "$SCRIPT_DIR/check-web-alive.service" > "$SERVICE_FILE"
fi

# 重新加载 systemd
echo -e "${YELLOW}重新加载 systemd 配置...${NC}"
systemctl daemon-reload

# 启用服务
echo -e "${YELLOW}启用服务...${NC}"
systemctl enable "$SERVICE_NAME"

# 启动服务
echo -e "${YELLOW}启动服务...${NC}"
systemctl start "$SERVICE_NAME"

# 检查服务状态
echo -e "${YELLOW}检查服务状态...${NC}"
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}✓ 服务启动成功！${NC}"
else
    echo -e "${RED}✗ 服务启动失败${NC}"
    echo "查看服务状态: systemctl status $SERVICE_NAME"
    echo "查看服务日志: journalctl -u $SERVICE_NAME -f"
    exit 1
fi

echo -e "${GREEN}安装完成！${NC}"
echo ""
if [ "$USE_EXECUTABLE" = false ]; then
    echo -e "${YELLOW}注意: 使用 Python 脚本模式，请确保系统已安装 Python 3.6+ 和依赖包${NC}"
    echo "如需安装依赖: pip3 install -r $INSTALL_DIR/requirements.txt"
    echo ""
fi
echo "服务管理命令:"
echo "  启动服务: systemctl start $SERVICE_NAME"
echo "  停止服务: systemctl stop $SERVICE_NAME"
echo "  重启服务: systemctl restart $SERVICE_NAME"
echo "  查看状态: systemctl status $SERVICE_NAME"
echo "  查看日志: journalctl -u $SERVICE_NAME -f"
echo ""
echo "配置文件位置: $INSTALL_DIR/.env"
echo "日志文件位置: $INSTALL_DIR/logs/"
echo ""
echo "如需修改配置，请编辑 $INSTALL_DIR/.env 文件，然后重启服务。"
