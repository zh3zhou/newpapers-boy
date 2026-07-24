# v0.1.0 技术报告：可审计的双阶段速递

## 问题

单次 Agent 任务同时检索、生成、TTS 和发信，会把不可预测的网页延迟带进 07:00 发送时刻，也缺少“发出的文件与验证过的文件完全相同”的证据。旧实现还依赖 Markdown 配置和手工 TSV 日志。

## 架构

系统分为编辑平面与交付平面：

1. 编辑平面由可联网 Agent 读取 `AGENTS.md` 和 `dispatch.config.json`，进行广域网页搜索、筛选和写作。
2. `finalize_dispatch.py` 运行严格结构检查、链接分类、历史去重和来源规则，生成 TTS，并为每个 artifact 计算 SHA-256。
3. 原子写入的 `*_ready.json` 记录日期、UTC 时间、过期时间、路径、大小、哈希、内容统计、来源分布、验证摘要和运行 ID。
4. `deliver_ready.py` 在发送前再次校验 manifest，检查 `*_sent.json`，成功后记录本地生成的 Message-ID。
5. 门禁失败时只发送脱敏故障通知，任务仍失败，不回退旧内容。

## 配置与兼容性

`dispatch.config.json` 使用 `schemaVersion=1`。JSON 是机器真源；`config.md` 只解释如何配置。旧领域表格保留一个版本的只读兼容，`migrate_config.py` 可生成新配置。

依赖采用 `requirements.in` 加精确 `requirements.lock.txt`。`pyproject.toml` 声明 Python 3.9+ 与 v0.1.0 元数据。Windows setup 会检测损坏的 `.venv`，将其重命名备份后重建。

## 内容与链接证据

- 相同 URL 或标准化标题在 30 天内是硬错误。
- 艺术默认 5 条，至少 3 个来源/域名，单源最多 2 条。
- 学术来源采用 7 天滚动软目标，不为配额牺牲质量。
- 链接 verdict 为 `reachable`、`bot_blocked`、`dead`、`unsafe` 或 `transient`。
- DNS 解析后连接到已验证公网 IP，并再次阻止重定向到私网。

## 调度与隔离

桌面与 GitHub 都在 22:20 UTC 准备，在 23:00 UTC 交付，对应北京时间 06:20 与 07:00。GitHub prepare workflow 不获得 SMTP；deliver workflow 通过 GitHub CLI 选择默认分支成功的 prepare run，并由 manifest 再次约束日期和哈希。云端 schedule 默认关闭。

## 可观测性

`data/runs.jsonl` 记录运行阶段、状态、错误码、来源域名、哈希和 Message-ID；敏感值和邮件正文不进入日志。`project_doctor.py` 检查配置、锁文件、Python、最近 ready/sent 状态和 GitHub 发布面。

## 证据边界

单元和契约测试覆盖配置、链接、历史、artifact 完整性、重复发送门禁、邮件与 workflow 隔离。一次真实测试邮件证明当前 SMTP 路径可用；它不等于长期 07:00 SLA。长期准点只能由连续生产运行的结构化日志和发送收据证实。
