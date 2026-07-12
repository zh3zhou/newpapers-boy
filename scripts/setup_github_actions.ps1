# setup_github_actions.ps1 — GitHub Actions 配置/诊断向导
# 用法：
#   .\scripts\setup_github_actions.ps1 -CheckOnly
#   .\scripts\setup_github_actions.ps1
#   .\scripts\setup_github_actions.ps1 -AgentRunnerCmd "python scripts/my_agent_adapter.py"
#   .\scripts\setup_github_actions.ps1 -NonInteractive -ConfirmWrite -TriggerMock -SendEmailMock
#
# CheckOnly 只做本地和 GitHub 可达性诊断，不写入 GitHub。
# 非 CheckOnly 会在用户确认后写入 GitHub Secrets/Variables。

param(
    [string]$Repo = "",
    [string]$AgentRunnerCmd = "",
    [switch]$TriggerMock,
    [switch]$SendEmailMock,
    [switch]$EnableSchedule,
    [switch]$NonInteractive,
    [switch]$ConfirmWrite,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$WorkDir = Split-Path -Parent $PSScriptRoot
if (-not $WorkDir) { $WorkDir = $PWD.Path }
Set-Location $WorkDir

function Read-DotEnv {
    param([string]$Path)
    $envMap = @{}
    if (-not (Test-Path $Path)) { return $envMap }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        $envMap[$key] = $value
    }
    return $envMap
}

function Mask-Value {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "<missing>" }
    if ($Value.Contains("@")) {
        $parts = $Value.Split("@", 2)
        $prefix = $parts[0].Substring(0, [Math]::Min(2, $parts[0].Length))
        return "$prefix***@$($parts[1])"
    }
    return "<set>"
}

function Get-CommandText {
    param([string[]]$Command)
    try {
        $output = & $Command[0] @($Command[1..($Command.Length - 1)]) 2>$null
        if ($LASTEXITCODE -ne 0) { return "" }
        return (($output | Out-String).Trim())
    } catch {
        return ""
    }
}

function Get-RepoFromRemote {
    $url = Get-CommandText @("git", "remote", "get-url", "origin")
    if (-not $url) { return "" }
    if ($url -match "github\.com[:/](.+?)(\.git)?$") {
        return $Matches[1] -replace "\.git$", ""
    }
    return ""
}

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMs = 5000
    )
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Confirm-Step {
    param([string]$Message)
    $answer = Read-Host "$Message [y/N]"
    return $answer -match "^(y|Y|yes|YES)$"
}

function Write-Status {
    param(
        [string]$Status,
        [string]$Message
    )
    $color = "White"
    if ($Status -eq "OK") { $color = "Green" }
    elseif ($Status -eq "WARN") { $color = "Yellow" }
    elseif ($Status -eq "BLOCK") { $color = "Red" }
    elseif ($Status -eq "INFO") { $color = "Cyan" }
    Write-Host ("[{0}] {1}" -f $Status, $Message) -ForegroundColor $color
}

function Find-GitHubCli {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        (Join-Path $env:ProgramFiles "GitHub CLI\gh.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "GitHub CLI\gh.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe"),
        (Join-Path $env:LOCALAPPDATA "GitHub CLI\gh.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return ""
}

function Invoke-Gh {
    param(
        [string]$GhPath,
        [string[]]$Arguments
    )
    & $GhPath @Arguments
    return $LASTEXITCODE
}

function Set-GhSecret {
    param(
        [string]$GhPath,
        [string]$Name,
        [string]$Repo,
        [string]$Value
    )
    if ($Name -notmatch "^[A-Z0-9_]+$") { throw "无效的 secret 名称: $Name" }
    if ($Repo -notmatch "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") { throw "无效的 GitHub repo: $Repo" }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $GhPath
    $startInfo.Arguments = "secret set `"$Name`" --repo `"$Repo`""
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $process.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $process.StandardInput.BaseStream.Flush()
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($stdout.Trim()) { Write-Host $stdout.Trim() }
    if ($stderr.Trim()) { Write-Host $stderr.Trim() -ForegroundColor Red }
    return $process.ExitCode
}

function Test-GitHubDns {
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses("github.com")
        return @($addresses | ForEach-Object { $_.IPAddressToString })
    } catch {
        return @()
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  会打岔的学术速递 — GitHub Actions 配置向导" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
if ($CheckOnly) {
    Write-Host "模式：只读诊断，不会写入 GitHub。" -ForegroundColor Cyan
}
Write-Host ""

$canConfigure = $true
$canTriggerMock = $true
$notes = New-Object System.Collections.Generic.List[string]

if (-not $Repo) {
    $Repo = Get-RepoFromRemote
}
if ($Repo) {
    Write-Status "OK" "GitHub repo: $Repo"
} else {
    Write-Status "BLOCK" "没有识别到 GitHub remote。先创建 GitHub 仓库并设置 origin。"
    $canConfigure = $false
    $canTriggerMock = $false
}

$currentBranch = Get-CommandText @("git", "branch", "--show-current")
if ($currentBranch) {
    Write-Status "INFO" "当前本地分支: $currentBranch"
}
$upstream = Get-CommandText @("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
if ($upstream) {
    Write-Status "INFO" "当前分支上游: $upstream"
} else {
    Write-Status "WARN" "当前分支没有上游。push 前可能需要设置 upstream。"
}

$workflowPath = Join-Path $WorkDir ".github\workflows\daily-dispatch.yml"
if (Test-Path $workflowPath) {
    Write-Status "OK" "workflow 文件存在: .github/workflows/daily-dispatch.yml"
} else {
    Write-Status "BLOCK" "未找到 workflow 文件: .github/workflows/daily-dispatch.yml"
    $canTriggerMock = $false
}

$trackedWorkflowOutput = Get-CommandText @("git", "ls-files", ".github/workflows/daily-dispatch.yml")
if ($trackedWorkflowOutput) {
    Write-Status "OK" "workflow 文件已被 Git 跟踪。"
} else {
    Write-Status "WARN" "workflow 文件还没有被 Git 跟踪/提交；GitHub Actions 页面暂时不会出现它。"
    $canTriggerMock = $false
}

$uncommitted = Get-CommandText @("git", "status", "--short")
if ($uncommitted) {
    Write-Status "WARN" "当前有未提交改动。要让 GitHub Actions 生效，需要 commit 并 push。"
} else {
    Write-Status "OK" "工作区没有未提交改动。"
}

$dns = @(Test-GitHubDns)
if ($dns.Count -gt 0) {
    Write-Status "OK" "github.com DNS 可解析: $($dns -join ', ')"
} else {
    Write-Status "BLOCK" "github.com DNS 解析失败。"
    $canConfigure = $false
    $canTriggerMock = $false
}

$tcpOk = Test-TcpPort -HostName "github.com" -Port 443 -TimeoutMs 5000
if ($tcpOk) {
    Write-Status "OK" "github.com:443 可连接。"
} else {
    Write-Status "BLOCK" "github.com:443 当前不可连接。请检查网络、代理或防火墙。"
    $canConfigure = $false
    $canTriggerMock = $false
}

$ghPath = Find-GitHubCli
if ($ghPath) {
    Write-Status "OK" "GitHub CLI 已安装: $ghPath"
    try {
        Invoke-Gh -GhPath $ghPath -Arguments @("auth", "status") 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "OK" "GitHub CLI 已登录。"
            if ($Repo) {
                $canonicalRepo = Get-CommandText @($ghPath, "repo", "view", $Repo, "--json", "nameWithOwner", "--jq", ".nameWithOwner")
                if ($canonicalRepo -and $canonicalRepo -ne $Repo) {
                    Write-Status "INFO" "GitHub 仓库已重命名，使用当前名称: $canonicalRepo"
                    $Repo = $canonicalRepo
                }
            }
        } else {
            Write-Status "BLOCK" "GitHub CLI 尚未登录。请运行: `"$ghPath`" auth login"
            $canConfigure = $false
            $canTriggerMock = $false
        }
    } catch {
        Write-Status "BLOCK" "无法检查 GitHub CLI 登录状态。请运行: `"$ghPath`" auth status"
        $canConfigure = $false
        $canTriggerMock = $false
    }
} else {
    Write-Status "BLOCK" "未检测到 GitHub CLI（gh）。安装: winget install --id GitHub.cli"
    $canConfigure = $false
    $canTriggerMock = $false
}

$dotEnvPath = Join-Path $WorkDir ".env"
$dotEnv = Read-DotEnv $dotEnvPath
if (Test-Path $dotEnvPath) {
    Write-Status "OK" ".env 存在。"
} else {
    Write-Status "BLOCK" ".env 不存在。请先复制 .env.example 为 .env 并填写邮箱配置。"
    $canConfigure = $false
}

$requiredSecrets = @("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO")
$missingSecrets = @()
Write-Host ""
Write-Host "GitHub Secrets 预检查（来自 .env，不显示密码明文）:" -ForegroundColor Cyan
foreach ($name in $requiredSecrets) {
    $value = $dotEnv[$name]
    Write-Host ("  {0} = {1}" -f $name, (Mask-Value $value))
    if ([string]::IsNullOrWhiteSpace($value)) { $missingSecrets += $name }
}
if ($missingSecrets.Count -gt 0) {
    Write-Status "BLOCK" ".env 缺少: $($missingSecrets -join ', ')"
    $canConfigure = $false
} else {
    Write-Status "OK" "SMTP Secrets 已具备，可搬运到 GitHub。"
}

if (-not $AgentRunnerCmd) {
    $AgentRunnerCmd = $dotEnv["AGENT_RUNNER_CMD"]
}
$ttsVoice = $dotEnv["TTS_VOICE"]
if (-not $ttsVoice) { $ttsVoice = "zh-CN-XiaoxiaoNeural" }
$ttsRate = $dotEnv["TTS_RATE"]
if (-not $ttsRate) { $ttsRate = "+0%" }

Write-Host ""
Write-Host "GitHub Variables 预检查:" -ForegroundColor Cyan
Write-Host "  TTS_VOICE = $ttsVoice"
Write-Host "  TTS_RATE = $ttsRate"
if ($AgentRunnerCmd) {
    Write-Host "  AGENT_RUNNER_CMD = <set>"
    Write-Status "OK" "AGENT_RUNNER_CMD 已配置。真实定时运行可尝试调用 agent。"
} else {
    Write-Host "  AGENT_RUNNER_CMD = <missing>"
    Write-Status "WARN" "AGENT_RUNNER_CMD 缺失。mock 可跑；真实自动采集还不能跑。"
}
$agentEnvAllowlist = $dotEnv["AGENT_ENV_ALLOWLIST"]
$dispatchEnabled = if ($EnableSchedule) { "true" } else { "false" }
$remoteAgentRunnerSecret = $false
if ($ghPath -and $Repo) {
    $remoteSecretNames = Get-CommandText @($ghPath, "secret", "list", "--repo", $Repo, "--json", "name", "--jq", ".[].name")
    $remoteAgentRunnerSecret = @($remoteSecretNames -split "`r?`n") -contains "AGENT_RUNNER_CMD"
}
if ($EnableSchedule -and -not $AgentRunnerCmd -and -not $remoteAgentRunnerSecret) {
    Write-Status "BLOCK" "不能启用定时任务：AGENT_RUNNER_CMD 仍为空。"
    $canConfigure = $false
}
Write-Host "  DISPATCH_ENABLED = $dispatchEnabled"
if ($agentEnvAllowlist) {
    Write-Host "  AGENT_ENV_ALLOWLIST = <set>"
}

Write-Host ""
Write-Host "诊断结论:" -ForegroundColor Cyan
if ($canConfigure) {
    Write-Status "OK" "可以尝试自动写入 GitHub Secrets/Variables。"
} else {
    Write-Status "BLOCK" "当前还不能自动配置 GitHub。先处理上面的 BLOCK 项。"
}
if ($canTriggerMock) {
    Write-Status "OK" "配置完成后可以触发 mock workflow。"
} else {
    Write-Status "WARN" "暂时不能触发 mock workflow；通常是 workflow 未 push、gh 缺失/未登录或 GitHub 网络不通。"
}
if (-not $AgentRunnerCmd) {
    Write-Status "INFO" "即使不配置 AGENT_RUNNER_CMD，也可以先用 mock 测试 GitHub Actions 链路。"
}

if ($CheckOnly) {
    Write-Host ""
    Write-Host "[INFO] CheckOnly 完成，没有写入 GitHub。" -ForegroundColor Cyan
    exit 0
}

if (-not $canConfigure) {
    Write-Host ""
    Write-Host "下一步建议：" -ForegroundColor Yellow
    Write-Host "  1. 确保能访问 https://github.com"
    Write-Host "  2. 安装 GitHub CLI: winget install --id GitHub.cli"
    Write-Host "  3. 登录 GitHub CLI: gh auth login"
    Write-Host "  4. 提交并 push workflow 文件后，重新运行本脚本"
    exit 1
}

if (-not $AgentRunnerCmd) {
    Write-Host ""
    Write-Host "[WARN] 尚未配置 AGENT_RUNNER_CMD。" -ForegroundColor Yellow
    Write-Host "它是 GitHub Actions 调用 agent 的命令。没有它，定时真实运行会失败，但 mock 测试仍可跑。"
    Write-Host "示例（按你实际 agent 替换）:"
    Write-Host '  python scripts/my_agent_adapter.py'
    Write-Host '  your-agent-cli run --instructions AGENTS.md'
    if (-not $NonInteractive) {
        $AgentRunnerCmd = Read-Host "请输入 AGENT_RUNNER_CMD；如果暂时没有，直接回车跳过"
    }
}

Write-Host ""
Write-Host "将要写入 GitHub Secrets（不会显示密码明文）:" -ForegroundColor Cyan
foreach ($name in $requiredSecrets) {
    Write-Host ("  {0} = {1}" -f $name, (Mask-Value $dotEnv[$name]))
}

Write-Host ""
Write-Host "将要写入 GitHub Variables:" -ForegroundColor Cyan
Write-Host "  TTS_VOICE = $ttsVoice"
Write-Host "  TTS_RATE = $ttsRate"
if ($AgentRunnerCmd) {
    Write-Host "  AGENT_RUNNER_CMD = <set>"
} else {
    Write-Host "  AGENT_RUNNER_CMD = <skip>"
}
Write-Host "  DISPATCH_ENABLED = $dispatchEnabled"
if ($agentEnvAllowlist) {
    Write-Host "  AGENT_ENV_ALLOWLIST = <set>"
}

Write-Host ""
if ($NonInteractive) {
    if (-not $ConfirmWrite) {
        throw "非交互写入必须显式传入 -ConfirmWrite。"
    }
} else {
    if (-not (Confirm-Step "确认写入 GitHub repo '$Repo' 的 secrets/variables 吗？")) {
        Write-Host "[INFO] 已取消，没有写入 GitHub。"
        exit 0
    }
}

foreach ($name in $requiredSecrets) {
    $secretExitCode = Set-GhSecret -GhPath $ghPath -Name $name -Repo $Repo -Value $dotEnv[$name]
    if ($secretExitCode -ne 0) { throw "写入 secret 失败: $name" }
    Write-Status "OK" "secret: $name"
}

Invoke-Gh -GhPath $ghPath -Arguments @("variable", "set", "TTS_VOICE", "--repo", $Repo, "--body", $ttsVoice)
if ($LASTEXITCODE -ne 0) { throw "写入 variable 失败: TTS_VOICE" }
Write-Status "OK" "variable: TTS_VOICE"

Invoke-Gh -GhPath $ghPath -Arguments @("variable", "set", "TTS_RATE", "--repo", $Repo, "--body", $ttsRate)
if ($LASTEXITCODE -ne 0) { throw "写入 variable 失败: TTS_RATE" }
Write-Status "OK" "variable: TTS_RATE"

if ($AgentRunnerCmd) {
    Invoke-Gh -GhPath $ghPath -Arguments @("variable", "set", "AGENT_RUNNER_CMD", "--repo", $Repo, "--body", $AgentRunnerCmd)
    if ($LASTEXITCODE -ne 0) { throw "写入 variable 失败: AGENT_RUNNER_CMD" }
    Write-Status "OK" "variable: AGENT_RUNNER_CMD"
}

if ($agentEnvAllowlist) {
    Invoke-Gh -GhPath $ghPath -Arguments @("variable", "set", "AGENT_ENV_ALLOWLIST", "--repo", $Repo, "--body", $agentEnvAllowlist)
    if ($LASTEXITCODE -ne 0) { throw "写入 variable 失败: AGENT_ENV_ALLOWLIST" }
    Write-Status "OK" "variable: AGENT_ENV_ALLOWLIST"
}

Invoke-Gh -GhPath $ghPath -Arguments @("variable", "set", "DISPATCH_ENABLED", "--repo", $Repo, "--body", $dispatchEnabled)
if ($LASTEXITCODE -ne 0) { throw "写入 variable 失败: DISPATCH_ENABLED" }
Write-Status "OK" "variable: DISPATCH_ENABLED=$dispatchEnabled"

Write-Host ""
Write-Status "OK" "GitHub Actions 配置写入完成。"

$shouldTriggerMock = $TriggerMock
if (-not $NonInteractive -and -not $TriggerMock) {
    $shouldTriggerMock = Confirm-Step "要现在触发一次 GitHub Actions mock 测试吗？"
}
if ($shouldTriggerMock) {
    $sendEmailValue = if ($SendEmailMock) { "true" } else { "false" }
    Invoke-Gh -GhPath $ghPath -Arguments @("workflow", "run", "daily-dispatch.yml", "--repo", $Repo, "-f", "mock=true", "-f", "send_email=$sendEmailValue")
    if ($LASTEXITCODE -ne 0) { throw "触发 workflow 失败。请确认 workflow 已经 push 到 GitHub。" }
    Write-Status "OK" "已触发 mock workflow（send_email=$sendEmailValue）。"
    Write-Host "查看状态:"
    Write-Host "  gh run list --repo $Repo --workflow daily-dispatch.yml"
    Write-Host "  或打开: https://github.com/$Repo/actions"
}
