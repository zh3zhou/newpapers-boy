#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-dispatch.yml"


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.generate, cls.deliver = cls.text.split("\n  deliver:\n", 1)

    def test_schedule_requires_explicit_enable(self):
        self.assertIn("vars.DISPATCH_ENABLED == 'true'", self.generate)

    def test_generate_has_no_smtp_environment(self):
        for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO"):
            self.assertNotIn(name, self.generate)

    def test_delivery_keeps_tts_and_email_separate(self):
        self.assertIn('run_daily.py "$DISPATCH_DATE" --skip-email', self.deliver)
        self.assertIn('push_email.py "$DISPATCH_DATE" --strict', self.deliver)
        self.assertIn("needs.generate.outputs.send_email == 'true'", self.deliver)

    def test_generate_uses_strict_link_validation(self):
        self.assertIn("--strict", self.generate)
        self.assertIn("--check-links", self.generate)


if __name__ == "__main__":
    unittest.main()
