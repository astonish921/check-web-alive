#!/bin/bash

# Linux 卸载脚本
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 应用配置变量（可根据需要修改）
APP_NAME="${APP_NAME:-check-web-alive}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}}"
INSTALL_DIR="${INSTALL_DIR:-/opt/${APP_NAME}}"

echo -e "${GREEN}开始卸载 ${APP_NAME}...${NC}"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行此脚本${NC}"
    echo "使用: sudo $0"
    exit 1
fi

# 停止服务
echo -e "${YELLOW}停止服务...${NC}"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

# 禁用服务
echo -e "${YELLOW}禁用服务...${NC}"
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

# 删除服务文件
echo -e "${YELLOW}删除服务文件...${NC}"
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"

# 重新加载 systemd
echo -e "${YELLOW}重新加载 systemd 配置...${NC}"
systemctl daemon-reload

echo -e "${GREEN}卸载完成！${NC}"
echo ""
echo "已删除以下内容:"
echo "  - 服务文件: /etc/systemd/system/${SERVICE_NAME}.service"
echo "  - 服务已停止并禁用"
echo ""
echo "注意: 安装目录 $INSTALL_DIR 已保留，如需删除请手动执行:"
echo "  rm -rf $INSTALL_DIR"