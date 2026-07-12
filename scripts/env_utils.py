#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared environment loading for local runs and CI.

Values from the process environment override `.env`, which lets GitHub Actions
secrets replace local placeholder values without editing files.
"""

from __future__ import annotations

import os
from pathlib import Path


def parse_env_file(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def load_env(work_dir: Path) -> dict[str, str]:
    env = parse_env_file(work_dir / ".env")
    for key, value in os.environ.items():
        env[key] = value
    return env
