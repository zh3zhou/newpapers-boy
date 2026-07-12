# Agent Runtime 适配指南

本项目不假设用户一定使用 Codex、TRAE 或某个固定 provider。首次配置自动运行时，当前 agent 必须先识别自身运行时，再查阅该产品的官方文档和本机可验证状态。

## 调查顺序

1. 识别产品、版本和运行表面：桌面应用、IDE 插件、CLI、网页 agent 或云端 runner。
2. 优先检查当前会话暴露的正式工具，例如 automation、schedule、task、workflow 或 cron；不要根据产品名称猜能力。
3. 若能力或参数可能变化，查询该产品的官方文档。技术接口只使用官方文档、官方仓库或本机 `--help` 作为依据。
4. 核实登录能否用于后台任务：区分桌面订阅登录、CLI 登录、API Key、OAuth、GitHub App 和云端 Secret。
5. 核实运行条件：电脑是否必须开机、应用是否必须运行、任务能否联网、能否访问当前工作区、失败后在哪里查看日志。
6. 核实非交互契约：如何传入日期、工作区、提示词和输出路径，失败是否返回非零状态。
7. 向用户用平实语言汇报已确认事实、仍未知项、费用和可靠性边界，再请求创建或写入凭据的授权。

## 路线选择

| 已确认能力 | 采用路线 | 项目设置 |
| --- | --- | --- |
| 当前 agent 有原生定时/自动化，可复用现有登录 | 桌面 agent 自动化 | GitHub `DISPATCH_ENABLED=false` |
| 有可非交互 CLI/API 和独立凭据 | GitHub Actions 或其他 CI | 先真实试跑，通过后再启用 schedule |
| 只有交互式运行，没有原生定时 | 手动让 agent 跑一次 | 不创建伪后台任务 |
| 能力或授权方式无法从官方资料确认 | 暂不自动配置 | 保持现状并说明待确认项 |

## 桌面自动化任务契约

自动化提示词至少应包含：

```text
从项目根目录读取 AGENTS.md 和 config.md，运行当天的真实学术速递。
完成采集和 Markdown 后执行严格验证、TTS 和邮件。
不要运行 mock，不要修改 GitHub 配置，不要提交生成物。
失败时保留日志并明确报告失败步骤。
```

创建前必须向用户展示：任务名称、时区和时间、工作区、是否发送邮件、依赖本机还是云端。若另一套定时已经启用，先请求用户选择保留哪一套，避免重复邮件。

## CI / CLI 适配契约

非交互 runner 必须遵守 `AGENTS.md` 的 `AGENT_RUNNER_CMD` 契约，接收 `DISPATCH_DATE`、`DISPATCH_OUTPUT`、`DISPATCH_CONFIG`、`PROJECT_ROOT` 和 `DISPATCH_MODE`。必须先在 schedule 关闭状态下运行一次真实生成和严格验证；只有成功后才能开启定时。

凭据只放在运行平台的 Secret 存储中。不要要求用户把 API Key、OAuth token 或邮箱授权码发到聊天里，也不要把它们写进 README、命令参数、Git 历史或 artifact。

## 无法自动配置时

明确告诉用户仍可在项目中说：

```text
请读取 AGENTS.md 和 config.md，运行今天的学术速递。
```

也可以对已有 Markdown 执行：

```powershell
.\.venv\Scripts\python.exe scripts\validate_dispatch.py YYYY-MM-DD --strict --check-links
.\.venv\Scripts\python.exe run_daily.py YYYY-MM-DD
```
