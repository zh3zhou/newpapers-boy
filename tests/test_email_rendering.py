#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from push_email import _inline_md, _md_to_html


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


if __name__ == "__main__":
    unittest.main()
