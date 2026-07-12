# TECH_REPORT.md — 技术架构文档

> 本文档供 AI Agent / 开发者快速理解项目结构、契约边界和扩展点。

## 1. 架构总览

```text
config.md + AGENTS.md
        ↓
任意 agent runtime（由 AGENT_RUNNER_CMD 适配）
        ↓
data/YYYY-MM-DD_学术速递.md
        ↓
scripts/validate_dispatch.py
        ↓
GitHub generate artifact / 本地 data/
        ↓
run_daily.py --skip-email
        ├─ scripts/tts_generate.py → data/YYYY-MM-DD_学术播报.mp3
        └─ scripts/push_email.py --strict → SMTP 邮件
        ↓
GitHub Actions artifacts / 本地 data/
```

核心原则：

- Agent 做语义判断：搜索、筛选、摘要、编辑口吻、链接核验。
- 脚本做确定性工作：环境读取、结构验证、TTS、邮件、退出码。
- 调度器只做编排：GitHub Actions、本机计划任务或其他 agent 平台都可以。

## 2. Agent 运行器契约

`scripts/run_agent_command.py` 是平台适配层。它读取 `AGENT_RUNNER_CMD` 并从项目根目录执行。

注入给 agent 命令的环境变量：

| 变量 | 说明 |
| --- | --- |
| `DISPATCH_DATE` | 目标日期，`YYYY-MM-DD` |
| `DISPATCH_OUTPUT` | Markdown 输出路径 |
| `DISPATCH_CONFIG` | 配置文件，默认 `config.md` |
| `PROJECT_ROOT` | 仓库根目录 |
| `DISPATCH_MODE` | `ci` 或 `local` |

agent 命令必须：

- 读取 `AGENTS.md` 和 `config.md`。
- 写出 UTF-8 Markdown 到 `DISPATCH_OUTPUT`。
- 验证链接可达，不编造来源。
- 成功退出 `0`，失败退出非零。

`--mock` 会生成一份本地 mock Markdown，用于 GitHub Actions 手动烟测。

可靠性与权限边界：

- Agent 写入本次临时路径；脚本验证非空 UTF-8 后原子替换正式输出，旧文件不能冒充成功。
- 默认超时 1800 秒，可用 `AGENT_TIMEOUT_SECONDS` 或 `--timeout` 调整。
- 子进程只获得基础系统环境、契约变量、默认 provider key 和 `AGENT_ENV_ALLOWLIST` 指定项。
- `SMTP_*`、`MAIL_TO` 不传给子进程；agent/provider 输出中的已知秘密值在日志写入前脱敏。
- 本地命令仍能通过文件系统读取 `.env`，因此本地 runner 必须可信；GitHub generate job 中没有本地 `.env`。

## 3. GitHub Actions 编排

`.github/workflows/daily-dispatch.yml`：

- `schedule`: UTC `0 23 * * *`，对应北京时间 07:00。
- `workflow_dispatch`: 支持指定日期、mock 模式、是否发送邮件。
- `DISPATCH_ENABLED=true` 只控制 schedule；手动 workflow 不受影响。
- `generate` job 解析并验证日期，执行 agent/mock、严格结构与链接检查，上传 source evidence。
- `deliver` job fresh checkout，下载并重新验证 source，生成 TTS，再按输入决定是否发送邮件。
- SMTP Secrets 只注入邮件 step，不存在于 generate job 或 agent 子进程环境。
- 两个 job 使用不同 artifact 名，失败时尽量保留已有证据。

必需配置：

- Repository variable 或 secret：`AGENT_RUNNER_CMD`
- Repository variable：`DISPATCH_ENABLED`
- Secrets：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`MAIL_TO`

可选配置：

- `TTS_VOICE`、`TTS_RATE`
- `AGENT_ENV_ALLOWLIST`
- agent provider API keys，如 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`、`HF_TOKEN`

### 3.1 GitHub 配置向导

`scripts/setup_github_actions.ps1` 面向不熟 GitHub 的用户，负责把本地配置搬到 GitHub：

- 从 `git remote get-url origin` 推导 `owner/repo`。
- `-CheckOnly` 只做诊断，不写入 GitHub。
- 检查 GitHub DNS/TCP 可达性。
- 检查 GitHub CLI `gh` 是否安装、是否登录。
- 检查 workflow 是否存在、是否被 Git 跟踪，以及当前是否有未提交改动。
- 从 `.env` 读取 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`、`MAIL_TO`。
- 将 SMTP 项写入 GitHub Actions Secrets。
- 将 `TTS_VOICE`、`TTS_RATE`、`AGENT_RUNNER_CMD` 写入 GitHub Actions Variables。
- 没有真实 runner 时写入 `DISPATCH_ENABLED=false`；只有 `-EnableSchedule` 才写入 `true`。
- 可选触发一次 `daily-dispatch.yml` 的 mock workflow。
- 非交互写入必须同时使用 `-NonInteractive -ConfirmWrite`，可用 `-SendEmailMock` 测试邮件。

该脚本不会提交代码、不会 push、不会替用户创建真实 agent 命令。workflow 必须先提交并 push 到 GitHub，Actions 页面才会出现；如果用户暂不配置 GitHub，仍可按 `AGENTS.md` 让 agent 手动执行，或对已有 Markdown 运行 `run_daily.py`。

## 4. 配置体系

| 文件/来源 | 用途 | 是否入库 |
| --- | --- | --- |
| `config.md` | 内容偏好：领域、关键词、条数、来源、路径、艺术方向 | 是 |
| `AGENTS.md` | agent 执行契约：采集、输出、失败、CI 行为 | 是 |
| `.env.example` | 本地/CI 环境变量模板 | 是 |
| `.env` | 本地密钥：SMTP、TTS、agent 命令 | 否 |
| GitHub secrets/vars | CI 密钥和运行配置 | 否 |

`scripts/env_utils.py` 会先读 `.env`，再用进程环境覆盖。这保证本地文件方便调试，CI secrets 拥有更高优先级。

`scripts/project_doctor.py` 提供三种脱敏 readiness：

- `manual`：Python 3.9+ 真探针、依赖、配置和本地目录；可选要求邮箱。
- `github-mock`：Git/gh、workflow 已发布、可选要求远端 SMTP Secret 名称。
- `github-scheduled`：在 mock 条件上要求 SMTP、`DISPATCH_ENABLED=true` 和 runner Variable/Secret。

输出支持人类文本和 `--json`。JSON 只包含状态、名称和下一步，不包含 `.env` 或 GitHub Secret 值。

## 5. Markdown 契约

生成端必须输出：

```markdown
# 会打岔的学术速递 — YYYY-MM-DD

> 引言

## 一、领域名称
- **标题** — 来源
  摘要：一句话摘要。
  为什么值得看：一句话理由。
  https://example.com/source

## ✦ 今日打岔 ✦

### 艺术一刻
- **作品标题** — 来源
  简介：一句话介绍。
  https://example.com/art

### 会心一笑
- 趣味内容。
```

关键点：

- 一级标题包含日期。
- 每个 `config.md` 学术领域都要出现。
- 学术条目以 `- **` 开头。
- 学术条目必须包含摘要、为什么值得看、URL。
- 打岔板块标题必须包含「打岔」。
- 艺术和幽默分别用三级标题。

## 6. Validator

`scripts/validate_dispatch.py` 做确定性契约验证：

- 日期格式和标题日期。
- UTF-8、非空文件。
- `config.md` 中配置的领域是否都存在。
- 每个学术条目的摘要、理由、URL 是否存在。
- 打岔、艺术、幽默结构是否存在。
- TTS parser 是否能解析日期、学术区块、艺术和幽默。
- 生成 JSON 报告到 `data/YYYY-MM-DD_validation.json`。
- `--check-links` 对 URL 去重后执行 HEAD/GET 检查并记录每条结果。
- 404/410 等明确永久错误失败；403、429、5xx、超时和临时 DNS 故障记为 warning。
- 请求前及重定向时拒绝 localhost、私网、link-local、保留地址和 URL 内嵌凭据，降低 SSRF 风险。

注意：配置中的 `3-5` 是偏好，不是硬性失败条件。低于配置数量会记录 warning，因为项目允许「宁缺毋滥」和「今日暂无亮点」。

## 7. TTS 模块

`scripts/tts_generate.py`：

- 从 Markdown 二级标题动态解析学术领域，不硬编码字段名。
- 用状态机识别打岔、艺术、幽默。
- `edge_tts` 懒加载，便于测试 parser 时不安装 TTS 依赖。
- 输出：
  - `data/YYYY-MM-DD_学术播报.mp3`
  - `data/YYYY-MM-DD_播报稿.txt`

可修改点：

- 语音：`.env` / CI vars 中的 `TTS_VOICE`
- 语速：`TTS_RATE`
- 播报文案：`build_broadcast_text()`
- 截断长度：`smart_truncate()` 调用参数

## 8. 邮件模块

`scripts/push_email.py`：

- SMTP SSL 465 或 STARTTLS。
- Markdown 轻量转 HTML。
- MP3 作为附件发送。
- 默认本地模式：邮件未配置或失败时返回 `0`，方便只生成音频。
- strict/CI 模式：`--strict` 或 `DISPATCH_MODE=ci` 时，邮件失败返回非零。

## 9. 后处理入口

`run_daily.py`：

- 检查 `data/YYYY-MM-DD_学术速递.md` 是否存在。
- 调用 `tts_generate.py`。
- 调用 `push_email.py`。
- 支持：
  - `--skip-email`
  - `--strict-email`

它会优先使用可用的 `.venv\Scripts\python.exe`。如果本地虚拟环境已损坏，会回退到当前 Python 并打印 warning。GitHub Actions 不依赖本地 `.venv`。

## 10. 测试

使用标准库 `unittest`：

```bash
python -m unittest discover -s tests
```

覆盖点：

- Markdown parser 支持可配置领域和打岔板块。
- 环境变量覆盖 `.env`。
- validator 接受有效 Markdown。
- validator 拒绝缺失输出、缺失配置字段、缺失 URL。
- doctor 三种 target、Secret 脱敏和 manual 不触发 GitHub 探针。
- fake agent 成功、失败、缺输出、旧输出、空文件、非 UTF-8、日志脱敏和 SMTP 环境隔离。
- 链接永久失败、限流/临时失败和私网地址分类。

手动验证：

```bash
python scripts/run_agent_command.py 2026-07-04 --mock
python scripts/validate_dispatch.py 2026-07-04 --strict --check-links
python run_daily.py 2026-07-04 --skip-email
```

## 11. 扩展点

### 接入新 Agent

不要改核心脚本；配置 `AGENT_RUNNER_CMD` 即可。若某 agent 需要复杂适配，新增一个脚本，例如：

```text
scripts/my_agent_adapter.py
```

然后设置：

```text
AGENT_RUNNER_CMD=python scripts/my_agent_adapter.py
```

适配脚本只需遵守 `DISPATCH_*` 环境变量和输出契约。

### 添加推送通道

在 `scripts/push_email.py` 中添加 `push_xxx(...) -> bool`，并在 `main()` 中按需调用。保持 strict 模式的退出码语义。

### 添加 TTS 引擎

新增 `scripts/tts_xxx.py`，保持 CLI 接口 `python scripts/tts_xxx.py YYYY-MM-DD`，或在 `tts_generate.py` 内抽象 `synthesize()`。

## 12. 风险边界

- 不提交 `.env`、`data/`、`archive/`。
- 不把每日输出提交回仓库；GitHub Actions 使用 artifacts。
- 不在文档中写入真实 API key 或邮箱授权码。
- `--check-links` 会访问生成内容中的公开 URL；私网和本机地址被拒绝，临时外部故障只记 warning。
- GitHub generate job 不持有 SMTP Secrets；deliver 在 fresh checkout 后才取得邮件配置。
- 没有真实 runner 时 `DISPATCH_ENABLED=false`，避免每天制造预期失败。
