# Changelog

## 2026-07-15

- 将配置表、Markdown 内容模型、日期与工件路径抽成无副作用核心模块，解除 runner/doctor/validator 对 TTS 模块的隐式依赖。
- 为 runner、validator、TTS、邮件和后处理入口增加显式项目根目录及可选工件路径，同时保留全部旧 CLI。
- `run_daily.py` 现在同时识别 Windows 与 Linux/macOS 虚拟环境；新增 `setup.sh` 和模块方式运行支持。
- 新增可移植性回归测试，覆盖任意根目录、配置表隔离、英文标题、日期、模块导入和 Unix venv。

## 2026-07-13

- 将每日速递从 TRAE 专用工作流改造成平台中立的 agent 契约与确定性后处理架构。
- 新增 GitHub Actions 定时、手动 mock、隔离的生成/发送 job 和 artifacts 留证。
- 新增严格 Markdown/链接验证、agent 环境隔离、日志脱敏和 Secret 安全上传。
- 新增 `project_doctor.py`、GitHub 配置向导和“不配置 GitHub 也能用”的首次引导。
- 新增内置 OpenAI Web Search runner，以及真实试跑成功后才启用 schedule 的两阶段向导。
- 新增无显式 API 路线：支持 Codex 等具备原生自动化能力的桌面 agent 复用现有登录。
- 新增跨 agent runtime 的官方文档调查协议；未知产品能力不得靠猜测配置。
- 在 `zh3zhou/newpapers-boy` 完成 GitHub mock、严格验证、TTS、artifact 和邮件端到端验证。
