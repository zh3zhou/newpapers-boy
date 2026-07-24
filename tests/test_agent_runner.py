#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_agent_command.py"
FAKE_AGENT = ROOT / "tests" / "fixtures" / "fake_agent.py"


class AgentRunnerIntegrationTests(unittest.TestCase):
    def run_fake(self, mode: str, preexisting: bool = False):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        output = root / "dispatch.md"
        log = root / "agent.log"
        observed = root / "observed.json"
        if preexisting:
            output.write_text("# stale output\n", encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "AGENT_RUNNER_CMD": f'"{sys.executable}" "{FAKE_AGENT}" {mode}',
                "AGENT_ENV_ALLOWLIST": "FAKE_OBSERVED_ENV",
                "FAKE_OBSERVED_ENV": str(observed),
                "OPENAI_API_KEY": "provider-secret",
                "SMTP_PASS": "mail-secret",
                "MAIL_TO": "private@example.com",
            }
        )
        result = subprocess.run(
            [sys.executable, str(RUNNER), "2026-07-12", "--output", str(output), "--log", str(log)],
            cwd=str(ROOT),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return temp, root, output, log, observed, result

    def test_runner_passes_contract_but_not_smtp(self):
        temp, _, output, _, observed, result = self.run_fake("success")
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(output.exists())
        captured = json.loads(observed.read_text(encoding="utf-8"))
        self.assertFalse(captured["smtp_present"])
        self.assertFalse(captured["mail_present"])
        self.assertTrue(captured["provider_present"])
        self.assertEqual(captured["date"], "2026-07-12")
        self.assertEqual(captured["config"], "dispatch.config.json")
        self.assertEqual(captured["mode"], "local")
        self.assertEqual(Path(captured["project_root"]), ROOT)
        self.assertEqual(Path(captured["cwd"]), ROOT)
        self.assertNotEqual(Path(captured["output"]), output)

    def test_runner_preserves_nonzero_exit(self):
        temp, _, _, _, _, result = self.run_fake("fail")
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 7)

    def test_runner_rejects_missing_output(self):
        temp, _, _, _, _, result = self.run_fake("missing")
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 3)

    def test_runner_rejects_stale_preexisting_output(self):
        temp, _, output, _, _, result = self.run_fake("missing", preexisting=True)
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(output.read_text(encoding="utf-8"), "# stale output\n")

    def test_runner_rejects_non_utf8_output(self):
        temp, _, _, _, _, result = self.run_fake("invalid")
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 4)

    def test_runner_rejects_empty_output(self):
        temp, _, _, _, _, result = self.run_fake("empty")
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 5)

    def test_runner_redacts_provider_secret_from_log(self):
        temp, _, _, log, _, result = self.run_fake("leak")
        self.addCleanup(temp.cleanup)
        self.assertEqual(result.returncode, 0, result.stdout)
        log_text = log.read_text(encoding="utf-8")
        self.assertNotIn("provider-secret", log_text)
        self.assertIn("***REDACTED***", log_text)


if __name__ == "__main__":
    unittest.main()
