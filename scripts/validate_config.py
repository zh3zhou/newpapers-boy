#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .dispatch_config import load_dispatch_config
    from .dispatch_paths import ProjectPaths
except ImportError:
    from dispatch_config import load_dispatch_config
    from dispatch_paths import ProjectPaths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate dispatch.config.json.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    project = ProjectPaths.from_root(args.root)
    try:
        config = load_dispatch_config(project.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.as_json:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        else:
            print(f"[ERROR] {exc}")
        return 2
    payload = {"status": "ok", "source": str(config.source), "legacy": config.legacy, "fields": len(config.fields)}
    print(json.dumps(payload, ensure_ascii=False) if args.as_json else f"[OK] {len(config.fields)} fields from {config.source.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
