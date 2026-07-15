#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import run_daily
from scripts import push_email, tts_generate
from scripts.dispatch_config import parse_config_fields
from scripts.dispatch_markdown import parse_markdown
from scripts.dispatch_paths import ProjectPaths, resolve_dispatch_date, resolve_from_root

ROOT = Path(__file__).resolve().parents[1]

VALID_MD = """# 会打岔的学术速递 — 2026-07-15

> 测试引言。

## 一、Test Field
- **Portable Test** — Source
  摘要：验证可移植路径。
  为什么值得看：它覆盖非默认项目根目录。
  https://example.com/research

## DIVERSION
### ART
- **Portable Art** — Museum
  简介：测试艺术条目。
  https://example.com/art

### HUMOR
- 测试趣味内容。
"""


class PortableCoreTests(unittest.TestCase):
    def test_project_paths_centralize_artifact_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = ProjectPaths.from_root(tmp)
            artifacts = project.artifacts("2026-07-15")

        self.assertEqual(artifacts.markdown.name, "2026-07-15_学术速递.md")
        self.assertEqual(artifacts.audio.name, "2026-07-15_学术播报.mp3")
        self.assertEqual(artifacts.transcript.name, "2026-07-15_播报稿.txt")
        self.assertEqual(artifacts.validation.name, "2026-07-15_validation.json")
        self.assertEqual(resolve_from_root(Path("custom/out.md"), project.root, artifacts.markdown), project.root / "custom/out.md")

    def test_dispatch_date_is_validated_once(self):
        now = datetime(2026, 7, 15, 7, 0)
        self.assertEqual(resolve_dispatch_date(now=now), "2026-07-15")
        for value in ("2026-7-15", "2026-02-30", "not-a-date"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_dispatch_date(value)

    def test_config_parser_ignores_unrelated_numbered_tables(self):
        config_text = """# config

| 编号 | 名称 | 值 | 备注 |
| --- | --- | --- | --- |
| 9 | 不是领域 | ignored | 99 |

| 编号 | 领域 | 关键词范围 | 每日条数 |
| --- | --- | --- | --- |
| 1 | Systems | graph \\| network | 2-4 |
"""
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.md"
            config.write_text(config_text, encoding="utf-8")
            fields = parse_config_fields(config)

        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].name, "Systems")
        self.assertEqual(fields[0].keywords, "graph | network")
        self.assertEqual((fields[0].min_items, fields[0].max_items), (2, 4))

    def test_markdown_parser_accepts_english_heading_case(self):
        parsed = parse_markdown(VALID_MD)
        self.assertEqual([section["title"] for section in parsed["sections"]], ["Test Field"])
        self.assertEqual(len(parsed["arts"]), 1)
        self.assertEqual(len(parsed["humors"]), 1)

        not_art = VALID_MD.replace("### ART", "### PARTY TRICKS")
        self.assertEqual(parse_markdown(not_art)["arts"], [])

    def test_unix_virtualenv_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / ".venv" / "bin" / "python"
            candidate.parent.mkdir(parents=True)
            candidate.touch()
            calls = []

            def probe(command, **kwargs):
                calls.append(command)

            selected = run_daily.select_python(
                root,
                current_python="system-python",
                platform_name="posix",
                runner=probe,
            )

        self.assertEqual(selected, str(candidate))
        self.assertEqual(calls[0][0], str(candidate))

    def test_broken_virtualenv_falls_back_to_current_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / ".venv" / "bin" / "python"
            candidate.parent.mkdir(parents=True)
            candidate.touch()

            def failed_probe(command, **kwargs):
                raise OSError("broken interpreter")

            selected = run_daily.select_python(
                root,
                current_python="system-python",
                platform_name="posix",
                runner=failed_probe,
            )

        self.assertEqual(selected, "system-python")

    def test_tts_and_email_accept_an_arbitrary_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            markdown = data / "2026-07-15_学术速递.md"
            markdown.write_text(VALID_MD, encoding="utf-8")

            async def fake_synthesize(text, output_path, voice, rate):
                output_path.write_bytes(b"ID3-portable-test")

            with patch.object(tts_generate, "synthesize", new=fake_synthesize):
                tts_result = tts_generate.main(["2026-07-15", "--root", str(root)])

            with patch.object(push_email, "push_email", return_value=True) as sender:
                email_result = push_email.main(["2026-07-15", "--root", str(root), "--strict"])

            self.assertEqual(tts_result, 0)
            self.assertEqual(email_result, 0)
            self.assertTrue((data / "2026-07-15_学术播报.mp3").is_file())
            self.assertTrue((data / "2026-07-15_播报稿.txt").is_file())
            self.assertEqual(sender.call_args.args[3], markdown)

    def test_commands_are_importable_as_modules(self):
        modules = (
            "scripts.project_doctor",
            "scripts.run_agent_command",
            "scripts.tts_generate",
            "scripts.push_email",
            "scripts.validate_dispatch",
        )
        for module in modules:
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-m", module, "--help"],
                    cwd=ROOT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_mock_runner_can_target_a_separate_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.md").write_text(
                "| 编号 | 领域 | 关键词范围 | 每日条数 |\n"
                "| --- | --- | --- | --- |\n"
                "| 1 | Portable Field | portable | 1 |\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_agent_command.py"),
                    "2026-07-15",
                    "--root",
                    str(root),
                    "--mock",
                ],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            output = root / "data" / "2026-07-15_学术速递.md"
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("Portable Field", output.read_text(encoding="utf-8"))

    def test_unix_setup_uses_the_portable_entrypoints(self):
        setup_text = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("set -eu", setup_text)
        self.assertIn(".venv/bin/python", setup_text)
        self.assertIn(".env.example", setup_text)
        self.assertIn('project_doctor.py" --root "$ROOT" --target manual', setup_text)


if __name__ == "__main__":
    unittest.main()
