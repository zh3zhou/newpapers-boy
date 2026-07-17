# 会打岔的学术速递

[中文（默认）](README.md) · [English](README.en.md)

每天搜集学术内容，穿插艺术和轻松内容，生成 Markdown、中文语音和邮件。Agent 负责研究与编辑，脚本负责结构验证、链接检查、TTS、邮件和运行证据。

项目不绑定某个 IDE 或 agent 平台：人类偏好在 `config.md`，agent 契约在 `AGENTS.md`，可重复步骤在 `scripts/`，运行结果在本地 `data/` 或 GitHub Actions artifacts。

## 推荐方式：让 Agent 帮你部署

对大多数用户，安装、检查环境、配置本地运行或定时推送的最好方法，是把仓库交给一个能读取文件和运行终端命令的 agent，并直接说：

```text
请读取 AGENTS.md、README.md 和 config.md，帮我部署这个项目。默认用中文交流；检查当前环境后，先说明本地运行和定时推送两种方案，再执行适合当前环境的配置。不要让我在对话中发送密码或 API Key，也不要在未经确认时开启云端定时或修改 GitHub 配置。
```

agent 会按项目契约检查 Python、虚拟环境、邮件/TTS 配置、GitHub 状态和可用的自动化能力，并在需要你选择或输入秘密时停下来说明。你也可以明确说“Please continue in English”，之后让 agent 用英文引导；项目生成内容仍以 `config.md` 的语言设置为准。

如果你只想马上生成一次速递，可以说：

```text
请读取 AGENTS.md 和 config.md，运行今天的学术速递。
```

## 手动安装（可选）

如果你更喜欢自己操作终端，再使用下面的命令。

Windows PowerShell：

```powershell
git clone <your-repo-url>
cd <repo-dir>
.\setup.ps1
```

`setup.ps1` 会创建 `.venv`、安装依赖、准备 `.env`，最后运行本地体检。Windows 优先使用 `py`；即使系统的 `python` 是无效 WindowsApps 别名，也会明确报告。

Linux/macOS：

```bash
sh setup.sh
```

也可以继续手动创建 `.venv`；`setup.sh` 只是把创建环境、安装依赖、准备 `.env` 和本地体检合并为一个可重复入口。

安装完成后，在项目目录对任意有文件、终端和联网能力的 agent 说：

```text
请读取 AGENTS.md 和 config.md，运行今天的学术速递。
```

交互式 agent 会直接完成研究和 Markdown 生成，不需要再填写 `AGENT_RUNNER_CMD` 或单独的 API Key。是否能联网、写文件和运行命令，仍取决于该 agent 当前会话的能力与权限。

### 可移植命令入口

所有确定性 Python CLI 都可以通过脚本路径从任意工作目录调用，并用 `--root` 明确目标项目。相对的 Markdown、MP3、报告和配置路径都基于该根目录解析；省略参数时保持原有行为。在项目根目录内还可以使用 `python -m scripts.<module>` 的模块方式。

```bash
python /path/to/academic-dispatch/run_daily.py 2026-07-15 --root /path/to/academic-dispatch --skip-email
cd /path/to/academic-dispatch
python -m scripts.validate_dispatch 2026-07-15 --root /path/to/academic-dispatch --strict
python -m scripts.tts_generate 2026-07-15 --root /path/to/academic-dispatch
```

这使同一套后处理可以被桌面自动化、CI、容器或另一个 Python 调度器复用，不要求调用方切换到固定工作目录。旧的 `python scripts/<name>.py ...` 入口仍然兼容。

## 邮件和语音

本地配置写在不会提交的 `.env`：

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-name@gmail.com
SMTP_PASS=your-app-password
MAIL_TO=your-name@gmail.com

TTS_VOICE=zh-CN-XiaoxiaoNeural
TTS_RATE=+0%
```

Gmail 使用应用专用密码，QQ 邮箱使用 SMTP 授权码。只生成 Markdown 或音频时，邮箱可以暂不配置。

检查本地状态：

```powershell
.\.venv\Scripts\python.exe scripts\project_doctor.py --target manual
```

## 两种 Agent 模式

| 模式 | 是否额外需要 runner/API | 用途 |
| --- | --- | --- |
| 交互式运行 | 通常不需要 | 在 Codex、其他 IDE agent 或终端 agent 中手动说“运行今天的速递” |
| 无人值守定时 | 需要 | GitHub Actions 到点后必须有可非交互执行的 `AGENT_RUNNER_CMD` 及其凭据 |

GitHub 云端机器不能继承你在本机 Codex 或其他桌面 agent 中的登录。没有真实 runner 时，项目会保持 `DISPATCH_ENABLED=false`，定时事件安全跳过；手动 mock 不受影响。

### 配置真实定时（推荐路径）

真实定时有两条路线：

| 路线 | 需要显式 API Key | 运行位置 | 适合谁 |
| --- | --- | --- | --- |
| Codex/桌面 agent 原生自动化 | 否 | 用户电脑上的 agent 应用 | 已登录桌面 agent、电脑和应用能按时运行的个人用户 |
| GitHub Actions + provider API | 是 | GitHub 云端 | 希望电脑关机后仍能运行、重视云端日志与稳定性的用户 |

#### 路线 A：不用 API，复用 Codex 登录

在支持自动化的 Codex 应用中对 agent 说：

```text
请为这个项目创建每天北京时间 07:00 的本地自动化：读取 AGENTS.md 和 config.md，运行当天的真实学术速递，严格验证后生成 TTS 并发邮件。不要修改 GitHub 配置；失败时保留日志并报告。
```

agent 应先展示自动化名称、时间、工作区和提示词供确认。此路线不设置 `AGENT_RUNNER_CMD`，GitHub 的 `DISPATCH_ENABLED` 保持 `false`。它依赖本机、Codex 应用、当前登录和工作区路径可用；不同 agent 产品如果没有原生自动化能力，就只能手动运行或改用路线 B。

使用其他 agent 应用时，不需要用户自己猜配置。请直接对该 agent 说：

```text
请读取 AGENTS.md 和 RUNTIME_ADAPTERS.md，查询你这个产品的官方文档，判断能否在不提供显式 API Key 的情况下为本项目配置每天 07:00 的真实自动运行；先汇报边界，再引导我配置。
```

项目要求 agent 核实产品版本、原生定时能力、登录是否能用于后台任务、电脑/应用依赖、联网与文件权限、日志位置和费用。官方资料无法确认时不会猜测或擅自开启定时。详细协议见 [`RUNTIME_ADAPTERS.md`](RUNTIME_ADAPTERS.md)。

#### 路线 B：GitHub 云端定时

项目内置 `scripts/openai_dispatch_agent.py`，使用 OpenAI Responses API 的 Web Search 生成真实简报。它需要 [OpenAI API Key](https://platform.openai.com/api-keys) 和 [API 余额/账单设置](https://platform.openai.com/settings/organization/billing/overview)；ChatGPT Plus/Pro 或 Codex 桌面端登录不能替代 API Key，API 使用单独计费。默认使用支持 Web Search、成本相对较低的 [`gpt-5.4-mini`](https://developers.openai.com/api/docs/models/gpt-5.4-mini)。

先只读检查：

```powershell
.\.venv\Scripts\python.exe scripts\configure_real_schedule.py --check-only
```

确认 GitHub、邮箱 mock 都已就绪后运行交互向导：

```powershell
.\.venv\Scripts\python.exe scripts\configure_real_schedule.py
```

向导会在终端中隐藏 API Key 输入，不写入 `.env` 或命令历史。它依次执行：

1. 上传 `OPENAI_API_KEY` 到 GitHub Secrets。
2. 配置内置 runner 和默认模型 `gpt-5.4-mini`。
3. 保持 `DISPATCH_ENABLED=false`，先触发一次真实生成且不发邮件。
4. 等待生成、严格验证和 TTS 全部成功。
5. 再询问是否开启每天北京时间 07:00；只有用户确认才写入 `DISPATCH_ENABLED=true`。

试跑失败时定时保持关闭。把 Actions 运行链接交给 agent，说“请检查这次真实试跑为什么失败”即可继续排查。其他模型可用 `--model 模型名`；其他 provider 仍可按下文的 `AGENT_RUNNER_CMD` 契约接入。

### Agent 命令契约

任何命令只要读取 `AGENTS.md`、`config.md`，并把 UTF-8 Markdown 写到 `DISPATCH_OUTPUT`，都可以成为 `AGENT_RUNNER_CMD`。

运行时注入：

```text
DISPATCH_DATE=YYYY-MM-DD
DISPATCH_OUTPUT=data/YYYY-MM-DD_学术速递.md
DISPATCH_CONFIG=config.md
PROJECT_ROOT=<repo root>
DISPATCH_MODE=ci 或 local
```

`run_agent_command.py` 使用本次临时输出，验证非空 UTF-8 后才替换正式文件，旧文件不能冒充本次成功。子进程只获得基础系统环境、上述契约和允许的 provider 凭据，不会获得 `SMTP_*` 或 `MAIL_TO` 环境变量。

可选配置：

```env
AGENT_RUNNER_CMD=python scripts/my_agent_adapter.py
AGENT_ENV_ALLOWLIST=MY_PROVIDER_KEY
AGENT_TIMEOUT_SECONDS=1800
```

本地 runner 仍能读取项目目录里的 `.env` 文件，因此只应运行可信 agent/命令。GitHub 的 generate job 中不存在本地 `.env`，邮件 Secrets 只注入独立的发送步骤。

## GitHub Actions

`.github/workflows/daily-dispatch.yml` 每天 UTC `23:00` 触发，对应北京时间 `07:00`。流程分为：

1. `generate`：agent/mock 生成 Markdown，执行严格结构和链接检查，上传 source evidence。
2. `deliver`：重新下载并验证 Markdown，生成 MP3，可选发送邮件，上传最终 artifacts。

SMTP Secrets 只进入 `deliver` 的邮件步骤，生成 agent 看不到它们。

### 小白解释

- GitHub repo：项目在 GitHub 上的云端副本。
- Actions：GitHub 提供的定时任务机器。
- Secrets：邮箱授权码、API Key 等密码保险箱。
- Variables：语音、开关、agent 命令等普通配置。
- Artifacts：每次运行保存的 Markdown、MP3、报告和日志。

### 自动诊断和配置

先运行只读检查：

```powershell
.\scripts\setup_github_actions.ps1 -CheckOnly
.\.venv\Scripts\python.exe scripts\project_doctor.py --target github-mock --require-email
```

如果未安装 GitHub CLI：

```powershell
winget install --id GitHub.cli
gh auth login
```

安装后若当前 PowerShell 仍找不到 `gh`，重新打开终端；配置脚本也会自动查找常见安装路径。

workflow 必须先提交并 push 到默认分支。随后运行：

```powershell
.\scripts\setup_github_actions.ps1
```

它会在用户确认后把本地 SMTP 项写入 GitHub Secrets，把 TTS、`AGENT_RUNNER_CMD` 和 `DISPATCH_ENABLED` 写入 Variables，并可触发 mock。

已明确授权 agent 代为配置时，可用显式非交互模式：

```powershell
.\scripts\setup_github_actions.ps1 `
  -NonInteractive -ConfirmWrite -TriggerMock -SendEmailMock
```

非交互写入缺少 `-ConfirmWrite` 会直接失败。没有 `AGENT_RUNNER_CMD` 时，脚本写入 `DISPATCH_ENABLED=false`；只有同时传入真实命令和 `-EnableSchedule` 才会开启定时。

### GitHub 配置映射

| 名称 | 类型 | 来源/用途 |
| --- | --- | --- |
| `SMTP_HOST/PORT/USER/PASS`、`MAIL_TO` | Secret | 对应本地 `.env` 邮件配置 |
| `TTS_VOICE`、`TTS_RATE` | Variable | 播报声音和语速 |
| `AGENT_RUNNER_CMD` | Variable 或 Secret | 无人值守 agent 命令 |
| `AGENT_ENV_ALLOWLIST` | Variable | 额外允许传给 agent 的 provider 环境变量名 |
| `DISPATCH_ENABLED` | Variable | `true` 才允许 schedule 真跑 |
| provider key | Secret | 例如 `OPENAI_API_KEY` 或 `AGENT_PROVIDER_TOKEN` |
| `OPENAI_MODEL` | Variable | 内置 OpenAI runner 使用的模型，默认 `gpt-5.4-mini` |

手动 smoke：在 Actions 页面运行 `Daily Academic Dispatch`，选择 `mock=true`；`send_email=true` 会同时验证 TTS 和邮件。

三个就绪状态：

```powershell
.\.venv\Scripts\python.exe scripts\project_doctor.py --target manual
.\.venv\Scripts\python.exe scripts\project_doctor.py --target github-mock --require-email
.\.venv\Scripts\python.exe scripts\project_doctor.py --target github-scheduled
```

`github-scheduled=disabled` 表示定时开关尚未开启，是没有真实 runner 时的正常状态。

## 不配置 GitHub 也能用

直接让 agent 跑一次：

```text
请读取 AGENTS.md 和 config.md，运行今天的学术速递。
```

已有 Markdown 后验证、生成音频并发邮件：

```powershell
.\.venv\Scripts\python.exe scripts\validate_dispatch.py YYYY-MM-DD --strict --check-links
.\.venv\Scripts\python.exe run_daily.py YYYY-MM-DD
```

只生成音频：

```powershell
.\.venv\Scripts\python.exe run_daily.py YYYY-MM-DD --skip-email
```

以后再配置 GitHub：

```powershell
.\scripts\setup_github_actions.ps1 -CheckOnly
.\scripts\setup_github_actions.ps1
```

## 自定义与目录

编辑 `config.md` 第一节修改学术领域、关键词和条数；编辑第三节修改艺术偏好。修改 `.env` 的 `TTS_VOICE/TTS_RATE` 可更换语音和语速。

```text
academic-dispatch/
├── AGENTS.md                       # 平台无关 agent 契约
├── README.md / README.en.md        # 默认中文说明与可选英文入口
├── RUNTIME_ADAPTERS.md             # 运行时调查与适配协议
├── CHANGELOG.md                    # 重要版本和验证记录
├── config.md                       # 人类内容偏好
├── setup.ps1 / setup.sh            # Windows 与 Linux/macOS 初始化
├── .github/workflows/
│   └── daily-dispatch.yml          # 隔离的生成/交付流程
├── scripts/
│   ├── dispatch_config.py          # 配置表纯解析
│   ├── dispatch_markdown.py        # Markdown 内容模型纯解析
│   ├── dispatch_paths.py           # 项目布局、日期和工件命名
│   ├── project_doctor.py           # 三种目标的脱敏体检
│   ├── run_agent_command.py        # 通用 agent 命令适配
│   ├── validate_dispatch.py        # 结构、链接和 JSON 报告
│   ├── setup_github_actions.ps1    # GitHub 配置向导
│   ├── tts_generate.py             # Markdown 到 MP3
│   └── push_email.py               # SMTP 邮件
├── run_daily.py                    # 后处理入口
├── tests/                          # unittest 单元/集成测试
├── data/                           # 本地生成物，不入 Git
└── archive/                        # 本地归档，不入 Git
```

## 隐私与测试

- `.env`、`data/`、`archive/` 默认不提交。
- GitHub artifacts 可能包含生成内容，不要在简报中写秘密。
- 邮箱授权码和 API Key 只放 `.env` 或 GitHub Secrets。
- URL 检查拒绝 localhost、私网、link-local 和保留地址；404/410 失败，403/429/临时网络错误记为 warning。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\validate_dispatch.py 2026-07-04 --strict --check-links
```

Linux/macOS 对应使用 `.venv/bin/python`。命令也支持模块方式，例如 `python -m scripts.validate_dispatch --help`。

## License

MIT
