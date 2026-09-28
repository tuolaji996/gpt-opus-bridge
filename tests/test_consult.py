"""Offline checks for consultation result handling."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from consult import summarize


class ConsultationTests(unittest.TestCase):
    def payload(self):
        return {
            "status": "continuation_available",
            "content": "Bounded result",
            "metadata": {
                "model_used": "provider-opus-id",
                "return_code": 0,
                "is_error": False,
                "duration_seconds": 1,
                "raw": {"unnecessary": "private-debug-material"},
            },
        }

    def test_summary_excludes_raw_debug_metadata(self):
        answer = summarize(self.payload(), "provider-opus-id")
        self.assertEqual(answer["reply"], "Bounded result")
        self.assertNotIn("raw", answer)
        self.assertNotIn("private-debug-material", str(answer))

    def test_model_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize(self.payload(), "another-model")

    def test_absent_model_is_rejected(self):
        p = self.payload()
        del p["metadata"]["model_used"]
        with self.assertRaises(ValueError):
            summarize(p, "provider-opus-id")

    def test_provider_error_is_rejected(self):
        p = self.payload()
        p["metadata"]["is_error"] = True
        with self.assertRaises(ValueError):
            summarize(p, "provider-opus-id")

    def test_failed_cli_is_rejected(self):
        p = self.payload()
        p["metadata"]["return_code"] = 1
        with self.assertRaises(ValueError):
            summarize(p, "provider-opus-id")
