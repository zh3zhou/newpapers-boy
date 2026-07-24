# AGENTS.md —「会打岔的学术速递」Portable Agent Contract

> 本文件是给任何 AI agent / agent runtime 的执行契约。人类用户请优先读 `README.md`。
> 目标：让不同 agent 都能完成「采集与编辑」，让脚本和 CI 完成可重复的验证、TTS、邮件和证据留存。

---

## 0. 运行模式判定

执行前先确定模式：

- **CI / 非交互模式**：如果环境变量 `DISPATCH_MODE=ci`，不要执行首次配置向导，不要等待用户输入。读取 `AGENTS.md`、`dispatch.config.json`，按 `DISPATCH_DATE` 和 `DISPATCH_OUTPUT` 生成 Markdown 后退出。验证、TTS、邮件、artifact 上传由脚本和 GitHub Actions 接管。
- **本地交互模式**：如果不是 CI，先检查项目根目录是否存在 `.first_run_done`。
  - 不存在：执行「首次配置向导」。
  - 存在：执行「每日工作流」。

交互式 agent 直接执行本文件即可，不要求用户另配 API Key 或 `AGENT_RUNNER_CMD`。只有 GitHub Actions 等无人值守调度器需要一个可非交互执行的 runner 及其凭据。

任何模式都不要依赖对话历史；一切以当前仓库文件、环境变量和运行时可验证事实为准。

### 0.1 交互语言

- 本地交互默认使用中文，包括首次配置、诊断、部署说明和最终摘要。
- 用户明确要求 English / 英文时，后续交互与操作说明使用英文；不要因此改变命令、路径或安全边界。
- 交互语言不等于速递内容语言。速递正文以 `dispatch.config.json` 的 `content.language` 为准；默认保持中文正文、英文论文题目和专有名词。
- CI / 非交互模式不输出配置向导，只按契约生成文件和日志。

### 0.2 Agent-first 部署原则

本项目的首选部署方式，是让具备文件读取、终端执行和必要联网能力的 agent 读取本文件、`README.md` 与 `dispatch.config.json` 后完成环境检查和引导配置。用户不需要先理解虚拟环境、SMTP、GitHub Actions 或 runner。

当用户说“部署这个项目”“帮我配置”或同等意思时，agent 应：

1. 先运行脱敏体检并检查仓库、Python、`.venv`、`.env` 占位状态和自动化能力，不读取或回显秘密值。
2. 用当前交互语言说明本地按需运行、桌面 agent 原生自动化、GitHub 云端定时三种边界，只展示当前环境真实可用的路线。
3. 默认推荐由 agent 继续执行适合当前环境的步骤；需要路线选择、秘密输入或外部写入授权时再暂停。
4. API Key、邮箱密码或授权码只能由用户在终端隐藏输入、`.env` 或正式 Secrets 界面中填写，禁止要求用户发送到对话中。
5. 未经确认不得开启云端定时、修改 GitHub Secrets/Variables、安装持久自动化或发送测试邮件。

---

## 1. Agent 运行器契约

GitHub Actions 或其他调度器通过 `AGENT_RUNNER_CMD` 调用 agent。该命令必须满足：

- 从项目根目录执行。
- 读取 `AGENTS.md` 和 `dispatch.config.json`。
- 根据当前日期和配置完成采集、筛选、中文摘要和 Markdown 写入。
- 将 UTF-8 Markdown 写到 `DISPATCH_OUTPUT`。
- 链接写入前必须验证可达；不可编造链接。
- 成功时退出码为 `0`；失败时退出非零码。

运行时会注入这些环境变量：

```text
DISPATCH_DATE=YYYY-MM-DD
DISPATCH_OUTPUT=data/YYYY-MM-DD_学术速递.md
DISPATCH_CONFIG=dispatch.config.json
PROJECT_ROOT=<repo root>
DISPATCH_MODE=ci 或 local
```

非交互 agent 在 CI 中只负责生成 Markdown；不要发送邮件、不要改 GitHub secrets、不要把生成内容提交回仓库。

`run_agent_command.py` 只向子进程传递基础系统环境、上述契约变量和 `AGENT_ENV_ALLOWLIST` 允许的 provider 凭据；`SMTP_*` 与 `MAIL_TO` 永远不作为环境变量传入。由于本地 agent 仍可能读取项目目录中的 `.env`，本地只运行可信 agent/命令。

---

## 2. 首次配置向导（仅本地交互模式）

默认中文时，开头第一句话必须说：「zh3zhou向你问问好，体验愉快！」用户已明确要求英文时，第一句话说：「Hello from zh3zhou — enjoy the experience!」

一次问 1-2 个问题，按顺序完成：

1. 优先运行脱敏体检并读取结果，不要凭对话历史猜环境：
   ```powershell
   .\.venv\Scripts\python.exe scripts\project_doctor.py --target manual --json
   ```
   如果 `.venv` 不存在，Windows 运行 `.\setup.ps1`，Linux/macOS 运行 `sh setup.sh`。介绍项目：每天搜集学术论文，穿插艺术和轻松内容，生成 Markdown 与 TTS 音频并通过邮件推送。
2. 读取 `dispatch.config.json` 的 `content.academicFields`，询问是否调整学术领域、关键词和每日条数；需要时直接编辑 JSON 并运行配置校验。
3. 询问艺术方向偏好，更新 `content.art.preferences`。
4. 询问每日运行时间。默认北京时间 07:00。
5. 配置邮箱：引导用户填写 `.env` 中 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`MAIL_TO`。Gmail/QQ 使用应用专用密码或授权码。
6. 可选配置 TTS：更新 `.env` 中 `TTS_VOICE` 和 `TTS_RATE`。
7. 配置自动运行方式。默认推荐继续由当前 agent 协助判断和配置；不要在检查环境前预设 GitHub Actions 一定更合适。用平实语言解释：
   - 首先告诉用户：本项目推荐继续让当前 agent 帮忙完成部署；用户只需要选择运行路线，并在安全位置填写必要凭据。
   - GitHub repo 是“这个项目在 GitHub 上的一份云端副本”；本地 `git remote -v` 可以查看它在哪里。
   - GitHub Actions 是“GitHub 自带的定时任务机器”；它会每天拉取仓库代码运行 workflow。
   - Secrets 是“只给 GitHub Actions 看的密码保险箱”，对应本地 `.env` 里的 SMTP 邮箱配置。
   - Variables 是“普通配置项”，例如 `TTS_VOICE`、`TTS_RATE`、`AGENT_RUNNER_CMD`。
   - `AGENT_RUNNER_CMD` 是“GitHub 到点后调用哪个 agent 来写 Markdown 的命令”；项目不能替用户猜测具体 agent。
   - 在询问 API Key 前，必须给用户两个真实选项：A）复用当前桌面 agent 的原生自动化，不需要显式 API，但依赖本机与应用；B）GitHub 云端定时，需要非交互 runner 和 provider 凭据，电脑关机后仍可运行。
   - 用户选择 A 时，检查当前 runtime 是否提供原生 automation/schedule 能力。支持时先向用户展示时间、工作区和任务内容，再通过 runtime 的正式自动化接口创建；不支持时明确说明，提供手动运行或路线 B。禁止用伪造的后台脚本冒充 agent 自动化。
   - 配置 Codex 以外的 agent 应用时，必须读取 `RUNTIME_ADAPTERS.md`，识别产品和版本，并查询该产品的官方文档或官方仓库；核实定时接口、登录继承、后台条件、联网/文件权限、日志位置和费用后再操作。事实、推断和未知项要分开汇报。
   - 不得把某个产品的 CLI 参数、订阅权益或 API Key 要求类推到另一个产品。官方资料仍无法确认时，保持自动化关闭并给出手动路径。
   - 桌面自动化必须拆成两项：22:20 UTC 的准备任务读取 `AGENTS.md/dispatch.config.json`、完成真实网页检索并运行 finalize，不发邮件；23:00 UTC 的发送任务只运行 deliver。失败时保留结构化日志；不要修改 GitHub 配置或提交生成物。
   - 选择桌面自动化时保持 GitHub `DISPATCH_ENABLED=false`，避免两套定时重复发送。
8. 优先尝试自动化 GitHub 配置诊断：
   - 检查 `git remote -v` 是否有 GitHub repo。
   - 检查是否安装 `gh`。如果没有，告诉用户安装：`winget install --id GitHub.cli`，然后运行 `gh auth login`。
   - 默认先运行 `.\scripts\setup_github_actions.ps1 -CheckOnly`，只读诊断，不写 GitHub。
   - 再运行 `scripts\project_doctor.py --target github-mock --require-email --json`，以 JSON 作为当前状态证据。
   - 向用户汇报诊断结果：remote、GitHub 网络、`gh` 是否安装/登录、workflow 是否已提交、`.env` 是否有 SMTP/TTS、`AGENT_RUNNER_CMD` 是否缺失。
   - 如果用户确认要配置且诊断允许，引导运行 `.\scripts\setup_github_actions.ps1`。该脚本会把 `.env` 中的 `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/MAIL_TO` 写入 GitHub Secrets，把 `TTS_VOICE/TTS_RATE/AGENT_RUNNER_CMD` 写入 Variables，并可触发一次 mock workflow。
   - 如果 `AGENT_RUNNER_CMD` 还没有确定，允许只配置邮件和 TTS，先跑 mock；真实定时运行会等用户选定 agent 命令后再启用。
   - 没有真实 runner 时设置 `DISPATCH_ENABLED=false`。只有 runner 和凭据验证通过后，才允许改为 `true`。
   - 用户要配置真实定时时，优先提供内置 OpenAI 路径，并明确说明 ChatGPT/Codex 登录不等于 API Key、API 单独计费。先运行：
     ```powershell
     .\.venv\Scripts\python.exe scripts\configure_real_schedule.py --check-only
     .\.venv\Scripts\python.exe scripts\configure_real_schedule.py
     ```
   - API Key 必须由用户在终端的隐藏输入中填写，不要求用户发到对话里，不写入 `.env`。向导会先真实试跑且不发邮件，成功后才询问开启定时。
   - 用户选择其他 provider 时，不猜命令：确认其非交互 CLI/API、凭据名称和联网能力，先保持 `DISPATCH_ENABLED=false` 做手动真实试跑，通过后再启用。
   - 如果用户选择暂不配置 GitHub 自动运行，进入「不配置也能用」说明，不要卡住流程。
9. 检查环境：如 `.venv` 不存在，Windows 提示运行 `.\setup.ps1`，Linux/macOS 提示运行 `sh setup.sh`；确保 `data/` 和 `archive/` 存在。
10. 说明手动运行方式：
   ```powershell
   .\scripts\postprocess.ps1 2026-07-04
   .\.venv\Scripts\python.exe scripts\finalize_dispatch.py 2026-07-04
   .\.venv\Scripts\python.exe scripts\deliver_ready.py 2026-07-04
   ```
   Linux/macOS 使用 `.venv/bin/python` 调用同名脚本。
11. 创建 `.first_run_done` 空文件，询问是否立即运行一次。

不要在 CI 模式中创建 `.first_run_done` 或写 `.env`。

---

## 3. 每日工作流

### Step 0：确定日期和输出路径

- 日期：优先用 `DISPATCH_DATE`；否则用用户指定日期；再否则用当天日期。
- 输出：优先用 `DISPATCH_OUTPUT`；否则写入 `data/{YYYY-MM-DD}_学术速递.md`。

### Step 1：读取核心文件

必须读取：

1. `dispatch.config.json`：内容配置、领域、来源、时效、调度与交付规则。
2. `AGENTS.md`：本执行契约。
3. 前一天 `data/{YYYY-MM-DD}_学术速递.md`（如果存在）：提取标题作为去重黑名单。

`RUNTIME_ADAPTERS.md` 只在首次配置、迁移调度器或用户询问其他 agent 应用时读取；每日内容生成无需重复读取。

### Step 2：采集内容

根据 `dispatch.config.json` 的 `content.academicFields`，为每个领域独立采集近 24 小时内的新内容：

- 来源优先级：arXiv、GitHub Trending、Hugging Face、Papers with Code、可信博客/技术报告/项目发布。
- 每个领域按配置挑选最有价值或最有趣的内容。宁缺毋滥。
- 24 小时内不足时可放宽到 48 小时，并在条目标题后标注 `(48h)`。
- 打岔内容：
  - 艺术一刻：默认目标 5 条，可放宽到近期；质量不足时宁缺毋滥，不为凑数降低标准。必须使用 agent 的广域网页搜索，不得用自建爬虫或固定抓取单一站点；目标覆盖至少 3 个相互独立的来源/机构，同一来源最多 2 条。优先轮换可信博物馆、美术馆、艺术节、摄影机构、艺术媒体及艺术家/项目官方页面，避免连续多日依赖 MoMA。
  - 会心一笑：1-2 条，合规、不低俗、不涉敏感话题。

每条学术内容必须包含：

- 英文原题或项目名。
- 已验证可达的来源链接。
- 一句话中文摘要。
- 一句话「为什么值得看」。

### Step 3：写 Markdown

输出必须是 UTF-8，结构如下：

```markdown
# 会打岔的学术速递 — YYYY-MM-DD

> 一句话引言（可俏皮，20字以内）

## 一、{领域1名称}
- **{论文标题}** — {来源}
  摘要：{一句话中文摘要}
  为什么值得看：{一句话理由}
  https://example.com/source

## 二、{领域2名称}
（同上）

## ✦ 今日打岔 ✦

### 艺术一刻
- **{作品/新闻标题}** — {来源}
  简介：{简短中文介绍}
  https://example.com/art

### 会心一笑
- {一段有趣发现/段子/冷知识}
```

要求：

- 学术板块用 `##`，标题名称来自 `dispatch.config.json`。
- 打岔板块标题必须包含「打岔」。
- 艺术和幽默子板块用 `###`。
- 学术/艺术条目以 `- **` 开头。
- 摘要和「为什么值得看」各占一行并缩进。
- 如果某领域确实无亮点，保留该领域标题，并写「今日暂无亮点」。

### Step 4：验证、封存与发送

本地交互模式可运行：

```powershell
.\.venv\Scripts\python.exe scripts\finalize_dispatch.py YYYY-MM-DD
.\.venv\Scripts\python.exe scripts\deliver_ready.py YYYY-MM-DD
```

Linux/macOS 将解释器路径替换为 `.venv/bin/python`；各 Python CLI 也支持 `--root` 从任意工作目录指定项目。

CI 模式由 GitHub Actions 自动运行：

```bash
python scripts/finalize_dispatch.py "$DISPATCH_DATE"
python scripts/deliver_ready.py "$DISPATCH_DATE"
```

### Step 5：日志和摘要

脚本自动向 `data/runs.jsonl` 追加结构化阶段事件。`runs.log` 只读兼容，不再要求 Agent 手工追加。日志禁止记录收件人、密码、Token、邮件正文或绝对本地路径。

会话里只返回摘要，不粘贴全文：

1. 今日共收录 X 篇学术 + Y 条艺术 + Z 则幽默。
2. 每个领域最值得看的一条。
3. 今日打岔亮点。
4. 邮件发送状态。
5. 保存路径。

---

## 4. GitHub Actions 适配

`.github/workflows/prepare-dispatch.yml` 与 `deliver-dispatch.yml` 是默认 CI 调度器：

- prepare：UTC `20 22 * * *`，对应北京时间 06:20；生成、验证、TTS 并上传同日期 ready artifact。
- deliver：UTC `0 23 * * *`，对应北京时间 07:00；通过 GitHub CLI 找到默认分支成功 prepare run，下载同日期 artifact 并复核后发送。
- GitHub schedule 可能因平台排队延迟，不能承诺精确到分钟。
- 手动：`workflow_dispatch` 可指定日期、mock 模式、是否发送邮件。
- `DISPATCH_ENABLED` 不是 `true` 时，schedule 安全跳过；手动 mock 模式仍可运行。
- 开启定时后，如果 `AGENT_RUNNER_CMD` 未配置，生成阶段会失败并提示配置。
- prepare job 不持有 SMTP；deliver job 重新下载并验证产物，SMTP 只进入邮件步骤。
- 生成物作为 Actions artifacts 保存，不提交回仓库。

推荐 GitHub 配置：

- Repository variable 或 secret：`AGENT_RUNNER_CMD`
- Repository variable：`DISPATCH_ENABLED`，没有真实 runner 时保持 `false`
- 可选 Repository variable：`AGENT_ENV_ALLOWLIST`
- Secrets：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`MAIL_TO`
- 可选：`TTS_VOICE`、`TTS_RATE`、agent provider API keys

小白优先使用自动化脚本：

```powershell
.\scripts\setup_github_actions.ps1 -CheckOnly
.\scripts\setup_github_actions.ps1
```

`-CheckOnly` 只诊断，不写 GitHub。正式配置脚本会从 `.env` 搬运 SMTP/TTS 配置，并提示用户补充 `AGENT_RUNNER_CMD`。如果没有安装 `gh`，先指导用户运行 `winget install --id GitHub.cli` 和 `gh auth login`。

已获得用户明确授权时，agent 可使用非交互模式：

```powershell
.\scripts\setup_github_actions.ps1 -NonInteractive -ConfirmWrite -TriggerMock -SendEmailMock
```

缺少 `-ConfirmWrite` 时禁止非交互写入。只有传入真实 runner 并加 `-EnableSchedule` 才开启定时。

如果用户选择不配置 GitHub 自动运行，必须告诉用户仍可这样使用：

1. 直接让 agent 跑一次：
   ```text
   请读取 AGENTS.md 和 dispatch.config.json，运行今天的学术速递并 finalize。
   ```
2. 已有 Markdown 后手动后处理：
   ```powershell
   .\.venv\Scripts\python.exe scripts\finalize_dispatch.py YYYY-MM-DD
   .\.venv\Scripts\python.exe scripts\deliver_ready.py YYYY-MM-DD
   ```
3. 只生成音频不发邮件：
   ```powershell
   .\.venv\Scripts\python.exe scripts\finalize_dispatch.py YYYY-MM-DD
   ```
4. 以后随时再配置 GitHub：
   ```powershell
   .\scripts\setup_github_actions.ps1 -CheckOnly
   .\scripts\setup_github_actions.ps1
   ```

---

## 5. 月度归档

如果本地交互模式运行日期是每月 1 号，在采集前将上个月的 `data/YYYY-MM-*` Markdown、MP3 和朗读稿移动到 `archive/YYYY-MM/`。

CI artifact 模式默认不移动历史内容，因为仓库里的 `data/` 只保留 `.gitkeep`，每日输出保存在 Actions artifacts 中。

---

## 6. 验证清单

- [ ] 已读取 `AGENTS.md` 和 `dispatch.config.json`
- [ ] 日期和输出路径正确
- [ ] 所有配置领域都出现，或注明「今日暂无亮点」
- [ ] 每个学术条目有摘要、为什么值得看、真实链接
- [ ] 打岔板块包含艺术一刻和会心一笑
- [ ] 与前一天标题去重
- [ ] `scripts/finalize_dispatch.py YYYY-MM-DD` 生成可复核的 ready manifest
- [ ] TTS 和邮件结果由脚本或 CI 明确报告
- [ ] 未泄露 `.env`、API key、邮箱授权码或私有生成内容

---

## 7. 为什么这是面向 agent 的项目

- 人类意图在 `dispatch.config.json`：关注领域、偏好、输出、调度和交付约定。
- Agent 契约在 `AGENTS.md`：如何采集、判断、写入、失败。
- 可重复步骤在脚本：验证、TTS、邮件、artifact。
- 证据在输出文件、验证报告、agent log、Actions artifact 和邮件结果。
- 平台适配在外层：GitHub Actions、本机计划任务或任意 agent runtime 都只需遵守同一契约。

---

## 8. 常见问题

**Q：CI 里没有 `.first_run_done` 怎么办？**
A：`DISPATCH_MODE=ci` 时跳过首次向导。

**Q：`AGENT_RUNNER_CMD` 应该写什么？**
A：写你实际使用的 agent CLI 或脚本命令。它只需要读 `AGENTS.md/dispatch.config.json` 并写出 `DISPATCH_OUTPUT`，项目不绑定供应商。

**Q：没有 API Key 能不能用？**
A：交互式 agent 可以直接按本文件手动运行；GitHub 无人值守真生成必须有 runner 和对应凭据。没有 runner 时保持 `DISPATCH_ENABLED=false`，仍可手动 mock。

**Q：ChatGPT Plus/Pro 或 Codex 登录能直接给 GitHub Actions 用吗？**
A：不能。GitHub 云端不继承本机登录。内置 OpenAI runner 需要单独的 OpenAI API Key 和 API 计费；Key 只通过配置向导的隐藏终端输入上传为 GitHub Secret。

**Q：完全不用 API Key，可以定时吗？**
A：如果当前 Codex/agent 应用支持原生自动化，可以复用该应用的登录在本机定时运行；代价是依赖电脑、应用、登录和工作区可用。它不是 GitHub Actions，`DISPATCH_ENABLED` 应保持 `false`。没有原生自动化能力的 agent 只能手动运行或配置云端 runner。

**Q：邮件失败是否会让 CI 失败？**
A：定时任务使用 `--strict-email`，邮件失败会失败；手动 mock 可选择不发送邮件。

**Q：本地 `.venv` 坏了怎么办？**
A：重新安装 Python 后，Windows 运行 `.\setup.ps1`，Linux/macOS 运行 `sh setup.sh`。CI 使用 `actions/setup-python`，不依赖本地 `.venv`。
