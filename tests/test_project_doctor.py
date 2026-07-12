#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from project_doctor import SMTP_NAMES, build_report, check, evaluate_target, inspect_python


BASE_CHECKS = [
    check("python", "ok", "python ok"),
    check("dependencies", "ok", "dependencies ok"),
    check("config", "ok", "config ok"),
    check("data_dirs", "ok", "dirs ok"),
    check("smtp_local", "ok", "smtp ok"),
    check("git_repo", "ok", "git ok"),
    check("git_remote", "ok", "remote ok"),
    check("gh", "ok", "gh ok"),
    check("workflow_local", "ok", "workflow local"),
    check("workflow_tracked", "ok", "workflow tracked"),
    check("workflow_published", "ok", "workflow published"),
]


class ProjectDoctorTests(unittest.TestCase):
    def test_target_states(self):
        state = {"secret_names": set(SMTP_NAMES), "variables": {"DISPATCH_ENABLED": "false"}}
        self.assertEqual(evaluate_target("manual", BASE_CHECKS, state, False)[0], "ready")
        self.assertEqual(evaluate_target("github-mock", BASE_CHECKS, state, True)[0], "ready")
        self.assertEqual(evaluate_target("github-scheduled", BASE_CHECKS, state, True)[0], "disabled")

        state["variables"] = {"DISPATCH_ENABLED": "true", "AGENT_RUNNER_CMD": "agent run"}
        self.assertEqual(evaluate_target("github-scheduled", BASE_CHECKS, state, True)[0], "ready")

    def test_openai_runner_requires_its_provider_secret(self):
        state = {"secret_names": set(SMTP_NAMES), "variables": {}}
        state["variables"] = {
            "DISPATCH_ENABLED": "true",
            "AGENT_RUNNER_CMD": "python scripts/openai_dispatch_agent.py",
        }
        readiness, reasons = evaluate_target("github-scheduled", BASE_CHECKS, state, True)
        self.assertEqual(readiness, "blocked")
        self.assertIn("OPENAI_API_KEY", reasons[0])
        state["secret_names"].add("OPENAI_API_KEY")
        self.assertEqual(evaluate_target("github-scheduled", BASE_CHECKS, state, True)[0], "ready")

        state["variables"] = {"DISPATCH_ENABLED": "true"}
        state["secret_names"].add("AGENT_RUNNER_CMD")
        self.assertEqual(evaluate_target("github-scheduled", BASE_CHECKS, state, True)[0], "ready")

    def test_missing_remote_secret_blocks_email_mock(self):
        state = {"secret_names": set(), "variables": {}}
        readiness, reasons = evaluate_target("github-mock", BASE_CHECKS, state, True)
        self.assertEqual(readiness, "blocked")
        self.assertTrue(any("SMTP_PASS" in reason for reason in reasons))

    def test_json_report_never_contains_env_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "archive").mkdir()
            (root / "config.md").write_text(
                "| 编号 | 领域 | 关键词范围 | 每日条数 |\n| --- | --- | --- | --- |\n| 1 | 测试 | test | 1 |\n",
                encoding="utf-8",
            )
            (root / ".env").write_text(
                "SMTP_HOST=smtp.example.com\nSMTP_PORT=465\nSMTP_USER=private@example.com\n"
                "SMTP_PASS=super-secret-password\nMAIL_TO=private@example.com\n",
                encoding="utf-8",
            )
            github_state = {
                "repo": "owner/repo",
                "secret_names": set(SMTP_NAMES),
                "variables": {"DISPATCH_ENABLED": "false"},
                "workflow_published": True,
            }
            with patch("project_doctor.inspect_python") as python_check, patch(
                "project_doctor.inspect_github"
            ) as github_check:
                python_check.return_value = (
                    check("python", "ok", "python ok"),
                    check("dependencies", "ok", "deps ok"),
                )
                github_check.return_value = (BASE_CHECKS[5:], github_state)
                report = build_report(root, "manual", require_email=True)

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("super-secret-password", serialized)
        self.assertNotIn("private@example.com", serialized)

    def test_manual_target_does_not_probe_github(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "archive").mkdir()
            (root / "config.md").write_text(
                "| 编号 | 领域 | 关键词范围 | 每日条数 |\n| --- | --- | --- | --- |\n| 1 | 测试 | test | 1 |\n",
                encoding="utf-8",
            )
            with patch("project_doctor.inspect_python") as python_check, patch(
                "project_doctor.inspect_github"
            ) as github_check:
                python_check.return_value = (
                    check("python", "ok", "python ok"),
                    check("dependencies", "ok", "deps ok"),
                )
                report = build_report(root, "manual")

        github_check.assert_not_called()
        self.assertEqual(report["readiness"], "ready")

    def test_python_probe_rejects_false_windows_alias(self):
        with patch("project_doctor.python_candidates", return_value=["fake-python"]), patch(
            "project_doctor.run_command", return_value=(0, "")
        ):
            python_check, dependency_check = inspect_python(ROOT)

        self.assertEqual(python_check["status"], "block")
        self.assertEqual(dependency_check["status"], "block")


if __name__ == "__main__":
    unittest.main()
