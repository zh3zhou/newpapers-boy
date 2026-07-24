#!/usr/bin/env python
"""Guide a user through safely enabling a real GitHub schedule."""

from __future__ import annotations

import argparse
import getpass
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER_CMD = "python scripts/openai_dispatch_agent.py"


def run_gh(args, *, stdin=None, check=True, capture=False):
    return subprocess.run(
        ["gh", *args], input=stdin, text=True, encoding="utf-8",
        cwd=ROOT, check=check, capture_output=capture,
    )


def repository() -> str:
    result = run_gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], capture=True)
    return result.stdout.strip()


def set_variable(repo: str, name: str, value: str) -> None:
    run_gh(["variable", "set", name, "--repo", repo, "--body", value])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="配置 OpenAI runner，真实试跑成功后启用每日定时。")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--repo")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)

    if not shutil.which("gh"):
        print("[BLOCK] 未找到 gh。请先安装 GitHub CLI，并重新打开终端。")
        return 2
    try:
        repo = args.repo or repository()
        run_gh(["auth", "status"], capture=True)
    except subprocess.CalledProcessError:
        print("[BLOCK] GitHub CLI 尚未登录。请先运行 gh auth login。")
        return 2

    print(f"[OK] GitHub 仓库: {repo}")
    print("[INFO] 推荐 runner: OpenAI Responses API + Web Search")
    print(f"[INFO] 默认模型: {args.model}")
    print("[INFO] ChatGPT/Codex 订阅登录不能代替 API Key；API 使用单独计费。")
    print("[INFO] 配置会先保持定时关闭，真实试跑成功后才启用。")
    if args.check_only:
        return 0

    key = getpass.getpass("请输入 OpenAI API Key（输入不可见，不会写入本地文件）: ").strip()
    if not key:
        print("[BLOCK] 未输入 API Key，没有修改 GitHub。")
        return 2
    confirm = input("确认上传到该仓库的 GitHub Secret 并开始真实试跑？[y/N]: ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("[INFO] 已取消，没有修改 GitHub。")
        return 0

    run_gh(["secret", "set", "OPENAI_API_KEY", "--repo", repo], stdin=key)
    key = ""
    set_variable(repo, "AGENT_RUNNER_CMD", RUNNER_CMD)
    set_variable(repo, "OPENAI_MODEL", args.model)
    set_variable(repo, "DISPATCH_ENABLED", "false")
    print("[OK] 凭据和 runner 已配置；定时仍为关闭。")

    previous = run_gh(["run", "list", "--repo", repo, "--workflow", "prepare-dispatch.yml",
                       "--event", "workflow_dispatch", "--limit", "1", "--json", "databaseId"], capture=True)
    previous_rows = json.loads(previous.stdout)
    previous_id = previous_rows[0]["databaseId"] if previous_rows else None
    run_gh(["workflow", "run", "prepare-dispatch.yml", "--repo", repo,
            "-f", "mock=false"])
    latest = None
    for _ in range(15):
        time.sleep(2)
        runs = run_gh(["run", "list", "--repo", repo, "--workflow", "prepare-dispatch.yml",
                       "--event", "workflow_dispatch", "--limit", "1", "--json", "databaseId,url"], capture=True)
        rows = json.loads(runs.stdout)
        if rows and rows[0]["databaseId"] != previous_id:
            latest = rows[0]
            break
    if latest is None:
        print("[BLOCK] 已触发 workflow，但未能取得新运行编号；定时仍保持关闭。")
        return 3
    print(f"[INFO] 正在等待真实试跑: {latest['url']}")
    watched = run_gh(["run", "watch", str(latest["databaseId"]), "--repo", repo, "--exit-status"], check=False)
    if watched.returncode != 0:
        print("[BLOCK] 真实试跑失败，DISPATCH_ENABLED 仍为 false。请让 agent 检查 Actions 日志。")
        return 3

    confirm_enable = input("真实 prepare 试跑成功。现在启用每天 06:20/07:00（北京时间）的双阶段运行？[y/N]: ").strip().lower()
    if confirm_enable not in {"y", "yes"}:
        print("[INFO] 已通过真实试跑，但定时仍保持关闭；以后可重新运行本向导。")
        return 0
    set_variable(repo, "DISPATCH_ENABLED", "true")
    print("[OK] 已启用每天 06:20 准备、07:00 发送（北京时间）的双阶段简报。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
