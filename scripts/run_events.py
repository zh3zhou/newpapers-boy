#!/usr/bin/env python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_event(path: Path, date_str: str, stage: str, status: str, **details) -> dict:
    event = {
        "schemaVersion": 1,
        "timestamp": utc_now(),
        "date": date_str,
        "stage": stage,
        "status": status,
    }
    event.update({key: value for key, value in details.items() if value is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event
