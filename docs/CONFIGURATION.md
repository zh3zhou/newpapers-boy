# Configuration

`dispatch.config.json` is the canonical machine configuration and uses `schemaVersion: 1`.

## Sections

- `content.academicFields`: field name, search keywords, and per-day min/max.
- `content.academicSources`: preferred web-search surfaces and rolling diversity warning.
- `content.art`: target 5, minimum 3 distinct sources, maximum 2 items per source.
- `content.freshness`: 24-hour primary and 48-hour marked fallback.
- `schedule`: `Asia/Shanghai`, prepare `06:20`, deliver `07:00`, and ready maximum age.
- `delivery`: SMTP, failure notification, and duplicate-send prevention.
- `tts`: default voice and rate.
- `history`: 30-day duplicate and 7-day diversity windows.

Secrets never belong in JSON. Use `.env` locally and GitHub Secrets remotely.

Validate with:

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py --json
```

To migrate an old Markdown field table, temporarily remove or rename the existing JSON and run:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_config.py
```

The effective override order is CLI, approved environment variables, JSON, then safe defaults. The legacy Markdown reader is read-only compatibility for one release.
