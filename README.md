# 网站存活监控（Windows/Linux）

监控 `https://www.axured.cn` 是否可访问。每分钟检查一次；当返回 4xx/5xx 或请求异常时，发送邮件告警（主题：`axure网站挂了`）。支持开机自启动（Windows 计划任务 / Linux systemd 服务）。

## 安装

### Windows

1. 安装 Python 3.9+（并勾选 Add to PATH）
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 生成可执行文件：
   ```bash
   pyinstaller --onefile check-web-alive.py
   ```
### Linux

1. 安装 Python 3.9+ 和 pip
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. （可选）生成可执行文件：
   ```bash
   pyinstaller --onefile check-web-alive.py
   ```

## 配置

程序支持从 `.env` 或系统环境变量读取配置。默认目标地址为 `https://www.axured.cn`，检查间隔 60 秒。

在项目根目录创建 `.env`（与 `app` 同级）：
```ini
TARGET_URL=https://www.axured.cn
CHECK_INTERVAL_SECONDS=60
REQUEST_TIMEOUT_SECONDS=10

MAIL_TO=astonish921@126.com
MAIL_FROM=your_from_address@example.com

SMTP_HOST=smtp.126.com
SMTP_PORT=465
SMTP_USERNAME=your_account@126.com
SMTP_PASSWORD=your_smtp_auth_code
SMTP_USE_TLS=true
```

> 注：126/QQ 邮箱需开启 SMTP 并使用授权码作为密码。

也可直接设置环境变量（示例）：
```powershell
$env:TARGET_URL="https://www.axured.cn"
$env:MAIL_TO="astonish921@126.com"
$env:SMTP_HOST="smtp.126.com"
$env:SMTP_PORT="465"
$env:SMTP_USERNAME="your_account@126.com"
$env:SMTP_PASSWORD="your_smtp_auth_code"
$env:SMTP_USE_TLS="true"
```

## 本地运行

### Windows

```powershell
pwsh -File .\scripts\run.ps1
```

### Linux

```bash
./scripts/run-linux.sh
```

日志输出到 `logs/check-web-alive-YYYY-MM-DD.log`。

## 开机自启动

### Windows（计划任务）

1. 允许脚本执行（一次性）：
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
2. 注册计划任务（当前用户权限运行）：
   ```powershell
   pwsh -File .\scripts\register_task.ps1 -TaskName "CheckWebAlive"
   ```
3. 或以 SYSTEM 身份运行（无需登录也会运行）：
   ```powershell
   pwsh -File .\scripts\register_task.ps1 -TaskName "CheckWebAlive" -RunAsSystem
   ```

### Linux（systemd 服务）

1. 安装服务（需要 root 权限）：
   ```bash
   sudo ./scripts/install-linux.sh
   ```
   
   安装脚本会自动检测：
   - 如果存在 `dist/check-web-alive` 可执行文件，使用可执行文件模式
   - 否则使用 Python 脚本模式（需要系统安装 Python 3.9+ 和依赖包）

2. 服务管理命令：
   ```bash
   # 启动服务
   sudo systemctl start check-web-alive
   
   # 停止服务
   sudo systemctl stop check-web-alive
   
   # 重启服务
   sudo systemctl restart check-web-alive
   
   # 查看状态
   sudo systemctl status check-web-alive
   
   # 查看日志
   sudo journalctl -u check-web-alive -f
   ```

3. 卸载服务：
   ```bash
   sudo ./scripts/uninstall-linux.sh
   ```

## 目录结构
```
check-web-alive.py
dist/
    check-web-alive.exe   # windows可执行文件，pyinstaller --onefile check-web-alive.py生成。这样拷贝到其他服务上就不需要安装python相关的内容了
scripts/
  run.ps1                    # Windows 运行脚本
  register_task.ps1          # Windows 计划任务注册
  run-linux.sh              # Linux 运行脚本
  install-linux.sh          # Linux 安装脚本
  uninstall-linux.sh        # Linux 卸载脚本
  check-web-alive.service   # Linux systemd 服务文件
logs/
  check-web-alive-YYYY-MM-DD.log (按天分割的日志文件)
  state.json (状态记录文件)
.env (配置文件)
```

## 日志功能
- **按天分割**：日志文件按日期命名，格式为 `check-web-alive-YYYY-MM-DD.log`
- **自动清理**：默认保留最近30天的日志文件，超期自动删除
- **详细记录**：记录每次检查结果、状态变更、邮件发送情况等
- **双重输出**：同时输出到日志文件和控制台
- **路径兼容**：自动适配 PyInstaller 打包环境，日志存储在用户数据目录

**日志文件位置**：
- 开发环境：`./logs/check-web-alive-YYYY-MM-DD.log`
- 打包后：
  - Windows: `%APPDATA%/check-web-alive/logs/`
  - Linux: `/opt/check-web-alive/logs/` (systemd 服务) 或 `~/.local/share/check-web-alive/logs/` (用户运行)

可通过 `.env` 中的 `LOG_RETENTION_DAYS` 配置日志保留天数（默认30天）。

## 单实例保护
- **跨平台锁机制**：Windows 使用命名互斥量，Linux 使用文件锁
- **自动退出**：检测到重复实例时自动退出，避免资源冲突
- **优雅退出**：支持 Ctrl+C 中断，自动清理锁资源

## 说明
- 仅在状态从"正常"变为"异常"时发送一封告警，避免重复刷屏。
- 邮件主题固定为：`axure网站挂了`；正文包含状态码/异常与时间。
- 如需更改目标站点或收件人，修改 `.env` 或环境变量即可。
- 程序启动时会自动清理过期日志文件，无需手动维护。
- 支持 Windows 和 Linux 双平台，开机自启动，单实例保护。
