# The Academic Dispatch That Likes a Detour

[中文（默认）](README.md) · **English**

This project collects recent academic work, adds a small art and humor detour, and produces a Markdown digest, Chinese TTS audio, and an optional email. Agents handle research and editing; deterministic scripts handle validation, link checks, TTS, email, and run evidence.

## Recommended: ask an agent to deploy it

The easiest and safest setup path is to open this repository in an agent that can read files and run terminal commands, then say:

```text
Read AGENTS.md, README.md, and config.md, then help me deploy this project. Continue in English. Inspect the current environment first, explain the local and scheduled options, and configure the option that fits this environment. Do not ask me to paste passwords or API keys into chat, and do not enable cloud schedules or change GitHub settings without confirmation.
```

The agent will inspect Python, the virtual environment, email/TTS settings, GitHub state, and available automation features. It must pause when you need to choose a deployment route or enter a secret. Chinese is the default interaction language; English is available when requested. Dispatch content still follows the language setting in `config.md`.

To generate one dispatch immediately, ask:

```text
Read AGENTS.md and config.md, then run today's academic dispatch. Continue in English.
```

## Manual installation (optional)

Windows PowerShell:

```powershell
git clone <your-repo-url>
cd <repo-dir>
.\setup.ps1
```

Linux or macOS:

```bash
git clone <your-repo-url>
cd <repo-dir>
sh setup.sh
```

Local configuration is stored in the untracked `.env` file. Never commit SMTP passwords or API keys. The main commands are:

```powershell
.\.venv\Scripts\python.exe scripts\project_doctor.py --target manual
.\.venv\Scripts\python.exe scripts\validate_dispatch.py YYYY-MM-DD --strict --check-links
.\.venv\Scripts\python.exe run_daily.py YYYY-MM-DD
```

On Linux/macOS, use `.venv/bin/python` instead. For detailed configuration, automation, GitHub Actions, privacy rules, and the repository layout, see the default [Chinese README](README.md); the executable agent contract is [AGENTS.md](AGENTS.md).

## Deployment choices

| Route | Runs on | Explicit API key | Best for |
| --- | --- | --- | --- |
| Interactive agent | Your current agent session | Usually no | Setup, testing, and on-demand dispatches |
| Desktop-agent automation | Your computer | Usually no | Scheduled personal use when the app supports native automation |
| GitHub Actions + provider API | GitHub | Yes | Cloud scheduling that continues while your computer is off |

GitHub cannot inherit a local Codex or desktop-agent login. Keep `DISPATCH_ENABLED=false` until a real non-interactive runner and its credentials have passed a test run.

## License

MIT
