#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_daily.py — 会打岔的学术速递：后处理主入口

用法：
    python run_daily.py [YYYY-MM-DD]

功能：
    1. 检查环境（venv、依赖）
    2. 运行 TTS 生成 MP3 播报
    3. 发送邮件推送（含 MP3 附件）

注意：
    学术内容采集（WebSearch + AI 筛选）需要由 AI agent 完成。
    agent 在采集完成并将 Markdown 写入 data/ 目录后，调用本脚本即可。
    详细工作流见项目根目录的 AGENTS.md。
"""

import sys
sys.dont_write_bytecode = True

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = WORK_DIR / "scripts"
DATA_DIR = WORK_DIR / "data"
VENV_PYTHON = WORK_DIR / ".venv" / "Scripts" / "python.exe"


def select_python() -> str:
    if VENV_PYTHON.exists():
        try:
            subprocess.run(
                [str(VENV_PYTHON), "--version"],
                cwd=str(WORK_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True,
            )
            return str(VENV_PYTHON)
        except Exception as exc:
            print(f"\n[WARN] 虚拟环境 Python 不可用，改用当前 Python: {exc}")
    else:
        print(f"\n[WARN] 未检测到虚拟环境 (.venv)，尝试使用当前 Python。")
        print(f"  如需完整本地环境，请先运行: setup.ps1")
    return sys.executable


def run_step(script_name: str, date_str: str, step_desc: str, extra_args=None) -> bool:
    script_path = SCRIPTS_DIR / script_name
    py = select_python()
    cmd = [str(py), str(script_path), date_str]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*50}")
    print(f"  {step_desc}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, cwd=str(WORK_DIR))
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="会打岔的学术速递后处理入口。")
    parser.add_argument("date", nargs="?", help="日期，格式 YYYY-MM-DD。")
    parser.add_argument("--strict-email", action="store_true", help="邮件失败时返回非零退出码。")
    parser.add_argument("--skip-email", action="store_true", help="只生成 TTS，不发送邮件。")
    args = parser.parse_args(argv)

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    strict_email = args.strict_email or os.environ.get("DISPATCH_MODE") == "ci"

    md_path = DATA_DIR / f"{date_str}_学术速递.md"
    if not md_path.exists():
        print(f"[ERROR] Markdown 文件不存在: {md_path}")
        print(f"  请先由 AI agent 完成内容采集并写入 data/ 目录。")
        print(f"  详细工作流见 AGENTS.md。")
        sys.exit(1)

    print(f"会打岔的学术速递 — 后处理")
    print(f"日期: {date_str}")
    print(f"Markdown: {md_path}")

    ok1 = run_step("tts_generate.py", date_str, "[1/2] 生成语音播报")
    if not ok1:
        print("\n[ERROR] TTS 生成失败，中止。")
        sys.exit(1)

    if args.skip_email:
        print("\n[INFO] 已按要求跳过邮件推送。")
    else:
        push_args = ["--strict"] if strict_email else []
        ok2 = run_step("push_email.py", date_str, "[2/2] 发送邮件推送", push_args)
        if not ok2:
            message = "\n[ERROR] 邮件推送失败，但 MP3 已生成。" if strict_email else "\n[WARN] 邮件推送失败，但 MP3 已生成。"
            print(message)
            if strict_email:
                sys.exit(1)
        else:
            print("\n[OK] 全部完成！")

    mp3_path = DATA_DIR / f"{date_str}_学术播报.mp3"
    if mp3_path.exists():
        size_kb = mp3_path.stat().st_size / 1024
        print(f"  音频文件: {mp3_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
