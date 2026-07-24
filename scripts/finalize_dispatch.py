#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    from .artifact_contract import atomic_write_json, build_ready_manifest
    from .content_history import append_history, extract_content_entries
    from .dispatch_config import load_dispatch_config
    from .dispatch_paths import ProjectPaths, resolve_dispatch_date
    from .run_events import append_event
    from .validate_dispatch import validate_dispatch
except ImportError:
    from artifact_contract import atomic_write_json, build_ready_manifest
    from content_history import append_history, extract_content_entries
    from dispatch_config import load_dispatch_config
    from dispatch_paths import ProjectPaths, resolve_dispatch_date
    from run_events import append_event
    from validate_dispatch import validate_dispatch


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate, synthesize, and seal a dispatch as a ready artifact.")
    parser.add_argument("date", nargs="?")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--skip-links", action="store_true", help="Skip network link checks (tests/offline only).")
    parser.add_argument("--skip-tts", action="store_true", help="Reuse existing audio/transcript files.")
    args = parser.parse_args(argv)
    project = ProjectPaths.from_root(args.root)
    try:
        date_str = resolve_dispatch_date(args.date)
        config = load_dispatch_config(project.config)
    except ValueError as exc:
        parser.error(str(exc))
    artifacts = project.artifacts(date_str)
    events = project.data / "runs.jsonl"
    run_id = os.environ.get("GITHUB_RUN_ID") or str(uuid.uuid4())
    append_event(events, date_str, "prepare_started", "running", runId=run_id)
    started = time.monotonic()
    report = validate_dispatch(
        date_str,
        artifacts.markdown,
        project.config,
        strict=True,
        check_links=not args.skip_links,
        history_path=project.data / "content-history.jsonl",
    )
    atomic_write_json(artifacts.validation, report)
    if report["errors"]:
        append_event(
            events, date_str, "validation_finished", "failed", runId=run_id,
            errors=report["errors"], durationMs=round((time.monotonic() - started) * 1000),
        )
        for error in report["errors"]:
            print(f"[ERROR] {error}")
        return 2
    append_event(
        events,
        date_str,
        "validation_finished",
        "ok",
        runId=run_id,
        warnings=len(report["warnings"]),
        sourceDomains=report["sourceDomains"],
    )
    if not args.skip_tts:
        result = subprocess.run(
            [sys.executable, str(project.scripts / "tts_generate.py"), date_str, "--root", str(project.root)],
            cwd=project.root,
        )
        if result.returncode:
            append_event(events, date_str, "tts_finished", "failed", runId=run_id)
            return result.returncode
    if not artifacts.audio.is_file() or not artifacts.transcript.is_file():
        append_event(events, date_str, "tts_finished", "failed", runId=run_id, errorCode="missing_tts_artifact")
        print("[ERROR] TTS artifacts are missing.")
        return 3
    append_event(events, date_str, "tts_finished", "ok", runId=run_id)
    manifest = build_ready_manifest(
        date_str,
        project.root,
        {
            "markdown": artifacts.markdown,
            "audio": artifacts.audio,
            "transcript": artifacts.transcript,
            "validation": artifacts.validation,
        },
        max_age_minutes=int(config.schedule.get("readyMaxAgeMinutes", 60)),
        summary={
            "sections": report["sections"],
            "arts": report["arts"],
            "humors": report["humors"],
            "sourceDomains": report["sourceDomains"],
            "warnings": report["warnings"],
        },
        run_id=run_id,
    )
    atomic_write_json(artifacts.ready, manifest)
    entries = extract_content_entries(artifacts.markdown.read_text(encoding="utf-8"), date_str)
    append_history(project.data / "content-history.jsonl", entries)
    append_event(
        events,
        date_str,
        "ready",
        "ok",
        runId=run_id,
        ready=artifacts.ready.name,
        artifactHashes={name: item["sha256"] for name, item in manifest["artifacts"].items()},
        durationMs=round((time.monotonic() - started) * 1000),
    )
    print(f"[OK] Ready artifact: {artifacts.ready}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
