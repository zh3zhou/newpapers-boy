from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = (ROOT / ".github" / "workflows" / "prepare-dispatch.yml").read_text(encoding="utf-8")
DELIVER = (ROOT / ".github" / "workflows" / "deliver-dispatch.yml").read_text(encoding="utf-8")


class WorkflowContractTests(unittest.TestCase):
    def test_schedules_are_explicit_utc_times(self):
        self.assertIn('cron: "20 22 * * *"', PREPARE)
        self.assertIn('cron: "0 23 * * *"', DELIVER)

    def test_schedules_require_explicit_enable(self):
        self.assertIn("vars.DISPATCH_ENABLED == 'true'", PREPARE)
        self.assertIn("vars.DISPATCH_ENABLED == 'true'", DELIVER)

    def test_prepare_has_no_smtp_secrets(self):
        for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO"):
            self.assertNotIn(name, PREPARE)

    def test_prepare_seals_and_deliver_rechecks(self):
        self.assertIn("finalize_dispatch.py", PREPARE)
        self.assertIn("deliver_ready.py", DELIVER)
        self.assertIn("dispatch-ready-${{ steps.metadata.outputs.date }}", PREPARE)
        self.assertIn("--name \"dispatch-ready-${{ steps.metadata.outputs.date }}\"", DELIVER)

    def test_deliver_uses_successful_default_branch_prepare_run(self):
        self.assertIn("--workflow prepare-dispatch.yml", DELIVER)
        self.assertIn("--branch \"$DEFAULT_BRANCH\"", DELIVER)
        self.assertIn("--status success", DELIVER)


if __name__ == "__main__":
    unittest.main()
