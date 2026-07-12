#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_github_actions.ps1"


class SetupScriptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_secret_stdin_is_written_as_exact_utf8_bytes(self):
        self.assertIn(
            "[System.IO.File]::WriteAllText($tempPath, $Value, [System.Text.UTF8Encoding]::new($false))",
            self.text,
        )
        self.assertIn("-RedirectStandardInput $tempPath", self.text)
        self.assertIn("Remove-Item -LiteralPath $tempPath", self.text)
        self.assertNotIn("$process.StandardInput", self.text)

    def test_secret_values_are_not_sent_through_powershell_pipeline(self):
        self.assertNotIn("$InputText | & $GhPath", self.text)
        self.assertNotIn('--body $dotEnv[$name]', self.text)


if __name__ == "__main__":
    unittest.main()
