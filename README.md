# 网站存活监控（Windows/Linux）

监控指定网站是否可访问。每分钟检查一次；当返回 4xx/5xx 或请求异常时，发送邮件告警。支持开机自启动（Windows 计划任务 / Linux systemd 服务）。
- 仅在状态从"正常"变为"异常"时发送一封告警，避免重复刷屏。
- 邮件主题和内容可根据需要自定义。
- 如需更改目标站点或收件人，修改 `.env` 文件即可。
- 单例执行能力：防止程序重复运行

## 代码目录结构
```
check-web-alive.py
scripts/
  linux/                    # Linux 相关脚本
    run-linux.sh              # Linux 运行脚本
    install-linux.sh          # Linux 安装脚本
    uninstall-linux.sh       # Linux 卸载脚本
    common_tpl.service              # Linux systemd 服务文件 的模板文件，运行install-linux.sh时会生成一个正式的service文件
  windows/                  # Windows 相关脚本
    run.ps1                    # Windows 运行脚本
    register_task.ps1          # Windows 计划任务注册    
  README.md                 # 脚本使用说明
logs/
  check-web-alive-YYYY-MM-DD.log (按天分割的日志文件)
rundata/
  state.json (状态记录文件)
  check-web-alive.lock (单实例锁文件，运行时创建)
.env (配置文件)
```

## 配置文件 .env
```ini
# 目标网站配置
TARGET_URL=https://example.com
CHECK_INTERVAL_SECONDS=60
REQUEST_TIMEOUT_SECONDS=10

# 邮件通知配置
MAIL_TO=admin@example.com
MAIL_FROM=noreply@example.com

# SMTP服务器配置
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_smtp_password
SMTP_USE_TLS=true

# 日志配置
LOG_RETENTION_DAYS=30
```

> 注：请根据您的邮件服务商要求配置SMTP参数。部分邮箱需要开启SMTP并使用授权码作为密码。
> 注：如果有.my-env文件，以这个为准。它的优先级给.env的高。

**日志文件位置**：
- 开发环境：`./logs/check-web-alive-YYYY-MM-DD.log`
- 打包后：
  - Windows: `%APPDATA%/check-web-alive/logs/`
  - Linux: `/opt/check-web-alive/logs/` (systemd 服务) 或 `~/.local/share/check-web-alive/logs/` (用户运行)

可通过 `.env` 中的 `LOG_RETENTION_DAYS` 配置日志保留天数（默认30天）。

## 本地开发时测试
### step1: 配置文件，参考上面的“配置文件说明”
### step2: 安装依赖
1. 安装 Python 3.6.8+
2. 安装依赖，否则python-dotenv没安装导致配置文件读取异常
定位到代码根目录，执行
   ```bash
   pip install -r requirements.txt
   ```

### stpe3: 定位到check-web-alive.py所在目录，执行命令
```powershell
python check-web-alive.py
```

## 服务器部署运行
### Windows

至少包括这些文件：
```
dist
   check-web-alive.exe
scripts/
  linux/                    # Linux 相关脚本
    run-linux.sh              # Linux 运行脚本
    install-linux.sh          # Linux 安装脚本
    uninstall-linux.sh       # Linux 卸载脚本
    common_tpl.service              # Linux systemd 服务文件 的模板文件，运行install-linux.sh时会生成一个正式的service文件
  windows/                  # Windows 相关脚本
    run.ps1                    # Windows 运行脚本
    register_task.ps1          # Windows 计划任务注册    
  README.md                 # 脚本使用说明
.env (配置文件)
```

要求将python程序生成的exe文件（如何生成exe文件，将附录是说明），如果检测到在dist文件夹没有exe文件，执行命令时会报错提醒。
```powershell
pwsh -File .\scripts\windows\run.ps1
```

如何生成exe文件参考最后的附录。

### Linux
### step1:安装python及依赖

1. 安装 Python 3.6.8+ 和 pip
2. 安装依赖：
   一定是要先执行这个，否则python-dotenv没安装导致配置文件读取异常
   ```bash
   pip install -r requirements.txt
   ```
### step2: 执行命令（如下是跑起来，关闭窗口后就断了，如果要后台进度，见下面“开机自启动”的说明）
```bash
./scripts/linux/run-linux.sh
```

日志输出到 `logs/check-web-alive-YYYY-MM-DD.log`。


如果提示找不到文件，检查此sh文件的权限。
1. 首先，使用 ls -l 命令检查文件的权限：ls -l ./scripts/run-linux.sh
这将显示文件的详细信息，包括权限。例如：
```
-rw-r--r-- 1 root root 1234 Oct 17 10:00 ./scripts/run-linux.sh
```
在这个例子中，文件的权限是 -rw-r--r--，表示所有者（root）有读写权限，组和其他用户只有读权限，没有执行权限。

2. 添加执行权限
如果文件没有执行权限，你可以使用 chmod 命令添加执行权限。运行以下命令：
```
chmod +x ./scripts/run-linux.sh
```
这将为当前用户添加执行权限。再次检查文件权限：
```
ls -l ./scripts/run-linux.sh
```
你应该会看到类似以下的输出：
```
-rwxr-xr-x 1 root root 1234 Oct 17 10:00 ./scripts/run-linux.sh
```
现在，文件已经具有执行权限。

## 开机自启动

### Windows（计划任务）
要求将python程序生成的exe文件，如果检测到在dist文件夹没有exe文件，执行命令时会报错提醒。
1. 允许脚本执行（一次性）：
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
2. 注册开机立即执行的计划任务（当前用户权限运行），执行后也会马上执行程序，不要等下次开机：
   ```powershell
   pwsh -File .\scripts\windows\register_task.ps1 -TaskName "CheckWebAlive"
   ```
3. 推荐：注册开机立即执行的计划任务，以 SYSTEM 身份运行（无需登录也会运行），需要使用管理员身份运行powershell,再来执行如下的命令。执行后也会马上执行程序，不要等下次开机。
   ```powershell
   pwsh -File .\scripts\windows\register_task.ps1 -TaskName "CheckWebAlive" -RunAsSystem
   ```

### Linux（systemd 服务）

1. 安装服务（需要 root 权限）：
   如果提示找不到文件，检查此sh文件的权限。
   ```bash
   sudo ./scripts/linux/install-linux.sh
   ```
   
   安装脚本使用 Python 脚本模式（需要系统安装 Python 3.6.8+ 和依赖包）

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
  如果提示找不到文件，检查此sh文件的权限。
   ```bash
   sudo ./scripts/linux/uninstall-linux.sh
   ```


## 通用基础模块

本项目包含一个通用的基础模块 `src/base.py`，提供以下通用能力：

1 单例执行能力：防止程序重复运行
- 跨平台锁机制：Windows 使用命名互斥量，Linux 使用文件锁
- 自动退出：检测到重复实例时自动退出，避免资源冲突
- 优雅退出：支持 Ctrl+C 中断，自动清理锁资源
2 日志登记能力：
- 按天分割：日志文件按日期命名，格式为 `XX-YYYY-MM-DD.log`
- 自动清理：默认保留最近30天的日志文件，超期自动删除
- 详细记录：记录每次检查结果、状态变更、邮件发送情况等
- 双重输出：同时输出到日志文件和控制台
- 路径兼容：自动适配 PyInstaller 打包环境，日志存储在用户数据目录
3 配置文件加载能力
- 支持 .env 文件
- 支持 个性化.my-env文件，如果存在优先使用这个
4 邮件发送能力
- 支持 SMTP 邮件发送

其他项目可以直接使用这些通用能力，无需重复开发。

### 使用示例

```python
from src.base import BaseApp

# 创建应用实例
app = BaseApp("my-app")

# 获取单例锁
if not app.acquire_single_instance_lock():
    print("程序已在运行")
    exit(1)

try:
    # 设置日志
    logger = app.setup_logging()
    
    # 加载配置
    config = app.load_config()
    
    # 发送邮件
    app.send_mail(config, "主题", "内容")
    
finally:
    # 释放锁
    app.release_single_instance_lock()
```

## 附录

### windows下如何生成一个exe文件
1、要提前安装好pyinstaller （使用pip install pyinstaller）
2、然后定位到check-web-alive.py所在的目录，然后执行：
   ```bash
   pyinstaller --onefile check-web-alive.py
   ```