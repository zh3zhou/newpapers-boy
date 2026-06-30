# setup.ps1 — 一键初始化环境
# 用法（PowerShell）：
#   .\setup.ps1
#
# 功能：检测 Python → 创建虚拟环境 → 安装依赖 → 复制 .env 模板

param(
    [string]$PythonCmd = "py"
)

$ErrorActionPreference = "Stop"
$WorkDir = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  会打岔的学术速递 — 环境初始化" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检测 Python
Write-Host "[1/4] 检测 Python..." -ForegroundColor Yellow
try {
    $pyVersion = & $PythonCmd --version 2>&1
    Write-Host "  找到: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 未检测到 Python（命令: $PythonCmd）。" -ForegroundColor Red
    Write-Host "  请安装 Python 3.9+ 并确保已加入 PATH，或指定 -PythonCmd 参数。" -ForegroundColor Red
    exit 1
}

# 2. 创建虚拟环境
$VenvDir = Join-Path $WorkDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[2/4] 创建虚拟环境 .venv ..." -ForegroundColor Yellow
    & $PythonCmd -m venv .venv
    Write-Host "  虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "[2/4] 虚拟环境已存在，跳过创建" -ForegroundColor Green
}

# 3. 安装依赖
Write-Host "[3/4] 安装依赖..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip | Out-Null
& $PythonExe -m pip install -r (Join-Path $WorkDir "requirements.txt")
Write-Host "  依赖安装完成" -ForegroundColor Green

# 4. 复制 .env 模板
$EnvFile = Join-Path $WorkDir ".env"
$EnvExample = Join-Path $WorkDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    Write-Host "[4/4] 创建 .env 配置文件..." -ForegroundColor Yellow
    Copy-Item $EnvExample $EnvFile
    Write-Host "  .env 已创建，请用编辑器打开并填写你的邮箱配置（SMTP_PASS 等）。" -ForegroundColor Green
} else {
    Write-Host "[4/4] .env 已存在，跳过复制" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  初始化完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1. 编辑 .env 文件，填写 SMTP_USER / SMTP_PASS / MAIL_TO" -ForegroundColor White
Write-Host "  2. 将当日学术速递 Markdown 放入 data/ 目录" -ForegroundColor White
Write-Host "  3. 运行 .\scripts\postprocess.ps1 生成音频并推送" -ForegroundColor White
Write-Host ""
