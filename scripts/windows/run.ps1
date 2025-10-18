# 不同的程序可以修改 $AppName = "check-web-alive"。这个会影响到后台进行监控的程序名称。
param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))),
    [string]$AppName = "check-web-alive"
)

$ErrorActionPreference = "Stop"

# 切到项目根目录
Set-Location $ProjectRoot

# 日志目录（程序内部会处理日志文件）
$logDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

# 查找 dist 下最新的 exe（兼容 onefile 或目录结构）
$distDir = Join-Path $ProjectRoot "dist"
if (-not (Test-Path $distDir)) { throw "未找到 dist 目录，请先使用 PyInstaller 生成可执行文件。" }

$exe = Get-ChildItem -Path $distDir -Filter *.exe -Recurse -ErrorAction Stop |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $exe) { throw "未在 dist 中找到 .exe，请先使用 PyInstaller 生成。" }

# 运行 exe
Write-Host "启动 $AppName 监控程序..."
Write-Host "可执行文件: $($exe.FullName)"
Write-Host "日志目录: $logDir"
Write-Host "按 Ctrl+C 停止程序"

try {
    & $exe.FullName
} catch {
    Write-Error "程序运行出错: $_"
    exit 1
}
