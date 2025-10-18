#!/bin/bash

# Linux 卸载脚本
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
SERVICE_NAME="check-web-alive"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_DIR="/opt/check-web-alive"

echo -e "${GREEN}开始卸载 Check Web Alive 监控程序...${NC}"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行此脚本${NC}"
    echo "使用: sudo $0"
    exit 1
fi

# 停止服务
echo -e "${YELLOW}停止服务...${NC}"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl stop "$SERVICE_NAME"
    echo -e "${GREEN}✓ 服务已停止${NC}"
else
    echo -e "${YELLOW}服务未运行${NC}"
fi

# 禁用服务
echo -e "${YELLOW}禁用服务...${NC}"
if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    systemctl disable "$SERVICE_NAME"
    echo -e "${GREEN}✓ 服务已禁用${NC}"
else
    echo -e "${YELLOW}服务未启用${NC}"
fi

# 删除服务文件
echo -e "${YELLOW}删除服务文件...${NC}"
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    echo -e "${GREEN}✓ 服务文件已删除${NC}"
else
    echo -e "${YELLOW}服务文件不存在${NC}"
fi

# 重新加载 systemd
echo -e "${YELLOW}重新加载 systemd 配置...${NC}"
systemctl daemon-reload

# 删除安装目录
echo -e "${YELLOW}删除安装目录...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ 安装目录已删除${NC}"
else
    echo -e "${YELLOW}安装目录不存在${NC}"
fi

echo -e "${GREEN}卸载完成！${NC}"
