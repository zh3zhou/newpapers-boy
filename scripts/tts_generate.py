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

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

try:
    from .dispatch_config import load_dispatch_config
    from .dispatch_markdown import clean_text, parse_markdown
    from .dispatch_paths import ProjectPaths, resolve_dispatch_date, resolve_from_root
    from .env_utils import load_env
except ImportError:  # Direct script execution: python scripts/tts_generate.py
    from dispatch_config import load_dispatch_config
    from dispatch_markdown import clean_text, parse_markdown
    from dispatch_paths import ProjectPaths, resolve_dispatch_date, resolve_from_root
    from env_utils import load_env

WORK_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
DEFAULT_RATE = "+0%"


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="将学术速递 Markdown 生成中文语音播报。")
    parser.add_argument("date", nargs="?", help="日期，格式 YYYY-MM-DD。")
    parser.add_argument("--root", type=Path, default=WORK_DIR, help="项目根目录。")
    parser.add_argument("--markdown", type=Path, help="输入 Markdown；相对路径基于项目根目录。")
    parser.add_argument("--mp3", type=Path, help="输出 MP3；相对路径基于项目根目录。")
    parser.add_argument("--transcript", type=Path, help="输出朗读稿；相对路径基于项目根目录。")
    parser.add_argument("--voice", help="TTS voice；优先于环境变量和 JSON 配置。")
    parser.add_argument("--rate", help="TTS rate；优先于环境变量和 JSON 配置。")
    args = parser.parse_args(argv)

    project = ProjectPaths.from_root(args.root)
    try:
        date_str = resolve_dispatch_date(args.date)
    except ValueError as exc:
        parser.error(str(exc))
    artifacts = project.artifacts(date_str)
    md_path = resolve_from_root(args.markdown, project.root, artifacts.markdown)
    out_path = resolve_from_root(args.mp3, project.root, artifacts.audio)
    txt_path = resolve_from_root(args.transcript, project.root, artifacts.transcript)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.parent.mkdir(parents=True, exist_ok=True)

    env = load_env(project.root)
    try:
        tts_config = load_dispatch_config(project.config).raw.get("tts", {})
    except (OSError, ValueError):
        tts_config = {}
    voice = args.voice or env.get("TTS_VOICE") or tts_config.get("voice") or DEFAULT_VOICE
    rate = args.rate or env.get("TTS_RATE") or tts_config.get("rate") or DEFAULT_RATE
    if not md_path.exists():
        print(f"[ERROR] Markdown 文件不存在: {md_path}", file=sys.stderr)
        return 1

    md_text = md_path.read_text(encoding="utf-8")
    parsed = parse_markdown(md_text)

    has_content = bool(parsed["sections"] or parsed["arts"] or parsed["humors"])
    if not has_content:
        print("[WARN] 未解析到内容，回退为朗读前 3000 字", file=sys.stderr)
        broadcast_text = clean_text(md_text)[:3000]
    else:
        broadcast_text = build_broadcast_text(parsed)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
