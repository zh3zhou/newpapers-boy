# Changelog

## 2026-07-13

- 将每日速递从 TRAE 专用工作流改造成平台中立的 agent 契约与确定性后处理架构。
- 新增 GitHub Actions 定时、手动 mock、隔离的生成/发送 job 和 artifacts 留证。
- 新增严格 Markdown/链接验证、agent 环境隔离、日志脱敏和 Secret 安全上传。
- 新增 `project_doctor.py`、GitHub 配置向导和“不配置 GitHub 也能用”的首次引导。
- 新增内置 OpenAI Web Search runner，以及真实试跑成功后才启用 schedule 的两阶段向导。
- 新增无显式 API 路线：支持 Codex 等具备原生自动化能力的桌面 agent 复用现有登录。
- 新增跨 agent runtime 的官方文档调查协议；未知产品能力不得靠猜测配置。
- 在 `zh3zhou/newpapers-boy` 完成 GitHub mock、严格验证、TTS、artifact 和邮件端到端验证。
