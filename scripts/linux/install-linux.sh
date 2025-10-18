#!/bin/bash

# Linux 安装脚本
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 应用配置变量（可根据需要修改）
APP_NAME="${APP_NAME:-check-web-alive}"
APP_DESCRIPTION="${APP_DESCRIPTION:-Check Web Alive Monitor}"
APP_PYTHON_SCRIPT="${APP_PYTHON_SCRIPT:-check-web-alive.py}"

# 安装配置
INSTALL_DIR="${INSTALL_DIR:-/opt/${APP_NAME}}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${GREEN}开始安装 ${APP_DESCRIPTION}...${NC}"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行此脚本${NC}"
    echo "使用: sudo $0"
    exit 1
fi

# 检查是否存在 Python 脚本
if [ ! -f "$PROJECT_ROOT/${APP_PYTHON_SCRIPT}" ]; then
    echo -e "${RED}错误: 未找到 Python 脚本 ${APP_PYTHON_SCRIPT}${NC}"
    exit 1
fi

# 检查 Python 脚本
echo -e "${GREEN}使用 Python 脚本模式${NC}"

# 创建安装目录
echo -e "${YELLOW}创建安装目录: $INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR"

# 复制 Python 脚本
echo -e "${YELLOW}复制 Python 脚本...${NC}"
if [ "$PROJECT_ROOT/${APP_PYTHON_SCRIPT}" != "$INSTALL_DIR/${APP_PYTHON_SCRIPT}" ]; then
    cp "$PROJECT_ROOT/${APP_PYTHON_SCRIPT}" "$INSTALL_DIR/"
else
    echo -e "${YELLOW}文件已在目标位置，跳过复制${NC}"
fi
chmod +x "$INSTALL_DIR/${APP_PYTHON_SCRIPT}"

# 复制配置文件
echo -e "${YELLOW}复制配置文件...${NC}"
if [ -f "$PROJECT_ROOT/.env" ]; then
    if [ "$PROJECT_ROOT/.env" != "$INSTALL_DIR/.env" ]; then
        cp "$PROJECT_ROOT/.env" "$INSTALL_DIR/"
        echo -e "${GREEN}配置文件已复制${NC}"
    else
        echo -e "${YELLOW}配置文件已在目标位置，跳过复制${NC}"
    fi
else
    echo -e "${RED}错误: 未找到 .env 配置文件${NC}"
    echo -e "${RED}请先创建 .env 配置文件，参考 config.example.env 文件${NC}"
    exit 1
fi

# 复制 requirements.txt
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${YELLOW}复制依赖文件...${NC}"
    if [ "$PROJECT_ROOT/requirements.txt" != "$INSTALL_DIR/requirements.txt" ]; then
        cp "$PROJECT_ROOT/requirements.txt" "$INSTALL_DIR/"
    else
        echo -e "${YELLOW}依赖文件已在目标位置，跳过复制${NC}"
    fi
fi

# 创建日志目录
echo -e "${YELLOW}创建日志目录...${NC}"
mkdir -p "$INSTALL_DIR/logs"
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# 安装 systemd 服务
echo -e "${YELLOW}安装 systemd 服务...${NC}"
# 使用 Python 脚本
sed -e "s|{{APP_DESCRIPTION}}|${APP_DESCRIPTION}|g" \
    -e "s|{{INSTALL_DIR}}|${INSTALL_DIR}|g" \
    -e "s|{{APP_NAME}}|/usr/bin/python3 ${INSTALL_DIR}/${APP_PYTHON_SCRIPT}|g" \
    "$SCRIPT_DIR/common_tpl.service" > "$SERVICE_FILE"

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
echo -e "${YELLOW}注意: 使用 Python 脚本模式，请确保系统已安装 Python 3.6+ 和依赖包${NC}"
echo "如需安装依赖: pip3 install -r $INSTALL_DIR/requirements.txt"
echo ""
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
echo -e "${YELLOW}重要: 请确保 $INSTALL_DIR/.env 文件配置正确后启动服务！${NC}"
echo "配置文件已复制，请检查以下配置项:"
echo "  - TARGET_URL: 要监控的网站URL"
echo "  - SMTP_*: 邮件服务器配置"
echo "  - MAIL_*: 邮件地址配置"
echo ""
echo "启动服务: systemctl start $SERVICE_NAME"
echo ""
echo "如果服务启动失败，请检查配置文件:"
echo "  调试配置: bash $SCRIPT_DIR/debug-config.sh"
echo "  查看日志: journalctl -u $SERVICE_NAME -f"
echo ""
echo "常见问题解决:"
echo "  1. python-dotenv 未安装: 运行 pip install -r requirements.txt"
echo "  2. 配置文件缺失: 检查根目录下是否存在 .env 文件，如果不存在拷贝config.example.env文件到根目录下并修改，并改名为.env"
echo "  2. 配置项缺失: 检查 .env 文件是否包含所有必需项"

