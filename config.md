# 配置指南（兼容入口）

机器配置的唯一真源是 [`dispatch.config.json`](dispatch.config.json)，并由
[`dispatch.config.schema.json`](dispatch.config.schema.json) 描述。不要再把本文件中的说明当作运行时配置。

## 常用修改

- `content.academicFields`：领域、关键词和每日条数范围。
- `content.art`：默认目标 5 条，至少 3 个独立来源，单源最多 2 条。
- `content.academicSources`：Agent 应轮换检索的高质量来源；这是质量优先的软目标。
- `schedule`：北京时间 06:20 准备、07:00 发送；`readyMaxAgeMinutes` 默认 60。
- `tts`：语音与语速。CLI 和环境变量可在单次运行中覆盖。
- `history`：30 天硬去重与 7 天来源集中告警窗口。

验证：

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py
```

旧版本自定义 Markdown 表格可用以下命令迁移：

```powershell
.\.venv\Scripts\python.exe scripts\migrate_config.py
```

迁移器默认不会覆盖已存在的 JSON。旧 Markdown 表格解析只保留到下一个不兼容版本。

## 秘密与运行覆盖

SMTP 密码、收件人和 provider key 不属于 JSON。它们只应放在未跟踪的 `.env` 或 GitHub Secrets 中。

覆盖优先级：

1. CLI 参数，例如 `--voice`、`--rate`、`--force`。
2. 允许的运行环境变量，例如 `TTS_VOICE`、`TTS_RATE`、`DISPATCH_DATE`。
3. `dispatch.config.json`。
4. 代码中的安全默认值。

完整字段说明见 [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)。
