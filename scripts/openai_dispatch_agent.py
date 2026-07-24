#!/usr/bin/env python
"""Generate a dispatch with the OpenAI Responses API and web search."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parent.parent))


def build_prompt(date: str, agents: str, config: str) -> str:
    return f"""你是无人值守的学术简报编辑 agent。今天是 {date}。
使用 web search 搜索并核验近期来源，严格执行下面的项目契约和配置。
只返回最终 Markdown，不要代码围栏、解释或执行日志。标题日期必须是 {date}。
每个链接必须来自你实际检索到的页面，禁止编造 URL。
艺术一刻必须主动做广域 web search，不得从固定站点抓取或默认只查 MoMA。
每日默认目标 5 条艺术内容，质量不足时宁缺毋滥；目标覆盖至少 3 个相互独立的
来源/机构和域名，同一来源最多 2 条；
优先轮换可信博物馆、美术馆、艺术节、摄影机构、艺术媒体及艺术家或项目官方页面。

--- AGENTS.md ---
{agents}

--- dispatch.config.json ---
{config}
"""


def add_citation_links(text: str, annotations: list[dict]) -> str:
    edits = []
    for annotation in annotations:
        if annotation.get("type") != "url_citation" or not annotation.get("url"):
            continue
        start = annotation.get("start_index")
        end = annotation.get("end_index")
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= len(text)):
            continue
        label = text[start:end]
        if annotation["url"] in label:
            continue
        edits.append((start, end, f"[{label}]({annotation['url']})"))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def extract_output_text(payload: dict) -> str:
    parts = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(add_citation_links(content["text"], content.get("annotations", [])))
    return "\n".join(parts).strip()


def strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```markdown") and text.endswith("```"):
        return text[len("```markdown") : -3].strip()
    if text.startswith("```") and text.endswith("```"):
        return text[3:-3].strip()
    return text


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    date = os.environ.get("DISPATCH_DATE", "").strip()
    output = os.environ.get("DISPATCH_OUTPUT", "").strip()
    config_name = os.environ.get("DISPATCH_CONFIG", "dispatch.config.json")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY is missing.")
        return 2
    if not date or not output:
        print("[ERROR] DISPATCH_DATE and DISPATCH_OUTPUT are required.")
        return 2

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    config = (ROOT / config_name).read_text(encoding="utf-8")
    prompt = build_prompt(date, agents, config)
    request_body = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        "tools": [{"type": "web_search"}],
        "input": prompt,
        "reasoning": {"effort": os.environ.get("OPENAI_REASONING_EFFORT", "medium")},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"[ERROR] OpenAI API returned HTTP {exc.code}.")
        return 3
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] OpenAI request failed: {type(exc).__name__}")
        return 4

    markdown = strip_markdown_fence(extract_output_text(payload))
    if not markdown:
        print("[ERROR] OpenAI response did not contain output_text.")
        return 5
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown + "\n", encoding="utf-8")
    print(f"[OK] OpenAI runner wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
