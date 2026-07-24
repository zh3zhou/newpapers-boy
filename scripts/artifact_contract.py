#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(path: Path, root: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_ready_manifest(date_str: str, root: Path, artifacts: dict[str, Path], *, max_age_minutes: int, summary: dict, run_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schemaVersion": 1,
        "status": "ready",
        "date": date_str,
        "createdAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": (now + timedelta(minutes=max_age_minutes)).isoformat().replace("+00:00", "Z"),
        "runId": run_id,
        "artifacts": {name: artifact_record(path, root) for name, path in artifacts.items()},
        "summary": summary,
    }


def verify_ready_manifest(path: Path, root: Path, date_str: str, *, now: datetime | None = None) -> tuple[dict | None, list[str]]:
    errors = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"ready manifest unavailable: {type(exc).__name__}"]
    if payload.get("schemaVersion") != 1 or payload.get("status") != "ready":
        errors.append("ready manifest schema or status is invalid")
    if payload.get("date") != date_str:
        errors.append("ready manifest date does not match")
    try:
        expires = datetime.fromisoformat(str(payload.get("expiresAt", "")).replace("Z", "+00:00"))
        if (now or datetime.now(timezone.utc)) > expires:
            errors.append("ready manifest has expired")
    except ValueError:
        errors.append("ready manifest expiresAt is invalid")
    for name, record in payload.get("artifacts", {}).items():
        candidate = (root / str(record.get("path", ""))).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"artifact path escapes project root: {name}")
            continue
        if not candidate.is_file():
            errors.append(f"artifact missing: {name}")
        elif candidate.stat().st_size != record.get("size") or sha256_file(candidate) != record.get("sha256"):
            errors.append(f"artifact integrity mismatch: {name}")
    return payload, errors
