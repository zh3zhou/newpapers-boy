#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Load the versioned JSON config with one-release Markdown compatibility."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FieldSpec:
    name: str
    count_spec: str
    min_items: int | None = None
    max_items: int | None = None
    keywords: str = ""


@dataclass(frozen=True)
class DispatchConfig:
    raw: dict
    source: Path
    legacy: bool = False

    @property
    def fields(self) -> list[FieldSpec]:
        result = []
        for item in self.raw.get("content", {}).get("academicFields", []):
            counts = item.get("items", {})
            minimum = counts.get("min")
            maximum = counts.get("max")
            count_spec = str(minimum) if minimum == maximum else f"{minimum}-{maximum}"
            result.append(
                FieldSpec(
                    name=str(item.get("name", "")).strip(),
                    count_spec=count_spec,
                    min_items=minimum,
                    max_items=maximum,
                    keywords=" / ".join(item.get("keywords", [])),
                )
            )
        return [field for field in result if field.name]

    @property
    def art(self) -> dict:
        return self.raw.get("content", {}).get("art", {})

    @property
    def schedule(self) -> dict:
        return self.raw.get("schedule", {})


def validate_config_data(data: dict) -> list[str]:
    errors = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    fields = data.get("content", {}).get("academicFields")
    if not isinstance(fields, list) or not fields:
        errors.append("content.academicFields must be a non-empty list")
    else:
        names = set()
        for index, field in enumerate(fields, 1):
            name = str(field.get("name", "")).strip()
            counts = field.get("items", {})
            minimum, maximum = counts.get("min"), counts.get("max")
            if not name:
                errors.append(f"academicFields[{index}].name is required")
            elif name in names:
                errors.append(f"duplicate academic field: {name}")
            names.add(name)
            if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 0 or maximum < minimum:
                errors.append(f"academicFields[{index}].items must satisfy 0 <= min <= max")
    art = data.get("content", {}).get("art", {})
    for key in ("targetItems", "minimumDistinctSources", "maximumItemsPerSource"):
        if not isinstance(art.get(key), int) or art[key] < 1:
            errors.append(f"content.art.{key} must be a positive integer")
    if art.get("minimumDistinctSources", 0) > art.get("targetItems", 0):
        errors.append("content.art.minimumDistinctSources cannot exceed targetItems")
    for key in ("prepareAt", "deliverAt"):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(data.get("schedule", {}).get(key, ""))):
            errors.append(f"schedule.{key} must use HH:MM")
    return errors


def _apply_environment_overrides(data: dict, environ: dict[str, str]) -> dict:
    result = deepcopy(data)
    integer_overrides = {
        "DISPATCH_ART_TARGET": ("content", "art", "targetItems"),
        "DISPATCH_ART_MIN_SOURCES": ("content", "art", "minimumDistinctSources"),
        "DISPATCH_ART_MAX_PER_SOURCE": ("content", "art", "maximumItemsPerSource"),
        "DISPATCH_READY_MAX_AGE_MINUTES": ("schedule", "readyMaxAgeMinutes"),
    }
    string_overrides = {
        "DISPATCH_PREPARE_AT": ("schedule", "prepareAt"),
        "DISPATCH_DELIVER_AT": ("schedule", "deliverAt"),
        "TTS_VOICE": ("tts", "voice"),
        "TTS_RATE": ("tts", "rate"),
    }
    for name, keys in integer_overrides.items():
        if name not in environ or not str(environ[name]).strip():
            continue
        value = int(environ[name])
        target = result
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = value
    for name, keys in string_overrides.items():
        if name not in environ or not str(environ[name]).strip():
            continue
        target = result
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = str(environ[name]).strip()
    return result


def load_dispatch_config(path: Path, *, environ: dict[str, str] | None = None) -> DispatchConfig:
    path = path.resolve()
    json_path = path if path.suffix.lower() == ".json" else path.parent / "dispatch.config.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        try:
            data = _apply_environment_overrides(data, environ if environ is not None else os.environ)
        except ValueError as exc:
            raise ValueError(f"invalid integer environment override: {exc}") from exc
        errors = validate_config_data(data)
        if errors:
            raise ValueError("; ".join(errors))
        return DispatchConfig(data, json_path)
    legacy_path = path.parent / "config.md" if path.suffix.lower() == ".json" else path
    fields = _parse_markdown_fields(legacy_path)
    if not fields:
        raise ValueError(f"configuration not found or invalid: {path}")
    return DispatchConfig(
        {
            "schemaVersion": 1,
            "content": {
                "academicFields": [
                    {
                        "name": field.name,
                        "keywords": [part.strip() for part in field.keywords.split("/") if part.strip()],
                        "items": {"min": field.min_items, "max": field.max_items},
                    }
                    for field in fields
                ],
                "art": {"targetItems": 5, "minimumDistinctSources": 3, "maximumItemsPerSource": 2},
            },
            "schedule": {"prepareAt": "06:20", "deliverAt": "07:00"},
        },
        legacy_path,
        legacy=True,
    )


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


def _parse_markdown_fields(config_path: Path) -> list[FieldSpec]:
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


def parse_config_fields(config_path: Path) -> list[FieldSpec]:
    try:
        return load_dispatch_config(config_path).fields
    except (OSError, ValueError, json.JSONDecodeError):
        return []
