#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from .artifact_contract import atomic_write_json, verify_ready_manifest
    from .dispatch_paths import ProjectPaths, resolve_dispatch_date
    from .env_utils import load_env
    from .push_email import build_summary, push_email, push_failure_email
    from .run_events import append_event, utc_now
except ImportError:
    from artifact_contract import atomic_write_json, verify_ready_manifest
    from dispatch_paths import ProjectPaths, resolve_dispatch_date
    from env_utils import load_env
    from push_email import build_summary, push_email, push_failure_email
    from run_events import append_event, utc_now


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Deliver a sealed ready artifact exactly once.")
    parser.add_argument("date", nargs="?")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--force", action="store_true", help="Allow an intentional resend.")
    parser.add_argument("--dry-run", action="store_true", help="Verify without sending or writing a sent receipt.")
    parser.add_argument("--test-label", action="store_true", help="Mark the email subject as a delivery test.")
    parser.add_argument("--no-failure-notification", action="store_true")
    args = parser.parse_args(argv)
    project = ProjectPaths.from_root(args.root)
    try:
        date_str = resolve_dispatch_date(args.date)
    except ValueError as exc:
        parser.error(str(exc))
    artifacts = project.artifacts(date_str)
    receipt_path = project.data / f"{date_str}_test_sent.json" if args.test_label else artifacts.sent
    events = project.data / "runs.jsonl"
    append_event(events, date_str, "delivery_started", "running")
    started = time.monotonic()
    manifest, errors = verify_ready_manifest(artifacts.ready, project.root, date_str)
    if receipt_path.exists() and not args.force:
        errors.append("sent receipt already exists")
    if errors:
        error_code = "ready_gate_failed"
        append_event(
            events, date_str, "delivery_finished", "failed", errorCode=error_code,
            errors=errors, durationMs=round((time.monotonic() - started) * 1000),
        )
        if not args.no_failure_notification and not args.dry_run:
            result = {}
            push_failure_email(load_env(project.root), date_str, error_code, "; ".join(errors), result=result)
            append_event(events, date_str, "failure_notification", result.get("status", "failed"), messageId=result.get("messageId"))
        for error in errors:
            print(f"[ERROR] {error}")
        return 2
    if args.dry_run:
        print(f"[OK] Ready artifact verified: {artifacts.ready}")
        return 0
    title, summary = build_summary(artifacts.markdown)
    if args.test_label:
        title = f"[TEST] {title}"
    result = {}
    success = push_email(
        load_env(project.root),
        f"📰 {title}",
        summary or f"{date_str} 的学术速递已生成。",
        artifacts.markdown,
        artifacts.audio,
        result=result,
    )
    if not success:
        append_event(events, date_str, "delivery_finished", "failed", errorCode="smtp_send_failed")
        return 3
    receipt = {
        "schemaVersion": 1,
        "status": "sent",
        "date": date_str,
        "sentAt": utc_now(),
        "messageId": result.get("messageId"),
        "readyRunId": manifest.get("runId"),
        "artifactHashes": {name: item["sha256"] for name, item in manifest["artifacts"].items()},
        "test": args.test_label,
    }
    atomic_write_json(receipt_path, receipt)
    append_event(
        events,
        date_str,
        "delivery_finished",
        "sent",
        messageId=receipt["messageId"],
        test=args.test_label,
        durationMs=round((time.monotonic() - started) * 1000),
    )
    print(f"[OK] Sent receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
