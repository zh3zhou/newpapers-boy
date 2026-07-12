#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "success"
    output = Path(os.environ["DISPATCH_OUTPUT"])
    observed = os.environ.get("FAKE_OBSERVED_ENV")
    if observed:
        Path(observed).write_text(
            json.dumps(
                {
                    "smtp_present": "SMTP_PASS" in os.environ,
                    "mail_present": "MAIL_TO" in os.environ,
                    "provider_present": os.environ.get("OPENAI_API_KEY") == "provider-secret",
                    "date": os.environ.get("DISPATCH_DATE"),
                    "config": os.environ.get("DISPATCH_CONFIG"),
                    "mode": os.environ.get("DISPATCH_MODE"),
                    "project_root": os.environ.get("PROJECT_ROOT"),
                    "cwd": str(Path.cwd()),
                    "output": os.environ.get("DISPATCH_OUTPUT"),
                }
            ),
            encoding="utf-8",
        )

    if mode == "fail":
        print("fake agent failed")
        return 7
    if mode == "missing":
        return 0
    if mode == "invalid":
        output.write_bytes(b"\xff\xfe\x00")
        return 0
    if mode == "empty":
        output.write_text("   \n", encoding="utf-8")
        return 0
    if mode == "leak":
        print(f"provider={os.environ.get('OPENAI_API_KEY', '')}")

    output.write_text("# fake agent output\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
