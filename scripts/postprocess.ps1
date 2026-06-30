# postprocess.ps1 — 学术速递后处理：TTS 音频生成 + 邮件推送
# 用法（在 PowerShell 中）：
#   .\scripts\postprocess.ps1              # 处理今日速递
#   .\scripts\postprocess.ps1 2026-06-30   # 处理指定日期

param(
    [string]$Date = (Get-Date -Format "yyyy-MM-dd")
)

$ErrorActionPreference = "Stop"

$WorkDir = Split-Path -Parent $PSScriptRoot
if (-not $WorkDir) { $WorkDir = $PWD.Path }

$DataDir = Join-Path $WorkDir "data"
$PythonExe = Join-Path $WorkDir ".venv\Scripts\python.exe"
$TtsScript = Join-Path $WorkDir "scripts\tts_generate.py"
$PushScript = Join-Path $WorkDir "scripts\push_email.py"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python 虚拟环境不存在，请先运行: .\setup.ps1" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

$MdFile = Join-Path $DataDir "${Date}_学术速递.md"
if (-not (Test-Path $MdFile)) {
    Write-Host "[ERROR] Markdown 文件不存在: $MdFile" -ForegroundColor Red
    Write-Host "  请先生成当日速递 Markdown 并放入 data/ 目录。" -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  会打岔的学术速递 — 后处理" -ForegroundColor Cyan
Write-Host "  日期: $Date" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: 生成 TTS 音频
Write-Host "[1/2] 生成语音播报..." -ForegroundColor Yellow
& $PythonExe $TtsScript $Date
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] TTS 生成失败" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host ""

# Step 2: 邮件推送（含MP3附件）
Write-Host "[2/2] 发送邮件推送..." -ForegroundColor Yellow
& $PythonExe $PushScript $Date
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] 邮件推送失败，但音频已生成" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "  后处理完成！" -ForegroundColor Green
$mp3 = Join-Path $DataDir "${Date}_学术播报.mp3"
if (Test-Path $mp3) {
    $size = [math]::Round((Get-Item $mp3).Length / 1024, 1)
    Write-Host "  音频文件: $mp3 ($size KB)" -ForegroundColor Green
}
Write-Host "========================================" -ForegroundColor Green
