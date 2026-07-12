#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tts_generate.py — 将当日「会打岔的学术速递」Markdown 转为新闻播报式 MP3。

用法：
    python scripts/tts_generate.py [YYYY-MM-DD]
    不传日期则使用当天日期。

依赖：edge-tts（安装在 .venv 中）
输出：data/YYYY-MM-DD_学术播报.mp3
      data/YYYY-MM-DD_播报稿.txt（朗读稿，便于调试）

设计原则：
    - 不硬编码领域名称，从 Markdown 二级标题（##）动态解析学术板块。
    - 「今日打岔」板块下的「艺术一刻」和「会心一笑」按三级标题（###）识别。
    - 任意领域配置均可正确播报，无需修改代码。
"""

import sys
sys.dont_write_bytecode = True

import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from env_utils import load_env

WORK_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = WORK_DIR / "data"
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
DEFAULT_RATE = "+0%"

DIVERSION_KEYWORDS = ("打岔", "休闲", "轻松一刻", "diversion")
ART_KEYWORDS = ("艺术", "摄影", "art")
HUMOR_KEYWORDS = ("笑", "幽默", "趣味", "冷知识", "趣闻", "段子", "humor")


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"[*_`#>]+", "", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def smart_truncate(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        if text and text[-1] not in "。！？.!?":
            text += "。"
        return text
    segment = text[:max_len]
    for punct in ("。", "！", "？"):
        pos = segment.rfind(punct)
        if pos >= max_len * 0.4:
            return segment[: pos + 1]
    for i in range(len(segment) - 1, -1, -1):
        ch = segment[i]
        if ch in ".!?":
            if ch == "." and i > 0 and segment[i - 1].isdigit():
                continue
            if i >= max_len * 0.4:
                return segment[: i + 1]
    for punct in ("；", "，", "、"):
        pos = segment.rfind(punct)
        if pos >= max_len * 0.5:
            return segment[:pos] + "。"
    for punct in (";", ","):
        pos = segment.rfind(punct)
        if pos >= max_len * 0.5:
            return segment[:pos] + "。"
    return segment[: max_len - 1] + "。"


def _is_diversion_heading(title: str) -> bool:
    return any(kw in title for kw in DIVERSION_KEYWORDS)


def _is_art_heading(title: str) -> bool:
    return any(kw in title for kw in ART_KEYWORDS)


def _is_humor_heading(title: str) -> bool:
    return any(kw in title for kw in HUMOR_KEYWORDS)


def _collect_sub_items(lines, start_idx):
    j = start_idx + 1
    sub_lines = []
    while j < len(lines):
        nxt = lines[j]
        if nxt.startswith("  ") or nxt.startswith("\t"):
            sub_lines.append(nxt.strip())
            j += 1
        elif nxt.strip() == "":
            j += 1
        else:
            break
    return sub_lines, j


def parse_markdown(md_text: str) -> dict:
    """
    泛化 Markdown 解析：
      - 任意 ## 二级标题 视为一个学术板块（除非命中打岔关键词）
      - ## 含"打岔"等关键词时进入 diversion 模式
        - 其下 ### 命中"艺术"等 → 艺术板块
        - 其下 ### 命中"笑/幽默/趣味"等 → 趣味板块
      - 学术条目：以 "- **" 或 "* **" 开头的列表项，紧随缩进行为"摘要/为什么值得看"
    """
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
    current_items = []
    mode = None

    def flush_section():
        nonlocal current_section_title, current_items
        if current_section_title is not None and mode == "academic":
            result["sections"].append({"title": current_section_title, "items": current_items})
        current_section_title = None
        current_items = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("---"):
            i += 1
            continue

        if stripped.startswith("# "):
            i += 1
            continue

        if stripped.startswith(">") and mode is None and not in_diversion:
            result["intro"] = stripped.lstrip(">").strip()
            i += 1
            continue

        m2 = re.match(r"^##\s+(?:[一二三四五六七八九十]+、)?\s*(.+)", stripped)
        if m2:
            flush_section()
            heading = m2.group(1).strip()
            if _is_diversion_heading(heading):
                in_diversion = True
                mode = None
            else:
                in_diversion = False
                mode = "academic"
                current_section_title = heading
                current_items = []
            i += 1
            continue

        m3 = re.match(r"^###\s+(.+)", stripped)
        if m3 and in_diversion:
            flush_section()
            sub = m3.group(1).strip()
            if _is_art_heading(sub):
                mode = "art"
            elif _is_humor_heading(sub):
                mode = "humor"
            else:
                mode = None
            i += 1
            continue

        if mode == "academic" and re.match(r"^[-*]\s+\*\*", stripped):
            sub_lines, j = _collect_sub_items(lines, i)
            summary = ""
            why = ""
            for sl in sub_lines:
                sl_clean = clean_text(sl)
                if sl_clean.startswith("摘要"):
                    summary = re.sub(r"^摘要[：:]\s*", "", sl_clean)
                elif sl_clean.startswith("为什么值得看"):
                    why = re.sub(r"^为什么值得看[：:]\s*", "", sl_clean)
            current_items.append({"summary": summary, "why": why})
            i = j
            continue

        if mode == "art" and re.match(r"^[-*]\s+\*\*", stripped):
            title_m = re.match(r"^[-*]\s+\*\*(.+?)\*\*", stripped)
            art_title = clean_text(title_m.group(1)) if title_m else ""
            art_title = re.sub(r"\s*[—–-]+\s*.+$", "", art_title).strip()
            sub_lines, j = _collect_sub_items(lines, i)
            intro = ""
            for sl in sub_lines:
                sl_clean = clean_text(sl)
                if sl_clean.startswith("简介"):
                    intro = re.sub(r"^简介[：:]\s*", "", sl_clean)
                elif not sl_clean.startswith("链接") and not sl_clean.startswith("http"):
                    if intro:
                        intro += " " + sl_clean
                    else:
                        intro = sl_clean
            result["arts"].append({"title": art_title, "intro": intro})
            i = j
            continue

        if mode == "humor" and re.match(r"^[-*]\s+", stripped):
            text = re.sub(r"^[-*]\s+", "", stripped)
            sub_lines, j = _collect_sub_items(lines, i)
            for sl in sub_lines:
                text += " " + sl.strip()
            text = clean_text(text)
            text = re.sub(r"^(冷知识一则|段子|笑话|趣事|趣闻)[：:]\s*", "", text)
            result["humors"].append(text)
            i = j
            continue

        i += 1

    flush_section()
    return result


def _section_intro(idx: int, total: int, title: str) -> str:
    if total == 1:
        return f"来看今天唯一的重点领域：{title}。"
    if idx == 0:
        return f"首先来看{title}。"
    if idx == total - 1:
        return f"最后来看{title}。"
    return f"接下来是{title}。"


def build_broadcast_text(parsed: dict) -> str:
    date_str = parsed.get("date") or datetime.now().strftime("%Y-%m-%d")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_cn = f"{dt.year}年{dt.month}月{dt.day}日"
    except Exception:
        date_cn = date_str

    sentences = []
    sentences.append(f"会打岔的学术速递，{date_cn}。")
    sentences.append("各位好，欢迎收听今天的学术速递。")

    total_papers = sum(len(s["items"]) for s in parsed["sections"])
    total_arts = len(parsed["arts"])
    total_humors = len(parsed["humors"])
    total_sections = len(parsed["sections"])

    if total_papers > 0:
        sentences.append(f"今天一共为您精选了{total_papers}篇学术论文，")
    if total_arts or total_humors:
        sentences.append(f"还有{total_arts}件艺术作品和{total_humors}条趣味内容。")

    for idx, sec in enumerate(parsed["sections"]):
        title = sec["title"]
        items = sec["items"]
        sentences.append(_section_intro(idx, total_sections, title))
        for paper_idx, it in enumerate(items, 1):
            summary = it.get("summary", "")
            if summary:
                short = smart_truncate(summary, 150)
                if len(items) > 1:
                    sentences.append(f"第{paper_idx}项研究：{short}")
                else:
                    sentences.append(f"这项研究：{short}")
            else:
                sentences.append(f"第{paper_idx}项研究，详情请查看文字版。")

    if total_arts or total_humors:
        sentences.append("接下来是今天的打岔时间，让大脑歇一歇。")
        if total_arts:
            sentences.append(f"艺术一刻，{total_arts}件有趣的作品。")
            for idx, a in enumerate(parsed["arts"], 1):
                intro = a.get("intro", "")
                title = a.get("title", "")
                if intro:
                    short = smart_truncate(intro, 90)
                    sentences.append(f"第{idx}件：{short}")
                elif title:
                    sentences.append(f"第{idx}件作品：{title}。")
        if total_humors:
            sentences.append("会心一笑。")
            for h in parsed["humors"]:
                short = smart_truncate(h, 130)
                sentences.append(short)

    sentences.append("以上就是今天的学术速递，祝你今天也有好的灵感。再会。")

    text = "\n".join(sentences)
    return text


async def synthesize(text: str, output_path: Path, voice: str, rate: str):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(output_path))


def main():
    ensure_data_dir()
    env = load_env(WORK_DIR)
    voice = env.get("TTS_VOICE", DEFAULT_VOICE)
    rate = env.get("TTS_RATE", DEFAULT_RATE)

    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    md_path = DATA_DIR / f"{date_str}_学术速递.md"
    if not md_path.exists():
        print(f"[ERROR] Markdown 文件不存在: {md_path}", file=sys.stderr)
        sys.exit(1)

    out_path = DATA_DIR / f"{date_str}_学术播报.mp3"

    md_text = md_path.read_text(encoding="utf-8")
    parsed = parse_markdown(md_text)

    has_content = bool(parsed["sections"] or parsed["arts"] or parsed["humors"])
    if not has_content:
        print("[WARN] 未解析到内容，回退为朗读前 3000 字", file=sys.stderr)
        broadcast_text = clean_text(md_text)[:3000]
    else:
        broadcast_text = build_broadcast_text(parsed)

    txt_path = DATA_DIR / f"{date_str}_播报稿.txt"
    txt_path.write_text(broadcast_text, encoding="utf-8")

    print(f"[INFO] 语音: {voice}, 语速: {rate}")
    print(f"[INFO] 学术板块: {len(parsed['sections'])}, 论文: {sum(len(s['items']) for s in parsed['sections'])}")
    print(f"[INFO] 艺术: {len(parsed['arts'])}, 趣味: {len(parsed['humors'])}")
    print(f"[INFO] 朗读稿字数: {len(broadcast_text)}")
    print(f"[INFO] 输出 MP3: {out_path}")

    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(synthesize(broadcast_text, out_path, voice, rate))
    print(f"[OK] 播报音频已生成: {out_path}")
    file_size = out_path.stat().st_size
    print(f"[INFO] 文件大小: {file_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
