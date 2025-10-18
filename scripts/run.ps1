param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
)

$ErrorActionPreference = "Stop"

# 切到项目根目录
Set-Location $ProjectRoot

# 日志目录
$logDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "check-web-alive.log"

# 查找 dist 下最新的 exe（兼容 onefile 或目录结构）
$distDir = Join-Path $ProjectRoot "dist"
if (-not (Test-Path $distDir)) { throw "未找到 dist 目录，请先使用 PyInstaller 生成可执行文件。" }

$exe = Get-ChildItem -Path $distDir -Filter *.exe -Recurse -ErrorAction Stop |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $exe) { throw "未在 dist 中找到 .exe，请先使用 PyInstaller 生成。" }

# 运行 exe（追加日志）
& $exe.FullName *>> $logFile
