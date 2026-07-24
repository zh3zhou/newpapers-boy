# Operations

## Manual prepare

After an agent writes `data/YYYY-MM-DD_学术速递.md`:

```powershell
.\.venv\Scripts\python.exe scripts\finalize_dispatch.py YYYY-MM-DD
```

Successful output includes Markdown, MP3, transcript, validation report, and `*_ready.json`.

## Manual delivery

```powershell
.\.venv\Scripts\python.exe scripts\deliver_ready.py YYYY-MM-DD
```

The command rejects stale, missing, date-mismatched, modified, or already-sent artifacts. `--force` is reserved for an intentional resend. Use `--dry-run` for a non-sending gate check and `--test-label` for a clearly marked delivery test.

## Evidence

- `data/runs.jsonl`: structured phase events.
- `data/content-history.jsonl`: ignored local deduplication and diversity history.
- `data/*_validation.json`: link verdicts, source distribution, and history findings.
- `data/*_ready.json`: immutable artifact contract.
- `data/*_sent.json`: delivery receipt and Message-ID.

These files are operational data and are not committed.

## Failure handling

Do not copy or rename yesterday's dispatch into today's date. Fix the current prepare failure, create a fresh ready manifest, and allow delivery only while it is within the configured age. Failure notifications must not include secrets, absolute local paths, or attachments.

Use:

```powershell
.\.venv\Scripts\python.exe scripts\project_doctor.py --target manual --json
```

Production punctuality is evaluated from consecutive `scheduled`, `prepare_started`, `ready`, `delivery_started`, and `sent/failed` events—not from repository tests alone.
