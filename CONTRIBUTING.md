# Contributing

Please open an issue before large behavioral or workflow changes. Keep the agent-facing editorial contract separate from deterministic validation and delivery code.

## Development

```powershell
.\setup.ps1
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
```

Changes to configuration require Schema and precedence tests. Delivery changes require failure, integrity, and idempotency tests. Workflow changes must preserve the rule that prepare has no SMTP credentials.

Do not commit `.env`, `data/` outputs, audio, receipts, or personal logs. Keep pull requests focused and describe validation evidence and known limits.
