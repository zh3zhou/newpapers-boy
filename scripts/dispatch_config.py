#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Parse the human-editable academic field table from ``config.md``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FieldSpec:
    name: str
    count_spec: str
    min_items: int | None = None
    max_items: int | None = None
    keywords: str = ""


def parse_count_spec(value: str) -> tuple[int | None, int | None]:
    match = re.search(r"(\d+)\s*-\s*(\d+)", value)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)", value)
    if match:
        count = int(match.group(1))
        return count, count
    return None, None


def _split_table_row(line: str) -> list[str]:
    content = line.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", content)
    return [cell.replace(r"\|", "|").strip() for cell in cells]


def parse_config_fields(config_path: Path) -> list[FieldSpec]:
    """Return fields from the table headed by 领域 and 每日条数.

    Requiring the table header prevents unrelated numbered tables elsewhere in
    a customized config file from being interpreted as academic fields.
    """
    if not config_path.exists():
        return []

    fields: list[FieldSpec] = []
    in_field_table = False
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_field_table and fields:
                break
            continue

        cells = _split_table_row(stripped)
        if "领域" in cells and "每日条数" in cells:
            in_field_table = True
            continue
        if not in_field_table or len(cells) < 4 or "---" in stripped:
            continue
        if not cells[0].isdigit():
            if fields:
                break
            continue

        min_items, max_items = parse_count_spec(cells[3])
        fields.append(
            FieldSpec(
                name=cells[1],
                count_spec=cells[3],
                min_items=min_items,
                max_items=max_items,
                keywords=cells[2],
            )
        )
    return fields
