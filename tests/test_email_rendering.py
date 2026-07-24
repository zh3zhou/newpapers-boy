#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from push_email import _inline_md, _md_to_html, push_failure_email


class EmailRenderingTests(unittest.TestCase):
    def test_raw_html_is_escaped(self):
        rendered = _md_to_html("<img src=x onerror=alert(1)>")
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)

    def test_non_http_markdown_link_is_not_activated(self):
        rendered = _inline_md("[click](javascript:alert(1))")
        self.assertNotIn("href=", rendered)

    def test_http_link_escapes_attribute_characters(self):
        rendered = _inline_md("[source](https://example.com/?a=1&b=2)")
        self.assertIn('href="https://example.com/?a=1&amp;b=2"', rendered)

    def test_failure_notice_is_sanitized_and_has_no_attachment(self):
        captured = {}

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                pass

            def login(self, *args):
                pass

            def sendmail(self, sender, recipients, message):
                captured["message"] = message

            def quit(self):
                pass

        env = {
            "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
            "SMTP_USER": "sender@example.com", "SMTP_PASS": "secret",
            "MAIL_TO": "reader@example.com",
        }
        result = {}
        with patch("smtplib.SMTP_SSL", FakeSMTP):
            ok = push_failure_email(
                env, "2026-07-24", "ready_gate_failed",
                r"missing E:\private\dispatch\data\file.md", result=result,
            )
        self.assertTrue(ok)
        self.assertIn("Message-ID:", captured["message"])
        self.assertNotIn("Content-Disposition: attachment", captured["message"])
        self.assertNotIn(r"E:\private", captured["message"])
        self.assertEqual(result["status"], "failure_notified")


if __name__ == "__main__":
    unittest.main()
