# setup.ps1 — 一键初始化环境
# 用法（PowerShell）：
#   .\setup.ps1
#
# 功能：检测 Python → 创建虚拟环境 → 安装依赖 → 复制 .env 模板 → 项目体检

param(
    [string]$PythonCmd = ""
)

$ErrorActionPreference = "Stop"
$WorkDir = $PSScriptRoot
$InstalledPython312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not $PythonCmd) {
    $PythonCmd = if (Test-Path $InstalledPython312) { $InstalledPython312 } else { "python" }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  会打岔的学术速递 — 环境初始化" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检测 Python
Write-Host "[1/5] 检测 Python..." -ForegroundColor Yellow
try {
    $pyProbe = & $PythonCmd -c "import sys;print(sys.version_info[0],sys.version_info[1],sys.version_info[2])" 2>&1
    if ($LASTEXITCODE -ne 0 -or "$pyProbe" -notmatch "^(\d+)\s+(\d+)\s+(\d+)$") {
        throw "Python 探针没有返回有效结果"
    }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
        throw "需要 Python 3.9+，当前是 $major.$minor"
    }
    Write-Host "  找到: Python $($Matches[1]).$($Matches[2]).$($Matches[3])" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 未检测到 Python（命令: $PythonCmd）。" -ForegroundColor Red
    Write-Host "  请安装 Python 3.9+ 并确保已加入 PATH，或指定 -PythonCmd 参数。" -ForegroundColor Red
    exit 1
}

# 2. 创建虚拟环境
$VenvDir = Join-Path $WorkDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (Test-Path $PythonExe) {
    $venvHealthy = $false
    try {
        & $PythonExe --version *> $null
        $venvHealthy = ($LASTEXITCODE -eq 0)
    } catch {
        $venvHealthy = $false
    }
    if (-not $venvHealthy) {
        $backup = Join-Path $WorkDir (".venv.broken-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        Write-Host "[WARN] 现有 .venv 已损坏，保留为 $backup" -ForegroundColor Yellow
        Move-Item -LiteralPath $VenvDir -Destination $backup
    }
}
if (-not (Test-Path $PythonExe)) {
    Write-Host "[2/5] 创建虚拟环境 .venv ..." -ForegroundColor Yellow
    & $PythonCmd -m venv .venv
    Write-Host "  虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "[2/5] 虚拟环境已存在，跳过创建" -ForegroundColor Green
}

# 3. 安装依赖
Write-Host "[3/5] 安装依赖..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip | Out-Null
& $PythonExe -m pip install -r (Join-Path $WorkDir "requirements.lock.txt")
Write-Host "  依赖安装完成" -ForegroundColor Green

# 4. 复制 .env 模板
$EnvFile = Join-Path $WorkDir ".env"
$EnvExample = Join-Path $WorkDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    Write-Host "[4/5] 创建 .env 配置文件..." -ForegroundColor Yellow
    Copy-Item $EnvExample $EnvFile
    Write-Host "  .env 已创建，请用编辑器打开并填写你的邮箱配置（SMTP_PASS 等）。" -ForegroundColor Green
} else {
    Write-Host "[4/5] .env 已存在，跳过复制" -ForegroundColor Green
}

Write-Host "[5/5] 运行本地模式体检..." -ForegroundColor Yellow
& $PythonExe (Join-Path $WorkDir "scripts\project_doctor.py") --target manual
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] 体检发现阻断项，请按上方 NEXT 提示处理。" -ForegroundColor Yellow
} else {
    Write-Host "  本地模式已就绪" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  初始化完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1. 编辑 .env 文件，填写 SMTP_USER / SMTP_PASS / MAIL_TO" -ForegroundColor White
Write-Host "  2. 在项目里对 agent 说：请读取 AGENTS.md 和 dispatch.config.json，运行今天的学术速递" -ForegroundColor White
Write-Host "  3. 自动运行诊断：.\scripts\setup_github_actions.ps1 -CheckOnly" -ForegroundColor White
Write-Host ""
