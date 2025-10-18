param(
    [string]$TaskName = "CheckWebAlive",
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [switch]$RunAsSystem
)

$ErrorActionPreference = "Stop"

Write-Host "开始注册计划任务..."

# 查找 dist 下最新 exe
$distDir = Join-Path $ProjectRoot "dist"
if (-not (Test-Path $distDir)) { throw "未找到 dist 目录，请先用 PyInstaller 生成可执行文件。" }
$exe = Get-ChildItem -Path $distDir -Filter *.exe -Recurse -ErrorAction Stop |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $exe) { throw "未在 dist 中找到 .exe，请先用 PyInstaller 生成。" }

Write-Host "找到可执行文件: $($exe.FullName)"

# 计划任务直接执行 exe
$taskCmd = '"' + $exe.FullName + '"'
Write-Host "任务命令: $taskCmd"

# 删除已存在同名任务（仅同名一条）
Write-Host "删除已存在的任务: $TaskName"
$deleteResult = Start-Process -FilePath "schtasks" -ArgumentList "/Delete", "/TN", $TaskName, "/F" -WindowStyle Hidden -Wait -PassThru -ErrorAction SilentlyContinue
Write-Host "删除任务结果: $($deleteResult.ExitCode)"

# 创建开机任务
Write-Host "创建开机任务: $TaskName"
$createArgs = @("/Create", "/TN", $TaskName, "/SC", "ONSTART", "/TR", $taskCmd, "/RL", "HIGHEST")
if ($RunAsSystem) { 
    $createArgs += @("/RU", "SYSTEM")
    Write-Host "以 SYSTEM 身份运行"
} else {
    Write-Host "以当前用户身份运行"
}

$createResult = Start-Process -FilePath "schtasks" -ArgumentList $createArgs -WindowStyle Hidden -Wait -PassThru
Write-Host "创建任务结果: $($createResult.ExitCode)"

if ($createResult.ExitCode -eq 0) {
    Write-Host "计划任务创建成功！"
    
    # 立即执行一次任务进行测试
    Write-Host "立即执行任务进行测试..."
    $runResult = Start-Process -FilePath "schtasks" -ArgumentList "/Run", "/TN", $TaskName -WindowStyle Hidden -Wait -PassThru
    Write-Host "立即执行结果: $($runResult.ExitCode)"
    
    if ($runResult.ExitCode -eq 0) {
        Write-Host "任务已立即执行，请检查日志文件确认是否正常运行"
        Write-Host "日志位置: $ProjectRoot\logs\"
    } else {
        Write-Host "任务执行失败，请检查任务计划程序中的错误信息"
    }
} else {
    Write-Host "计划任务创建失败！"
}

Write-Host "注册完成。"
