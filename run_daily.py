#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_daily.py — 会打岔的学术速递：后处理主入口

用法：
    python run_daily.py [YYYY-MM-DD]

兼容入口：内部委托给 finalize_dispatch.py 和 deliver_ready.py。

注意：
    学术内容采集（WebSearch + AI 筛选）需要由 AI agent 完成。
    agent 在采集完成并将 Markdown 写入 data/ 目录后，调用本脚本即可。
    详细工作流见项目根目录的 AGENTS.md。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.dispatch_paths import ProjectPaths, resolve_dispatch_date

WORK_DIR = Path(__file__).resolve().parent


def venv_python_candidates(project_root: Path, platform_name: str | None = None) -> list[Path]:
    platform_name = platform_name or os.name
    windows_python = project_root / ".venv" / "Scripts" / "python.exe"
    unix_python = project_root / ".venv" / "bin" / "python"
    return [windows_python, unix_python] if platform_name == "nt" else [unix_python, windows_python]


def select_python(
    project_root: Path = WORK_DIR,
    *,
    current_python: str | None = None,
    platform_name: str | None = None,
    runner=None,
) -> str:
    current_python = current_python or sys.executable
    runner = runner or subprocess.run
    candidates = [path for path in venv_python_candidates(project_root, platform_name) if path.exists()]
    for candidate in candidates:
        try:
            runner(
                [str(candidate), "--version"],
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True,
            )
            return str(candidate)
        except Exception as exc:
            print(f"\n[WARN] 虚拟环境 Python 不可用: {candidate} ({exc})")
    if not candidates:
        print(f"\n[WARN] 未检测到虚拟环境 (.venv)，尝试使用当前 Python。")
        print("  如需完整本地环境，请运行 setup.ps1（Windows）或 setup.sh（Linux/macOS）。")
    else:
        print("[WARN] 所有本地虚拟环境解释器均不可用，改用当前 Python。")
    return current_python


def run_step(
    project: ProjectPaths,
    python_executable: str,
    script_name: str,
    date_str: str,
    step_desc: str,
    extra_args=None,
) -> bool:
    script_path = project.scripts / script_name
    if not script_path.is_file():
        print(f"[ERROR] 后处理脚本不存在: {script_path}")
        return False
    cmd = [python_executable, str(script_path), date_str, "--root", str(project.root)]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*50}")
    print(f"  {step_desc}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, cwd=str(project.root))
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="会打岔的学术速递后处理入口。")
    parser.add_argument("date", nargs="?", help="日期，格式 YYYY-MM-DD。")
    parser.add_argument("--root", type=Path, default=WORK_DIR, help="项目根目录。")
    parser.add_argument("--strict-email", action="store_true", help="兼容参数；两阶段交付始终严格处理邮件失败。")
    parser.add_argument("--skip-email", action="store_true", help="只 finalize，不发送邮件。")
    args = parser.parse_args(argv)

    project = ProjectPaths.from_root(args.root)
    if not project.root.is_dir():
        parser.error(f"project root does not exist: {project.root}")
    try:
        date_str = resolve_dispatch_date(args.date)
    except ValueError as exc:
        parser.error(str(exc))
    artifacts = project.artifacts(date_str)
    md_path = artifacts.markdown
    if not md_path.exists():
        print(f"[ERROR] Markdown 文件不存在: {md_path}")
        print(f"  请先由 AI agent 完成内容采集并写入 data/ 目录。")
        print(f"  详细工作流见 AGENTS.md。")
        sys.exit(1)

    print(f"会打岔的学术速递 — 两阶段兼容入口")
    print(f"日期: {date_str}")
    print(f"Markdown: {md_path}")

    python_executable = select_python(project.root)
    ok1 = run_step(project, python_executable, "finalize_dispatch.py", date_str, "[1/2] 校验、TTS 与 ready manifest")
    if not ok1:
        print("\n[ERROR] TTS 生成失败，中止。")
        sys.exit(1)

    if args.skip_email:
        print("\n[INFO] 已按要求跳过邮件推送。")
    else:
        ok2 = run_step(project, python_executable, "deliver_ready.py", date_str, "[2/2] 复核 ready manifest 并发送")
        if not ok2:
            print("\n[ERROR] 确定性交付失败；未回退到旧内容。")
            sys.exit(1)
        else:
            print("\n[OK] 全部完成！")

    mp3_path = artifacts.audio
    if mp3_path.exists():
        size_kb = mp3_path.stat().st_size / 1024
        print(f"  音频文件: {mp3_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
