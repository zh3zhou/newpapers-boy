#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Redacted readiness checks for humans, agents, and CI setup."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .dispatch_config import parse_config_fields
    from .env_utils import parse_env_file
except ImportError:  # Direct script execution: python scripts/project_doctor.py
    from dispatch_config import parse_config_fields
    from env_utils import parse_env_file

WORK_DIR = Path(__file__).resolve().parent.parent
TARGETS = ("manual", "github-mock", "github-scheduled")
SMTP_NAMES = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO")
WORKFLOW_PATH = ".github/workflows/daily-dispatch.yml"


def run_command(command: list[str], cwd: Path, timeout: int = 15) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return result.returncode, (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def check(name: str, status: str, message: str, **details) -> dict:
    result = {"name": name, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def find_gh() -> str | None:
    found = shutil.which("gh")
    if found:
        return found
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "GitHub CLI" / "gh.exe",
    ]
    return str(next((path for path in candidates if path.is_file()), "")) or None


def python_candidates(root: Path) -> list[str]:
    candidates = [sys.executable]
    if os.name == "nt":
        candidates.append(str(root / ".venv" / "Scripts" / "python.exe"))
    else:
        candidates.append(str(root / ".venv" / "bin" / "python"))
    candidates.extend(filter(None, (shutil.which("py"), shutil.which("python3"), shutil.which("python"))))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def inspect_python(root: Path) -> tuple[dict, dict]:
    attempts = []
    selected = None
    probe_code = (
        "import json,sys; "
        "print('DISPATCH_PYTHON_PROBE=' + json.dumps({'executable': sys.executable, 'version': list(sys.version_info[:3])}))"
    )
    for candidate in python_candidates(root):
        if ("/" in candidate or "\\" in candidate) and not Path(candidate).exists():
            continue
        code, output = run_command([candidate, "-c", probe_code], root)
        payload = None
        marker = "DISPATCH_PYTHON_PROBE="
        if code == 0 and marker in output:
            try:
                payload = json.loads(output.split(marker, 1)[1].splitlines()[0])
            except json.JSONDecodeError:
                payload = None
        version = payload.get("version", []) if isinstance(payload, dict) else []
        working = bool(payload) and tuple(version[:2]) >= (3, 9)
        attempts.append(
            {
                "command": candidate,
                "working": working,
                "version": ".".join(str(part) for part in version) if working else "",
            }
        )
        if selected is None and working:
            selected = candidate

    if not selected:
        return check("python", "block", "没有可运行的 Python；Windows 推荐使用 py 或项目 .venv。", attempts=attempts), check(
            "dependencies", "block", "无法检查 Python 依赖。"
        )

    dependency_code, _ = run_command([selected, "-c", "import edge_tts"], root)
    python_check = check("python", "ok", "Python 可运行。", selected=selected, attempts=attempts)
    dependency_check = (
        check("dependencies", "ok", "TTS 依赖已安装。")
        if dependency_code == 0
        else check("dependencies", "block", "缺少 edge-tts；请运行 setup.ps1 或 pip install -r requirements.txt。")
    )
    return python_check, dependency_check


def repo_from_remote(url: str) -> str | None:
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return match.group(1).removesuffix(".git") if match else None


def read_json_command(command: list[str], root: Path) -> tuple[int, object | None]:
    code, output = run_command(command, root)
    if code != 0:
        return code, None
    try:
        return 0, json.loads(output or "null")
    except json.JSONDecodeError:
        return 1, None


def inspect_github(root: Path) -> tuple[list[dict], dict]:
    checks = []
    state = {
        "repo": None,
        "secret_names": set(),
        "variables": {},
        "workflow_published": False,
    }

    git_code, _ = run_command(["git", "rev-parse", "--show-toplevel"], root)
    checks.append(
        check("git_repo", "ok", "当前目录是 Git 仓库。")
        if git_code == 0
        else check("git_repo", "block", "当前目录不是 Git 仓库。")
    )

    remote_code, remote_url = run_command(["git", "remote", "get-url", "origin"], root)
    repo_guess = repo_from_remote(remote_url) if remote_code == 0 else None
    if repo_guess:
        checks.append(check("git_remote", "ok", "已识别 GitHub origin。", repository=repo_guess))
    else:
        checks.append(check("git_remote", "block", "没有识别到 GitHub origin。"))

    workflow = root / WORKFLOW_PATH
    checks.append(
        check("workflow_local", "ok", f"本地存在 {WORKFLOW_PATH}。")
        if workflow.is_file()
        else check("workflow_local", "block", f"缺少 {WORKFLOW_PATH}。")
    )
    tracked_code, _ = run_command(["git", "ls-files", "--error-unmatch", WORKFLOW_PATH], root)
    checks.append(
        check("workflow_tracked", "ok", "workflow 已被 Git 跟踪。")
        if tracked_code == 0
        else check("workflow_tracked", "block", "workflow 尚未提交，GitHub 还看不到它。")
    )

    gh = find_gh()
    if not gh:
        checks.append(check("gh", "block", "未找到 GitHub CLI（gh）。"))
        return checks, state

    auth_code, _ = run_command([gh, "auth", "status"], root)
    if auth_code != 0:
        checks.append(check("gh", "block", "GitHub CLI 已安装但尚未登录。", path=gh))
        return checks, state
    checks.append(check("gh", "ok", "GitHub CLI 已安装并登录。", path=gh))

    if not repo_guess:
        return checks, state

    repo_code, repo_data = read_json_command(
        [gh, "repo", "view", repo_guess, "--json", "nameWithOwner"], root
    )
    canonical_repo = repo_data.get("nameWithOwner") if repo_code == 0 and isinstance(repo_data, dict) else repo_guess
    state["repo"] = canonical_repo
    if canonical_repo != repo_guess:
        checks.append(check("canonical_repo", "warn", "GitHub 已重命名仓库，origin 仍可通过重定向使用。", repository=canonical_repo))
    else:
        checks.append(check("canonical_repo", "ok", "GitHub 仓库名称是最新的。", repository=canonical_repo))

    workflows_code, workflows = read_json_command(
        [gh, "workflow", "list", "--repo", canonical_repo, "--json", "path,state"], root
    )
    if workflows_code == 0 and isinstance(workflows, list):
        state["workflow_published"] = any(item.get("path") == WORKFLOW_PATH for item in workflows)
    checks.append(
        check("workflow_published", "ok", "workflow 已发布到 GitHub 默认分支。")
        if state["workflow_published"]
        else check("workflow_published", "block", "GitHub 默认分支还没有该 workflow。")
    )

    secrets_code, secrets = read_json_command(
        [gh, "secret", "list", "--repo", canonical_repo, "--json", "name"], root
    )
    if secrets_code == 0 and isinstance(secrets, list):
        state["secret_names"] = {item.get("name") for item in secrets if item.get("name")}

    variables_code, variables = read_json_command(
        [gh, "variable", "list", "--repo", canonical_repo, "--json", "name,value"], root
    )
    if variables_code == 0 and isinstance(variables, list):
        state["variables"] = {item.get("name"): item.get("value", "") for item in variables if item.get("name")}

    checks.append(
        check("github_settings", "ok", "已读取 GitHub Secrets/Variables 名称（未读取 Secret 值）。")
        if secrets_code == 0 and variables_code == 0
        else check("github_settings", "warn", "无法完整读取 GitHub Secrets/Variables 列表。")
    )
    return checks, state


def checks_by_name(checks: list[dict]) -> dict[str, dict]:
    return {item["name"]: item for item in checks}


def evaluate_target(target: str, checks: list[dict], github_state: dict, require_email: bool) -> tuple[str, list[str]]:
    indexed = checks_by_name(checks)
    reasons = []

    def require_ok(*names: str) -> None:
        for name in names:
            item = indexed.get(name)
            if not item or item["status"] == "block":
                reasons.append(item["message"] if item else f"缺少检查项: {name}")

    if target == "manual":
        require_ok("python", "dependencies", "config", "data_dirs")
        if require_email:
            require_ok("smtp_local")
        return ("blocked", reasons) if reasons else ("ready", [])

    require_ok("config", "git_repo", "git_remote", "gh", "workflow_local", "workflow_tracked", "workflow_published")
    if require_email or target == "github-scheduled":
        missing = sorted(set(SMTP_NAMES) - set(github_state.get("secret_names", set())))
        if missing:
            reasons.append("GitHub 缺少邮件 Secrets: " + ", ".join(missing))

    if reasons:
        return "blocked", reasons
    if target == "github-mock":
        return "ready", []

    variables = github_state.get("variables", {})
    enabled = str(variables.get("DISPATCH_ENABLED", "false")).lower() == "true"
    if not enabled:
        return "disabled", ["DISPATCH_ENABLED 不是 true；定时任务会安全跳过。"]
    runner_configured = bool(str(variables.get("AGENT_RUNNER_CMD", "")).strip()) or (
        "AGENT_RUNNER_CMD" in set(github_state.get("secret_names", set()))
    )
    if not runner_configured:
        return "blocked", ["GitHub 尚未配置 AGENT_RUNNER_CMD。"]
    runner_command = str(variables.get("AGENT_RUNNER_CMD", "")).strip()
    if "openai_dispatch_agent.py" in runner_command and "OPENAI_API_KEY" not in set(
        github_state.get("secret_names", set())
    ):
        return "blocked", ["内置 OpenAI runner 已配置，但 GitHub 缺少 OPENAI_API_KEY Secret。"]
    return "ready", []


def build_report(root: Path, target: str, require_email: bool = False) -> dict:
    env = parse_env_file(root / ".env")
    checks = []

    fields = parse_config_fields(root / "config.md")
    checks.append(
        check("config", "ok", f"config.md 包含 {len(fields)} 个学术领域。")
        if fields
        else check("config", "block", "config.md 没有可解析的学术领域。")
    )

    github_state = {"repo": None, "secret_names": set(), "variables": {}, "workflow_published": False}
    if target == "manual":
        python_check, dependencies_check = inspect_python(root)
        checks.extend((python_check, dependencies_check))
        missing_dirs = [name for name in ("data", "archive") if not (root / name).is_dir()]
        checks.append(
            check("data_dirs", "ok", "data/ 和 archive/ 已存在。")
            if not missing_dirs
            else check("data_dirs", "block", "缺少目录: " + ", ".join(missing_dirs))
        )
        checks.append(
            check("env_file", "ok", ".env 存在；doctor 不会显示其中的值。")
            if (root / ".env").is_file()
            else check("env_file", "warn", ".env 不存在；不影响只生成 Markdown。")
        )
        missing_smtp = [name for name in SMTP_NAMES if not env.get(name)]
        checks.append(
            check("smtp_local", "ok", "本地 SMTP 配置完整（值已隐藏）。")
            if not missing_smtp
            else check(
                "smtp_local",
                "block" if require_email else "warn",
                "本地 SMTP 缺少: " + ", ".join(missing_smtp),
            )
        )
        checks.append(
            check("agent_runner_local", "ok", "本地 AGENT_RUNNER_CMD 已配置（值已隐藏）。")
            if env.get("AGENT_RUNNER_CMD")
            else check("agent_runner_local", "warn", "未配置本地 runner；仍可让当前交互式 agent 直接运行。")
        )
    else:
        github_checks, github_state = inspect_github(root)
        checks.extend(github_checks)
    readiness, reasons = evaluate_target(target, checks, github_state, require_email)
    return {
        "target": target,
        "readiness": readiness,
        "require_email": require_email,
        "project_root": str(root),
        "repository": github_state.get("repo"),
        "checks": checks,
        "reasons": reasons,
        "secrets_present": sorted(github_state.get("secret_names", set()) & set(SMTP_NAMES)),
        "variables_present": sorted(github_state.get("variables", {}).keys()),
    }


def print_human(report: dict) -> None:
    labels = {"ok": "OK", "warn": "WARN", "block": "BLOCK", "info": "INFO"}
    print("会打岔的学术速递 - 项目体检")
    print(f"目标: {report['target']}  结论: {report['readiness']}")
    for item in report["checks"]:
        print(f"[{labels.get(item['status'], item['status'].upper())}] {item['message']}")
    for reason in report["reasons"]:
        print(f"[NEXT] {reason}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="检查项目在手动或 GitHub 模式下是否可运行。")
    parser.add_argument("--target", choices=TARGETS, default="manual")
    parser.add_argument("--json", action="store_true", help="输出不含秘密值的 JSON。")
    parser.add_argument("--require-email", action="store_true", help="把邮件配置作为就绪条件。")
    parser.add_argument("--root", type=Path, default=WORK_DIR, help="项目根目录。")
    args = parser.parse_args(argv)

    report = build_report(args.root.resolve(), args.target, args.require_email)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)

    if report["readiness"] == "ready":
        return 0
    if report["readiness"] == "disabled":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
