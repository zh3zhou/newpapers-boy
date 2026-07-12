#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env
from tts_generate import parse_markdown
from validate_dispatch import check_url, classify_http_status, validate_dispatch, validate_public_url


VALID_MD = """# 会打岔的学术速递 — 2026-07-04

> 测试引言。

## 一、复杂系统

- **Complex Systems Test** — arXiv
  摘要：这是一条复杂系统测试摘要。
  为什么值得看：它用于确认字段可配置后仍能解析。
  https://example.com/complex

## 二、AI4S / S4AI

- **AI4S Test** — arXiv
  摘要：这是一条 AI4S 测试摘要。
  为什么值得看：它用于确认斜杠字段名能被验证。
  https://example.com/ai4s

## ✦ 今日打岔 ✦

### 艺术一刻

- **Artwork Test** — Museum
  简介：这是一条艺术测试内容。
  https://example.com/art

### 会心一笑

- 测试趣味内容。
"""


CONFIG = """# config

| 编号 | 领域 | 关键词范围 | 每日条数 |
| --- | --- | --- | --- |
| 1 | 复杂系统 | complex systems | 1-2 |
| 2 | AI4S / S4AI | AI for Science | 1-2 |
"""


class DispatchContractTests(unittest.TestCase):
    def test_parser_handles_configurable_fields_and_diversion(self):
        parsed = parse_markdown(VALID_MD)
        self.assertEqual(parsed["date"], "2026-07-04")
        self.assertEqual([section["title"] for section in parsed["sections"]], ["复杂系统", "AI4S / S4AI"])
        self.assertEqual(len(parsed["sections"][0]["items"]), 1)
        self.assertEqual(len(parsed["arts"]), 1)
        self.assertEqual(len(parsed["humors"]), 1)

    def test_env_loader_prefers_process_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("SMTP_HOST=file.example\nTTS_RATE=-10%\n", encoding="utf-8")
            old_value = os.environ.get("SMTP_HOST")
            os.environ["SMTP_HOST"] = "env.example"
            try:
                env = load_env(root)
            finally:
                if old_value is None:
                    os.environ.pop("SMTP_HOST", None)
                else:
                    os.environ["SMTP_HOST"] = old_value

        self.assertEqual(env["SMTP_HOST"], "env.example")
        self.assertEqual(env["TTS_RATE"], "-10%")

    def test_validator_accepts_valid_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.md"
            md = root / "2026-07-04_学术速递.md"
            config.write_text(CONFIG, encoding="utf-8")
            md.write_text(VALID_MD, encoding="utf-8")

            report = validate_dispatch("2026-07-04", md, config, strict=True)

        self.assertEqual(report["errors"], [])
        self.assertEqual(report["url_count"], 3)

    def test_validator_rejects_missing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.md"
            config.write_text(CONFIG, encoding="utf-8")

            report = validate_dispatch("2026-07-04", root / "missing.md", config, strict=True)

        self.assertTrue(any("does not exist" in error for error in report["errors"]))

    def test_validator_rejects_malformed_sections_and_missing_links(self):
        bad_md = VALID_MD.replace("## 二、AI4S / S4AI", "## 二、其他领域")
        bad_md = bad_md.replace("  https://example.com/complex\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.md"
            md = root / "2026-07-04_学术速递.md"
            config.write_text(CONFIG, encoding="utf-8")
            md.write_text(bad_md, encoding="utf-8")

            report = validate_dispatch("2026-07-04", md, config, strict=True)

        self.assertTrue(any("missing configured section" in error for error in report["errors"]))
        self.assertTrue(any("missing a URL" in error for error in report["errors"]))

    def test_link_check_fails_clear_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.md"
            md = root / "2026-07-04_学术速递.md"
            config.write_text(CONFIG, encoding="utf-8")
            md.write_text(VALID_MD, encoding="utf-8")

            report = validate_dispatch(
                "2026-07-04",
                md,
                config,
                strict=True,
                check_links=True,
                link_checker=lambda url: classify_http_status(url, 404),
            )

        self.assertTrue(any("HTTP 404" in error for error in report["errors"]))
        self.assertEqual(len(report["links"]), 3)

    def test_link_check_warns_for_rate_limits_and_server_errors(self):
        statuses = iter((403, 429, 503))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.md"
            md = root / "2026-07-04_学术速递.md"
            config.write_text(CONFIG, encoding="utf-8")
            md.write_text(VALID_MD, encoding="utf-8")

            report = validate_dispatch(
                "2026-07-04",
                md,
                config,
                strict=True,
                check_links=True,
                link_checker=lambda url: classify_http_status(url, next(statuses)),
            )

        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["warnings"]), 3)

    def test_link_check_rejects_private_and_local_targets(self):
        for url in ("http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "http://localhost/"):
            level, _ = validate_public_url(url)
            self.assertEqual(level, "error", url)

    def test_link_check_accepts_public_dns_result(self):
        def public_resolver(host, port, type):
            return [(2, type, 6, "", ("93.184.216.34", port))]

        level, _ = validate_public_url("https://example.com/", resolver=public_resolver)
        self.assertEqual(level, "ok")

    def test_dns_nxdomain_is_error_but_retry_is_warning(self):
        def nxdomain(host, port, type):
            raise socket.gaierror(socket.EAI_NONAME, "not found")

        def retry(host, port, type):
            raise socket.gaierror(socket.EAI_AGAIN, "try again")

        self.assertEqual(validate_public_url("https://missing.example/", resolver=nxdomain)[0], "error")
        self.assertEqual(validate_public_url("https://retry.example/", resolver=retry)[0], "warning")

    def test_link_transport_connects_to_the_validated_ip(self):
        calls = {"resolver": 0, "ip": None}

        def resolver(host, port, type):
            calls["resolver"] += 1
            return [(2, type, 6, "", ("93.184.216.34", port))]

        class Response:
            status = 200

            @staticmethod
            def getheader(name):
                return None

            @staticmethod
            def read(size):
                return b""

        class Connection:
            def request(self, method, target, headers):
                pass

            @staticmethod
            def getresponse():
                return Response()

            @staticmethod
            def close():
                pass

        def builder(parsed, ip, timeout):
            calls["ip"] = ip
            return Connection()

        result = check_url("https://example.com/", resolver=resolver, connection_builder=builder)
        self.assertEqual(result["level"], "ok")
        self.assertEqual(calls["resolver"], 1)
        self.assertEqual(calls["ip"], "93.184.216.34")

    def test_redirect_to_private_address_is_rejected(self):
        def resolver(host, port, type):
            return [(2, type, 6, "", ("93.184.216.34", port))]

        class Response:
            status = 302

            @staticmethod
            def getheader(name):
                return "http://127.0.0.1/private" if name == "Location" else None

            @staticmethod
            def read(size):
                return b""

        class Connection:
            def request(self, method, target, headers):
                pass

            @staticmethod
            def getresponse():
                return Response()

            @staticmethod
            def close():
                pass

        result = check_url(
            "https://example.com/redirect",
            resolver=resolver,
            connection_builder=lambda parsed, ip, timeout: Connection(),
        )
        self.assertEqual(result["level"], "error")
        self.assertIn("private", result["message"])

    def test_strict_validator_checks_art_item_fields(self):
        bad_md = VALID_MD.replace("**Artwork Test** — Museum", "**Artwork Test**")
        bad_md = bad_md.replace("  简介：这是一条艺术测试内容。", "  介绍：这是一条艺术测试内容。")
        bad_md = bad_md.replace("  https://example.com/art\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.md"
            md = root / "2026-07-04_学术速递.md"
            config.write_text(CONFIG, encoding="utf-8")
            md.write_text(bad_md, encoding="utf-8")
            report = validate_dispatch("2026-07-04", md, config, strict=True)

        self.assertTrue(any("art item 1 is missing a source" in error for error in report["errors"]))
        self.assertTrue(any("art item 1 is missing 简介" in error for error in report["errors"]))
        self.assertTrue(any("art item 1 is missing a URL" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
