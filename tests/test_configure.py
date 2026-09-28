#!/usr/bin/env python3
"""Tests for configure.py"""

import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import configure


class TestConfigure(unittest.TestCase):
    """Test suite for configuration utility."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: self._cleanup_dir(Path(self.temp_dir)))

    def _cleanup_dir(self, path):
        """Recursively clean up directory."""
        if path.exists():
            for item in path.iterdir():
                if item.is_dir():
                    self._cleanup_dir(item)
                else:
                    item.unlink()
            path.rmdir()

    def _create_fake_pal(self):
        """Create fake PAL directory with actual required structure."""
        pal_dir = Path(self.temp_dir) / "pal"
        pal_dir.mkdir()

        # Create server.py with CLIHistoryContext
        server_py = pal_dir / "server.py"
        server_py.write_text('''
# Fake PAL server
class CLIHistoryContext:
    pass
''')

        # Create utils/model_context.py with CLIHistoryContext
        utils_dir = pal_dir / "utils"
        utils_dir.mkdir()
        model_context = utils_dir / "model_context.py"
        model_context.write_text('''
# Model context
class CLIHistoryContext:
    pass
''')

        # Create tools/clink.py with readOnlyHint False
        tools_dir = pal_dir / "tools"
        tools_dir.mkdir()
        clink_py = tools_dir / "clink.py"
        clink_py.write_text('''
# Clink tool
config = {"readOnlyHint": False}
''')

        # Create pyproject.toml with mcp<2
        pyproject = pal_dir / "pyproject.toml"
        pyproject.write_text('''[project]
name = "pal"
version = "1.0.0"
dependencies = [
    "mcp<2",
    "other-package==1.0"
]
''')

        # Create .venv/bin/python
        venv_bin = pal_dir / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        python_exe = venv_bin / "python"
        python_exe.write_text("#!/bin/bash\necho fake python")
        python_exe.chmod(0o755)

        return pal_dir

    def _create_fake_claude(self):
        """Create fake Claude executable."""
        claude_path = Path(self.temp_dir) / "claude"
        claude_path.write_text("#!/bin/bash\necho fake claude")
        claude_path.chmod(0o755)
        return claude_path

    def _create_fake_settings(self, with_creds=True):
        """Create fake Claude settings."""
        settings_path = Path(self.temp_dir) / "settings.json"
        settings = {
            "env": {
                "ANTHROPIC_BASE_URL": "https://api.example.com/v1"
            }
        }
        if with_creds:
            settings["env"]["ANTHROPIC_API_KEY"] = "sk-test-key"

        settings_path.write_text(json.dumps(settings))
        return settings_path

    def test_dry_run_no_mutations(self):
        """Test that dry run does not create files."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        # Run dry run
        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir)
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Verify no files were created
        self.assertFalse(config_dir.exists())
        self.assertFalse(workspace.exists())
        self.assertFalse(codex_config.exists())

    def test_real_schema_fields(self):
        """Test that generated config has correct PAL schema fields."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Verify claude.json has correct schema
        claude_config_path = config_dir / "claude.json"
        with open(claude_config_path) as f:
            config = json.load(f)

        # Required top-level fields
        self.assertEqual(config["name"], "claude")
        self.assertIn("command", config)
        self.assertIn("working_dir", config)
        self.assertEqual(config["timeout_seconds"], 240)
        self.assertIn("additional_args", config)
        self.assertIn("env", config)
        self.assertIn("roles", config)

        # Verify no role.command (roles should have prompt_path and role_args)
        for role_name, role_config in config["roles"].items():
            self.assertNotIn("command", role_config, f"Role {role_name} should not have command field")
            self.assertIn("prompt_path", role_config)
            self.assertIn("role_args", role_config)

        # Verify additional_args contains correct flags
        args = config["additional_args"]
        self.assertIn("--model", args)
        self.assertIn("--restricted", args)
        self.assertIn("--settings", args)
        self.assertIn("--strict-mcp-config", args)
        self.assertIn("--permission-mode", args)
        self.assertIn("acceptEdits", args)
        self.assertIn("--disable-slash-commands", args)

        # Verify forbidden args are not present
        args_str = " ".join(args)
        self.assertNotIn("--thinking-effort", args_str)
        self.assertNotIn("--allowed-tools", args_str)
        self.assertNotIn("--system-prompt-file", args_str)

        # Verify env has CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
        self.assertEqual(config["env"]["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"], "1")

    def test_parse_resulting_toml(self):
        """Test that resulting TOML is valid and parseable."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Parse resulting TOML
        with open(codex_config, "rb") as f:
            toml_data = tomllib.load(f)

        # Verify mcp_servers.pal exists and has correct structure
        self.assertIn("mcp_servers", toml_data)
        self.assertIn("pal", toml_data["mcp_servers"])

        pal_config = toml_data["mcp_servers"]["pal"]
        self.assertIn("command", pal_config)
        self.assertIn("cwd", pal_config)
        self.assertIn("enabled_tools", pal_config)
        self.assertEqual(pal_config["enabled_tools"], ["clink"])

    def test_exact_timeout_keys(self):
        """Test that TOML uses exact timeout key names (not seconds suffix)."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Parse TOML and check exact key names
        with open(codex_config, "rb") as f:
            toml_data = tomllib.load(f)

        pal_config = toml_data["mcp_servers"]["pal"]
        self.assertIn("startup_timeout_sec", pal_config)
        self.assertIn("tool_timeout_sec", pal_config)
        self.assertNotIn("startup_timeout_seconds", pal_config)
        self.assertNotIn("tool_timeout_seconds", pal_config)

    def test_failsafe_duplicate_no_file_changes(self):
        """Test that second apply refuses and makes no file changes."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        # First apply
        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]
        result = configure.main()
        self.assertEqual(result, 0)

        # Record file states
        codex_content_before = codex_config.read_text()
        codex_mtime_before = codex_config.stat().st_mtime

        # Second apply should fail
        result = configure.main()
        self.assertEqual(result, 1)

        # Verify no file changes occurred
        codex_content_after = codex_config.read_text()
        codex_mtime_after = codex_config.stat().st_mtime
        self.assertEqual(codex_content_before, codex_content_after)
        self.assertEqual(codex_mtime_before, codex_mtime_after)

    def test_launcher_uses_venv_python_unresolved(self):
        """Test that launcher uses .venv/bin/python not resolved system python."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Check launcher script
        launcher = config_dir / "launch-pal.sh"
        launcher_content = launcher.read_text()

        # Verify it uses .venv/bin/python path (not resolved)
        self.assertIn(".venv/bin/python", launcher_content)

        # Verify it doesn't use system python paths
        self.assertNotIn("/usr/bin/python", launcher_content)
        self.assertNotIn("/usr/local/bin/python", launcher_content)

    def test_settings_path_with_apostrophe(self):
        """Test settings path with apostrophe is properly quoted."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()

        # Create settings with apostrophe in path
        settings_dir = Path(self.temp_dir) / "user's settings"
        settings_dir.mkdir()
        settings_path = settings_dir / "settings.json"
        settings = {
            "env": {
                "ANTHROPIC_BASE_URL": "https://api.example.com/v1",
                "ANTHROPIC_API_KEY": "sk-test-key"
            }
        }
        settings_path.write_text(json.dumps(settings))

        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Verify config contains properly escaped path
        claude_config_path = config_dir / "claude.json"
        with open(claude_config_path) as f:
            config = json.load(f)

        # Settings path should be in additional_args
        args = config["additional_args"]
        settings_idx = args.index("--settings")
        settings_arg = args[settings_idx + 1]
        self.assertIn("user's settings", settings_arg)

    def test_control_character_rejection(self):
        """Test that paths with control characters including DEL are rejected."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()

        # Try workspace with newline
        workspace_with_newline = Path(self.temp_dir) / "work\nspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace_with_newline),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 1)

    def test_model_with_control_characters_rejected(self):
        """Test that model name with control characters is rejected."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude\x00opus",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 1)

    def test_empty_model_rejected(self):
        """Test that empty model name is rejected."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 1)

    def test_preserve_existing_codex_config(self):
        """Test that existing Codex config sections are preserved."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        # Create existing config with other sections
        existing_config = """# Existing Codex config
[gpt]
model = "gpt-4"

[providers.anthropic]
api_key = "sk-existing"

[mcp_servers.other]
command = "/usr/bin/other"
"""
        codex_config.parent.mkdir(parents=True, exist_ok=True)
        codex_config.write_text(existing_config)

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Parse TOML and verify existing content preserved
        with open(codex_config, "rb") as f:
            toml_data = tomllib.load(f)

        self.assertIn("gpt", toml_data)
        self.assertEqual(toml_data["gpt"]["model"], "gpt-4")
        self.assertIn("providers", toml_data)
        self.assertIn("anthropic", toml_data["providers"])
        self.assertIn("mcp_servers", toml_data)
        self.assertIn("other", toml_data["mcp_servers"])
        self.assertIn("pal", toml_data["mcp_servers"])

    def test_missing_credentials_refusal(self):
        """Test that missing credentials are refused without leaking secrets."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings(with_creds=False)
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 1)

    def test_url_with_userinfo_rejected(self):
        """Test that URL with userinfo is rejected."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = Path(self.temp_dir) / "settings.json"
        settings = {
            "env": {
                "ANTHROPIC_BASE_URL": "https://user:pass@api.example.com/v1",
                "ANTHROPIC_API_KEY": "sk-test-key"
            }
        }
        settings_path.write_text(json.dumps(settings))

        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 1)

    def test_backup_microsecond_timestamps(self):
        """Test that backups use microsecond timestamps for collision resistance."""
        pal_dir = self._create_fake_pal()
        claude_path = self._create_fake_claude()
        settings_path = self._create_fake_settings()
        workspace = Path(self.temp_dir) / "workspace"
        config_dir = Path(self.temp_dir) / "config"
        codex_config = Path(self.temp_dir) / "codex.toml"

        # Create existing file
        config_dir.mkdir(parents=True)
        (config_dir / "claude.json").write_text('{"old": "config"}')

        sys.argv = [
            "configure.py",
            "--pal-dir", str(pal_dir),
            "--claude", str(claude_path),
            "--workspace", str(workspace),
            "--model", "claude-opus-5",
            "--claude-settings", str(settings_path),
            "--codex-config", str(codex_config),
            "--config-dir", str(config_dir),
            "--apply"
        ]

        result = configure.main()
        self.assertEqual(result, 0)

        # Check backup directory name format
        backups_dir = config_dir / "backups"
        backup_dirs = list(backups_dir.iterdir())
        self.assertTrue(len(backup_dirs) > 0)

        # Backup dir should have format YYYYMMDD_HHMMSS_microseconds
        backup_name = backup_dirs[0].name
        self.assertRegex(backup_name, r'^\d{8}_\d{6}_\d{6}$')


if __name__ == "__main__":
    unittest.main()
