#!/usr/bin/env python
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ITEM_RE = re.compile(r"^[-*]\s+\*\*(.+?)\*\*\s+[—-]\s+(.+?)\s*$")
URL_RE = re.compile(r"https?://[^\s<>)\]]+")


def normalize_title(value: str) -> str:
    return re.sub(r"\W+", "", value.casefold(), flags=re.UNICODE)


def extract_content_entries(markdown: str, date_str: str) -> list[dict]:
    entries = []
    section = ""
    kind = "academic"
    current = None
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = re.sub(r"^[一二三四五六七八九十\d]+、\s*", "", line[3:].strip()).strip(" ✦")
            kind = "diversion" if "打岔" in section else "academic"
            current = None
            continue
        if line.startswith("### "):
            section = line[4:].strip()
            kind = "art" if re.search(r"艺术|摄影|art", section, re.I) else "humor"
            current = None
            continue
        match = ITEM_RE.match(line)
        if match:
            title, source = match.groups()
            current = {
                "date": date_str,
                "kind": kind,
                "section": section,
                "title": title.strip(),
                "normalizedTitle": normalize_title(title),
                "source": source.strip(),
                "url": "",
                "domain": "",
            }
            entries.append(current)
            continue
        if current:
            url_match = URL_RE.search(line)
            if url_match:
                url = url_match.group(0).rstrip(".,，。;；")
                current["url"] = url
                current["domain"] = (urlsplit(url).hostname or "").lower().removeprefix("www.")
                current = None
    return entries


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def history_findings(entries: list[dict], history: list[dict], current_date: str, *, duplicate_days=30, diversity_days=7) -> dict:
    today = date.fromisoformat(current_date)
    duplicate_cutoff = today - timedelta(days=duplicate_days)
    diversity_cutoff = today - timedelta(days=diversity_days)
    recent_duplicates = [
        row for row in history
        if row.get("date") and date.fromisoformat(row["date"]) >= duplicate_cutoff
    ]
    urls = {row.get("url") for row in recent_duplicates if row.get("url")}
    titles = {row.get("normalizedTitle") for row in recent_duplicates if row.get("normalizedTitle")}
    duplicates = [
        entry for entry in entries
        if (entry.get("url") and entry["url"] in urls)
        or (entry.get("normalizedTitle") and entry["normalizedTitle"] in titles)
    ]
    rolling = [
        row for row in history + entries
        if row.get("date") and date.fromisoformat(row["date"]) >= diversity_cutoff
    ]
    academic_domains = {}
    for row in rolling:
        if row.get("kind") != "academic" or not row.get("domain"):
            continue
        academic_domains.setdefault(row.get("section", ""), set()).add(row["domain"])
    concentration_warnings = [
        f"{section} used only one source domain in the last {diversity_days} days"
        for section, domains in academic_domains.items()
        if len(domains) < 2
    ]
    domains = Counter(entry.get("domain") for entry in entries if entry.get("domain"))
    return {
        "duplicates": duplicates,
        "warnings": concentration_warnings,
        "sourceDomains": dict(domains),
    }


def append_history(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
