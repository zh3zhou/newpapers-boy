#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Side-effect-free parsing for the dispatch Markdown contract."""

from __future__ import annotations

import re

DIVERSION_KEYWORDS = ("打岔", "休闲", "轻松一刻", "diversion")
ART_KEYWORDS = ("艺术", "摄影", "art")
HUMOR_KEYWORDS = ("笑", "幽默", "趣味", "冷知识", "趣闻", "段子", "humor")


def clean_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _heading_matches(title: str, keywords: tuple[str, ...]) -> bool:
    normalized = title.casefold()
    for keyword in keywords:
        normalized_keyword = keyword.casefold()
        if normalized_keyword.isascii():
            if re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized):
                return True
        elif normalized_keyword in normalized:
            return True
    return False


def _collect_sub_items(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    index = start_idx + 1
    sub_lines = []
    while index < len(lines):
        next_line = lines[index]
        if next_line.startswith("  ") or next_line.startswith("\t"):
            sub_lines.append(next_line.strip())
            index += 1
        elif not next_line.strip():
            index += 1
        else:
            break
    return sub_lines, index


def parse_markdown(md_text: str) -> dict:
    """Parse academic, art, and humor items without invoking TTS or network IO."""
    result = {
        "date": None,
        "intro": "",
        "sections": [],
        "arts": [],
        "humors": [],
    }

    date_match = re.search(r"#\s*.+?[—\-\s·]*(\d{4}-\d{2}-\d{2})", md_text)
    if date_match:
        result["date"] = date_match.group(1)

    lines = md_text.splitlines()
    in_diversion = False
    current_section_title = None
    current_items: list[dict] = []
    mode = None

    def flush_section() -> None:
        nonlocal current_section_title, current_items
        if current_section_title is not None and mode == "academic":
            result["sections"].append({"title": current_section_title, "items": current_items})
        current_section_title = None
        current_items = []

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("---"):
            index += 1
            continue
        if stripped.startswith("# "):
            index += 1
            continue
        if stripped.startswith(">") and mode is None and not in_diversion:
            result["intro"] = stripped.lstrip(">").strip()
            index += 1
            continue

        level_two = re.match(r"^##\s+(?:[一二三四五六七八九十]+、)?\s*(.+)", stripped)
        if level_two:
            flush_section()
            heading = level_two.group(1).strip()
            if _heading_matches(heading, DIVERSION_KEYWORDS):
                in_diversion = True
                mode = None
            else:
                in_diversion = False
                mode = "academic"
                current_section_title = heading
                current_items = []
            index += 1
            continue

        level_three = re.match(r"^###\s+(.+)", stripped)
        if level_three and in_diversion:
            flush_section()
            subheading = level_three.group(1).strip()
            if _heading_matches(subheading, ART_KEYWORDS):
                mode = "art"
            elif _heading_matches(subheading, HUMOR_KEYWORDS):
                mode = "humor"
            else:
                mode = None
            index += 1
            continue

        if mode == "academic" and re.match(r"^[-*]\s+\*\*", stripped):
            sub_lines, next_index = _collect_sub_items(lines, index)
            summary = ""
            why = ""
            for sub_line in sub_lines:
                cleaned = clean_text(sub_line)
                if cleaned.startswith("摘要"):
                    summary = re.sub(r"^摘要[：:]\s*", "", cleaned)
                elif cleaned.startswith("为什么值得看"):
                    why = re.sub(r"^为什么值得看[：:]\s*", "", cleaned)
            current_items.append({"summary": summary, "why": why})
            index = next_index
            continue

        if mode == "art" and re.match(r"^[-*]\s+\*\*", stripped):
            title_match = re.match(r"^[-*]\s+\*\*(.+?)\*\*", stripped)
            art_title = clean_text(title_match.group(1)) if title_match else ""
            art_title = re.sub(r"\s*[—–-]+\s*.+$", "", art_title).strip()
            sub_lines, next_index = _collect_sub_items(lines, index)
            intro = ""
            for sub_line in sub_lines:
                cleaned = clean_text(sub_line)
                if cleaned.startswith("简介"):
                    intro = re.sub(r"^简介[：:]\s*", "", cleaned)
                elif not cleaned.startswith(("链接", "http")):
                    intro = f"{intro} {cleaned}".strip()
            result["arts"].append({"title": art_title, "intro": intro})
            index = next_index
            continue

        if mode == "humor" and re.match(r"^[-*]\s+", stripped):
            text = re.sub(r"^[-*]\s+", "", stripped)
            sub_lines, next_index = _collect_sub_items(lines, index)
            if sub_lines:
                text += " " + " ".join(line.strip() for line in sub_lines)
            text = clean_text(text)
            text = re.sub(r"^(冷知识一则|段子|笑话|趣事|趣闻)[：:]\s*", "", text)
            result["humors"].append(text)
            index = next_index
            continue

        index += 1

    flush_section()
    return result
