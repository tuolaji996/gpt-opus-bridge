"""Regression tests from the independent integration review."""
import contextlib
import io
import json
import shlex
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import test_configure
import configure


class ConfigurationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_configure.TestConfigure()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = Path(self.fixture.temp_dir)
        self.pal = self.fixture._create_fake_pal()
        self.claude = self.fixture._create_fake_claude()
        self.settings = self.fixture._create_fake_settings()
        self.config = self.root / "codex.toml"
        self.output = self.root / "output"
        self.workspace = self.root / "workspace"

    def run_config(self, apply=True):
        args = [
            "configure.py", "--pal-dir", str(self.pal), "--claude", str(self.claude),
            "--workspace", str(self.workspace), "--model", "claude-opus-5-5",
            "--claude-settings", str(self.settings), "--codex-config", str(self.config),
            "--config-dir", str(self.output),
        ] + (["--apply"] if apply else [])
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", args), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = configure.main()
        return result, stdout.getvalue() + stderr.getvalue()

    def test_existing_empty_mcp_table_is_preserved(self):
        self.config.write_text('model="preserve"\n[mcp_servers]\n')
        self.assertEqual(self.run_config()[0], 0)
        d = tomllib.loads(self.config.read_text())
        self.assertEqual(d["model"], "preserve")
        self.assertIn("pal", d["mcp_servers"])

    def test_comment_mentioning_pal_does_not_block_setup(self):
        self.config.write_text('# [mcp_servers.pal] is an example, not active\n')
        self.assertEqual(self.run_config()[0], 0)

    def test_malformed_toml_is_nonmutating_and_private(self):
        content = '"sensitive-fixture" = [invalid\n'
        self.config.write_text(content)
        result, output = self.run_config()
        self.assertEqual(result, 1)
        self.assertNotIn("sensitive-fixture", output)
        self.assertEqual(self.config.read_text(), content)
        self.assertFalse(self.workspace.exists())
        self.assertFalse(self.output.exists())

    def test_inline_mcp_table_is_rejected_before_writes(self):
        self.config.write_text('mcp_servers = {}\n')
        result, _ = self.run_config()
        self.assertEqual(result, 1)
        self.assertFalse(self.output.exists())

    def test_quoted_pal_table_is_rejected_in_dry_run(self):
        self.config.write_text('[mcp_servers."pal"]\ncommand = "existing"\n')
        self.assertEqual(self.run_config(apply=False)[0], 1)
        self.assertFalse(self.output.exists())

    def test_output_must_not_overwrite_settings(self):
        self.config = self.settings
        original = self.settings.read_bytes()
        self.assertEqual(self.run_config()[0], 1)
        self.assertEqual(self.settings.read_bytes(), original)

    def test_bad_json_shape_is_private_and_nonmutating(self):
        self.settings.write_text(json.dumps(["private-fixture-value"]))
        result, output = self.run_config()
        self.assertEqual(result, 1)
        self.assertNotIn("private-fixture-value", output)
        self.assertFalse(self.output.exists())

    def test_apostrophe_and_backslash_paths_round_trip(self):
        self.workspace = self.root / "space apostrophe' backslash\\"
        self.assertEqual(self.run_config()[0], 0)
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data["mcp_servers"]["pal"]["cwd"], str(self.workspace))
        preset = json.loads((self.output / "claude.json").read_text())
        self.assertEqual(shlex.split(preset["command"]), [str(self.claude)])
