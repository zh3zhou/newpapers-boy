from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.artifact_contract import atomic_write_json, build_ready_manifest, verify_ready_manifest
from scripts.content_history import history_findings
from scripts.deliver_ready import main as deliver_main
from scripts.dispatch_config import load_dispatch_config, validate_config_data


def valid_config() -> dict:
    return {
        "schemaVersion": 1,
        "content": {
            "academicFields": [{"name": "Systems", "keywords": ["systems"], "items": {"min": 1, "max": 2}}],
            "academicSources": {},
            "art": {"targetItems": 5, "minimumDistinctSources": 3, "maximumItemsPerSource": 2},
        },
        "schedule": {"prepareAt": "06:20", "deliverAt": "07:00"},
    }


class ConfigContractTests(unittest.TestCase):
    def test_json_is_preferred_and_art_default_is_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dispatch.config.json").write_text(json.dumps(valid_config()), encoding="utf-8")
            (root / "config.md").write_text("| 领域 | 每日条数 |\n", encoding="utf-8")
            config = load_dispatch_config(root / "dispatch.config.json")
            self.assertFalse(config.legacy)
            self.assertEqual(config.art["targetItems"], 5)

    def test_invalid_time_and_source_rules_are_rejected(self):
        data = valid_config()
        data["schedule"]["prepareAt"] = "25:00"
        data["content"]["art"]["minimumDistinctSources"] = 6
        errors = validate_config_data(data)
        self.assertTrue(any("prepareAt" in item for item in errors))
        self.assertTrue(any("cannot exceed" in item for item in errors))

    def test_environment_override_precedes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dispatch.config.json"
            path.write_text(json.dumps(valid_config()), encoding="utf-8")
            config = load_dispatch_config(path, environ={"DISPATCH_ART_TARGET": "7"})
            self.assertEqual(config.art["targetItems"], 7)

    def test_lock_has_exact_python39_and_modern_variants(self):
        lock = (Path(__file__).resolve().parents[1] / "requirements.lock.txt").read_text(encoding="utf-8")
        self.assertIn('aiohappyeyeballs==2.6.1; python_version < "3.10"', lock)
        self.assertIn('aiohappyeyeballs==2.7.1; python_version >= "3.10"', lock)


class HistoryContractTests(unittest.TestCase):
    def test_thirty_day_duplicate_and_seven_day_concentration(self):
        entries = [{
            "date": "2026-07-24", "kind": "academic", "section": "Systems",
            "title": "Same", "normalizedTitle": "same", "url": "https://arxiv.org/x", "domain": "arxiv.org",
        }]
        history = [{
            "date": "2026-07-01", "kind": "academic", "section": "Systems",
            "title": "Same", "normalizedTitle": "same", "url": "https://other.example/x", "domain": "arxiv.org",
        }]
        findings = history_findings(entries, history, "2026-07-24")
        self.assertEqual(len(findings["duplicates"]), 1)
        self.assertTrue(any("only one source domain" in item for item in findings["warnings"]))


class ArtifactContractTests(unittest.TestCase):
    def test_manifest_detects_tamper_and_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "data" / "item.txt"
            artifact.parent.mkdir()
            artifact.write_text("sealed", encoding="utf-8")
            manifest = build_ready_manifest(
                "2026-07-24", root, {"markdown": artifact},
                max_age_minutes=60, summary={}, run_id="run-1",
            )
            manifest_path = root / "data" / "2026-07-24_ready.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            _, errors = verify_ready_manifest(manifest_path, root, "2026-07-24")
            self.assertEqual(errors, [])
            artifact.write_text("tampered", encoding="utf-8")
            _, errors = verify_ready_manifest(manifest_path, root, "2026-07-24")
            self.assertTrue(any("integrity mismatch" in item for item in errors))
            artifact.write_text("sealed", encoding="utf-8")
            future = datetime.now(timezone.utc) + timedelta(hours=2)
            _, errors = verify_ready_manifest(manifest_path, root, "2026-07-24", now=future)
            self.assertIn("ready manifest has expired", errors)

    def test_delivery_writes_receipt_and_blocks_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            files = {
                "markdown": data / "2026-07-24_学术速递.md",
                "audio": data / "2026-07-24_学术播报.mp3",
                "transcript": data / "2026-07-24_播报稿.txt",
                "validation": data / "2026-07-24_validation.json",
            }
            files["markdown"].write_text("# Dispatch", encoding="utf-8")
            files["audio"].write_bytes(b"mp3")
            files["transcript"].write_text("speech", encoding="utf-8")
            files["validation"].write_text("{}", encoding="utf-8")
            manifest = build_ready_manifest(
                "2026-07-24", root, files, max_age_minutes=60, summary={}, run_id="run-1",
            )
            atomic_write_json(data / "2026-07-24_ready.json", manifest)

            def fake_send(*args, result=None, **kwargs):
                result.update({"status": "sent", "messageId": "<test@local>"})
                return True

            with patch("scripts.deliver_ready.push_email", side_effect=fake_send):
                first = deliver_main(["2026-07-24", "--root", str(root)])
            second = deliver_main([
                "2026-07-24", "--root", str(root), "--no-failure-notification",
            ])
            self.assertEqual(first, 0)
            self.assertEqual(second, 2)
            receipt = json.loads((data / "2026-07-24_sent.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["messageId"], "<test@local>")


if __name__ == "__main__":
    unittest.main()
