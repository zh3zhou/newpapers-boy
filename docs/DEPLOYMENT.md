# Deployment

## Desktop production route

Use two Codex desktop automations with explicit UTC schedules:

- `22:20 UTC`: read the agent contract and JSON config, generate today's dispatch, then run `finalize_dispatch.py`. Never send.
- `23:00 UTC`: run only `deliver_ready.py` for today's China Standard Time date.

The computer, Codex app, login, workspace, network, and SMTP configuration must be available. Desktop automation is the current production route.

## GitHub route

`prepare-dispatch.yml` and `deliver-dispatch.yml` implement the same split. Keep repository variable `DISPATCH_ENABLED=false` until a non-interactive agent runner and provider credentials have passed a real prepare test.

Required delivery Secrets:

`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_TO`.

Optional Variables:

`AGENT_RUNNER_CMD`, `AGENT_ENV_ALLOWLIST`, `TTS_VOICE`, `TTS_RATE`, `OPENAI_MODEL`.

Prepare receives provider credentials but no SMTP values. Deliver finds a successful prepare run on the default branch, downloads the date-named artifact, and lets the ready manifest enforce date and integrity. A missing artifact still enters `deliver_ready.py`, which sends a short failure notice and exits nonzero.

Run the read-only diagnosis before changing GitHub settings:

```powershell
.\scripts\setup_github_actions.ps1 -CheckOnly
.\.venv\Scripts\python.exe scripts\project_doctor.py --target github-mock --require-email --json
```
