#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .artifact_contract import atomic_write_json
    from .dispatch_config import _parse_markdown_fields, validate_config_data
except ImportError:
    from artifact_contract import atomic_write_json
    from dispatch_config import _parse_markdown_fields, validate_config_data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Migrate the legacy config.md field table to schemaVersion 1 JSON.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--force", action="store_true", help="Replace an existing dispatch.config.json.")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    source = root / "config.md"
    target = root / "dispatch.config.json"
    if target.exists() and not args.force:
        print(f"[ERROR] {target.name} already exists; use --force only after reviewing the migration.", file=sys.stderr)
        return 2
    fields = _parse_markdown_fields(source)
    if not fields:
        print("[ERROR] no legacy academic field table found", file=sys.stderr)
        return 2
    payload = {
        "$schema": "./dispatch.config.schema.json",
        "schemaVersion": 1,
        "content": {
            "academicFields": [
                {
                    "name": field.name,
                    "keywords": [part.strip() for part in field.keywords.split("/") if part.strip()],
                    "items": {"min": field.min_items or 0, "max": field.max_items or field.min_items or 1},
                }
                for field in fields
            ],
            "academicSources": {
                "preferred": ["arXiv", "GitHub", "Hugging Face", "Papers with Code", "official release"],
                "rollingWindowDays": 7,
                "minimumDistinctDomains": 2,
                "enforcement": "warning",
            },
            "art": {
                "targetItems": 5,
                "minimumDistinctSources": 3,
                "maximumItemsPerSource": 2,
                "preferences": [],
            },
            "humor": {"minItems": 1, "maxItems": 2},
            "freshness": {"defaultHours": 24, "fallbackHours": 48, "artAndHumor": "recent"},
            "language": "zh-CN",
        },
        "schedule": {
            "timezone": "Asia/Shanghai",
            "prepareAt": "06:20",
            "deliverAt": "07:00",
            "readyMaxAgeMinutes": 60,
        },
        "delivery": {"channel": "smtp", "failurePolicy": "notify", "preventDuplicateSend": True},
        "tts": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%"},
        "history": {"duplicateWindowDays": 30, "diversityWindowDays": 7},
    }
    errors = validate_config_data(payload)
    if errors:
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False), file=sys.stderr)
        return 2
    atomic_write_json(target, payload)
    print(f"[OK] migrated {source.name} to {target.name}; review before use")
    return 0


if __name__ == "__main__":
    sys.exit(main())
