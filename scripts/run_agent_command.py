#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run the configured agent command that generates the daily Markdown file."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from env_utils import load_env
from validate_dispatch import parse_config_fields

WORK_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = WORK_DIR / "data"

DEFAULT_AGENT_ENV_ALLOWLIST = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "AGENT_PROVIDER_TOKEN",
    "OPENAI_MODEL",
    "OPENAI_REASONING_EFFORT",
}
SAFE_SYSTEM_ENV = {
    "PATH",
    "PATHEXT",
    "HOME",
    "USERPROFILE",
    "TEMP",
    "TMP",
    "TMPDIR",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CI",
    "GITHUB_ACTIONS",
    "GITHUB_WORKSPACE",
    "GITHUB_REPOSITORY",
    "GITHUB_RUN_ID",
    "RUNNER_OS",
    "RUNNER_TEMP",
}
FORBIDDEN_AGENT_ENV = {"MAIL_TO"}


def build_mock_markdown(date_str: str) -> str:
    fields = parse_config_fields(WORK_DIR / "config.md")
    if not fields:
        fields = []

    lines = [
        f"# 会打岔的学术速递 [MOCK] — {date_str}",
        "",
        "> Mock run for scheduler smoke testing.",
        "",
    ]

    cn_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
    for idx, field in enumerate(fields, 1):
        prefix = cn_nums[idx - 1] if idx <= len(cn_nums) else str(idx)
        lines.extend(
            [
                f"## {prefix}、{field.name}",
                "",
                f"- **Mock research item for {field.name}** — MockSource",
                f"  摘要：这是 {field.name} 的 mock 条目，用于验证 agent 命令、Markdown 契约和后处理流程。",
                "  为什么值得看：它能在不调用真实 agent 的情况下测试 GitHub Actions 的端到端路径。",
                "  https://example.com/",
                "",
            ]
        )

    lines.extend(
        [
            "## ✦ 今日打岔 ✦",
            "",
            "### 艺术一刻",
            "",
            "- **Mock artwork** — MockMuseum",
            "  简介：这是用于 CI 烟测的艺术条目，确保 TTS 和邮件正文能解析打岔板块。",
            "  https://example.com/",
            "",
            "### 会心一笑",
            "",
            "- 这是一条 mock 趣味内容：当定时任务能自己产出 artifact，项目就少了一点手动守夜。",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_date(value: str | None) -> str:
    if value:
        return value
    return datetime.now().strftime("%Y-%m-%d")


def parse_agent_env_allowlist(env: dict[str, str]) -> set[str]:
    names = set(DEFAULT_AGENT_ENV_ALLOWLIST)
    configured = env.get("AGENT_ENV_ALLOWLIST", "")
    names.update(name.strip() for name in configured.split(",") if name.strip())
    return {name for name in names if not name.startswith("SMTP_") and name not in FORBIDDEN_AGENT_ENV}


def build_child_env(env: dict[str, str], base_env: dict[str, str] | None = None) -> dict[str, str]:
    source = base_env if base_env is not None else os.environ
    child_env = {key: value for key, value in source.items() if key.upper() in SAFE_SYSTEM_ENV}

    for name in parse_agent_env_allowlist(env):
        value = env.get(name)
        if value:
            child_env[name] = value

    return child_env


def redact_output(text: str, env: dict[str, str]) -> str:
    secret_names = parse_agent_env_allowlist(env)
    secret_names.update(name for name in env if name.startswith("SMTP_"))
    secret_names.add("MAIL_TO")
    secret_names.update(
        name
        for name in env
        if name.upper().endswith(("_KEY", "_TOKEN", "_PASS", "_PASSWORD", "_SECRET", "_PROXY"))
    )
    values = {env.get(name, "") for name in secret_names}
    for value in sorted((value for value in values if len(value) >= 4), key=len, reverse=True):
        text = text.replace(value, "***REDACTED***")
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="执行 agent 生成命令。")
    parser.add_argument("date", nargs="?", help="日期，格式 YYYY-MM-DD。")
    parser.add_argument("--output", type=Path, help="Markdown 输出路径。")
    parser.add_argument("--log", type=Path, help="agent 日志路径。")
    parser.add_argument("--timeout", type=int, help="agent 命令最长运行秒数，默认 1800。")
    parser.add_argument("--mock", action="store_true", help="生成 mock Markdown，用于 CI 手动烟测。")
    args = parser.parse_args(argv)

    env = load_env(WORK_DIR)
    date_str = resolve_date(args.date or env.get("DISPATCH_DATE"))
    output_path = args.output or Path(env.get("DISPATCH_OUTPUT", DATA_DIR / f"{date_str}_学术速递.md"))
    if not output_path.is_absolute():
        output_path = WORK_DIR / output_path
    log_path = args.log or DATA_DIR / f"{date_str}_agent.log"
    if not log_path.is_absolute():
        log_path = WORK_DIR / log_path

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    mock = args.mock or env.get("AGENT_RUNNER_MOCK", "").lower() in {"1", "true", "yes"}
    if mock:
        output_path.write_text(build_mock_markdown(date_str), encoding="utf-8")
        log_path.write_text(f"mock agent runner wrote {output_path}\n", encoding="utf-8")
        print(f"[OK] mock agent runner wrote Markdown: {output_path}")
        return 0

    command = env.get("AGENT_RUNNER_CMD", "").strip()
    if not command:
        print("[ERROR] AGENT_RUNNER_CMD is not set.")
        print("[ERROR] Configure it as a GitHub Actions repository variable/secret, or run with --mock for smoke tests.")
        print("[INFO] Without a runner, open this project in any capable agent and ask it to read AGENTS.md and config.md.")
        return 2

    try:
        timeout_seconds = args.timeout or int(env.get("AGENT_TIMEOUT_SECONDS", "1800"))
    except ValueError:
        print("[ERROR] AGENT_TIMEOUT_SECONDS must be an integer.")
        return 2

    temporary_output = output_path.with_name(f".{output_path.name}.{os.getpid()}.agent-tmp")
    temporary_output.unlink(missing_ok=True)

    child_env = build_child_env(env)
    child_env.update(
        {
            "DISPATCH_DATE": date_str,
            "DISPATCH_OUTPUT": str(temporary_output),
            "DISPATCH_CONFIG": env.get("DISPATCH_CONFIG", "config.md"),
            "PROJECT_ROOT": str(WORK_DIR),
            "DISPATCH_MODE": env.get("DISPATCH_MODE", "local"),
        }
    )

    print("[INFO] running AGENT_RUNNER_CMD from project root")
    try:
        result = subprocess.run(
            command,
            cwd=str(WORK_DIR),
            env=child_env,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_stdout = exc.stdout or ""
        timeout_stderr = exc.stderr or ""
        if isinstance(timeout_stdout, bytes):
            timeout_stdout = timeout_stdout.decode("utf-8", errors="replace")
        if isinstance(timeout_stderr, bytes):
            timeout_stderr = timeout_stderr.decode("utf-8", errors="replace")
        safe_output = redact_output(timeout_stdout + timeout_stderr, env)
        log_path.write_text(safe_output, encoding="utf-8")
        temporary_output.unlink(missing_ok=True)
        print(f"[ERROR] agent command timed out after {timeout_seconds} seconds")
        return 6
    safe_output = redact_output(result.stdout or "", env)
    log_path.write_text(safe_output, encoding="utf-8")
    if safe_output:
        print(safe_output)

    if result.returncode != 0:
        temporary_output.unlink(missing_ok=True)
        print(f"[ERROR] agent command failed with exit code {result.returncode}")
        return result.returncode

    if not temporary_output.exists():
        print(f"[ERROR] agent command completed but did not create a fresh output: {output_path}")
        return 3

    try:
        content = temporary_output.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        temporary_output.unlink(missing_ok=True)
        print(f"[ERROR] agent output is not valid UTF-8: {output_path}")
        return 4

    if not content.strip():
        temporary_output.unlink(missing_ok=True)
        print(f"[ERROR] agent output is empty: {output_path}")
        return 5

    temporary_output.replace(output_path)

    print(f"[OK] agent output ready: {output_path}")
    print(f"[INFO] agent log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
