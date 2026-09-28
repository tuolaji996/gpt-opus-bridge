#!/usr/bin/env python3
"""Configuration utility for GPT-led Claude Code delegation via PAL."""

import argparse
import json
import os
import re
import shlex
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


def validate_string_no_controls(value, name):
    """Reject strings with control characters or empty values."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{name} contains control characters")


def validate_path_chars(path_str):
    """Reject paths with control characters including DEL."""
    if any(ord(c) < 32 or ord(c) == 127 for c in path_str):
        raise ValueError(f"Path contains control characters")


def validate_pal_dir(pal_dir):
    """Validate PAL directory has required components."""
    server_py = pal_dir / "server.py"
    venv_python = pal_dir / ".venv" / "bin" / "python"
    tools_clink = pal_dir / "tools" / "clink.py"
    utils_model_context = pal_dir / "utils" / "model_context.py"
    pyproject = pal_dir / "pyproject.toml"

    if not server_py.is_file():
        raise ValueError(f"PAL directory missing server.py: {pal_dir}")
    if not venv_python.is_file() or not os.access(venv_python, os.X_OK):
        raise ValueError(f"PAL directory missing .venv/bin/python: {pal_dir}")

    # Check for CLIHistoryContext in server.py
    server_content = server_py.read_text()
    if "CLIHistoryContext" not in server_content:
        raise ValueError("PAL server.py missing required CLIHistoryContext")

    # Check for CLIHistoryContext in utils/model_context.py
    if not utils_model_context.is_file():
        raise ValueError(f"PAL directory missing utils/model_context.py: {pal_dir}")
    model_context_content = utils_model_context.read_text()
    if "CLIHistoryContext" not in model_context_content:
        raise ValueError("PAL utils/model_context.py missing required CLIHistoryContext")

    # Check for readOnlyHint False in tools/clink.py
    if not tools_clink.is_file():
        raise ValueError(f"PAL directory missing tools/clink.py: {pal_dir}")
    clink_content = tools_clink.read_text()
    if 'readOnlyHint": False' not in clink_content.replace("'", '"'):
        raise ValueError("PAL tools/clink.py missing readOnlyHint False")

    # Check mcp<2 in pyproject.toml [project].dependencies
    if not pyproject.is_file():
        raise ValueError(f"PAL directory missing pyproject.toml: {pal_dir}")

    with open(pyproject, "rb") as f:
        pyproject_data = tomllib.load(f)

    dependencies = pyproject_data.get("project", {}).get("dependencies", [])
    has_mcp_constraint = False
    for dep in dependencies:
        if isinstance(dep, str) and re.match(r"^mcp\s*[<>=!~]", dep):
            if re.search(r"<\s*2(?:\.0)?(?:\s*[,;]|$)", dep):
                has_mcp_constraint = True
                break

    if not has_mcp_constraint:
        raise ValueError("PAL pyproject.toml [project].dependencies must specify mcp<2")


def validate_claude_settings(settings_path):
    """Validate Claude settings has required provider configuration."""
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Claude settings file is not valid JSON")
    except OSError:
        raise ValueError("Cannot read Claude settings file")

    # Validate settings is an object
    if not isinstance(settings, dict):
        raise ValueError("Claude settings must be a JSON object")

    # Check for env object
    env = settings.get("env")
    if not isinstance(env, dict):
        raise ValueError("Claude settings must contain env object")

    base_url = env.get("ANTHROPIC_BASE_URL")
    if not base_url:
        raise ValueError("Claude settings missing env.ANTHROPIC_BASE_URL")

    # Validate URL structure
    try:
        parsed = urlsplit(base_url)
        if parsed.scheme != "https":
            raise ValueError("ANTHROPIC_BASE_URL must use https://")
        if not parsed.hostname:
            raise ValueError("ANTHROPIC_BASE_URL missing hostname")
        if parsed.username or parsed.password:
            raise ValueError("ANTHROPIC_BASE_URL must not contain userinfo")
    except Exception:
        raise ValueError("ANTHROPIC_BASE_URL is not a valid URL")

    # Check for credentials (validate privately)
    api_key = env.get("ANTHROPIC_API_KEY", "")
    auth_token = env.get("ANTHROPIC_AUTH_TOKEN", "")

    if not api_key and not auth_token:
        raise ValueError("Claude settings missing credentials in env")

    # Validate credential is nonempty string without exposing it
    cred = api_key or auth_token
    if not isinstance(cred, str) or not cred.strip():
        raise ValueError("Credential must be nonempty string")


def generate_claude_config(claude_path, workspace, model, settings_path, config_dir):
    """Generate claude.json configuration."""
    role_prompt_path = (config_dir / "role.txt").resolve()

    # Role configurations with correct PAL schema
    roles = {
        "default": {
            "prompt_path": str(role_prompt_path),
            "role_args": ["--effort", "medium", "--tools", "Read,Glob,Grep,Edit,Write"]
        },
        "codereviewer": {
            "prompt_path": str(role_prompt_path),
            "role_args": ["--effort", "medium", "--tools", "Read,Glob,Grep"]
        },
        "planner": {
            "prompt_path": str(role_prompt_path),
            "role_args": ["--effort", "high", "--tools", "Read,Glob,Grep"]
        },
        "implementer": {
            "prompt_path": str(role_prompt_path),
            "role_args": ["--effort", "high", "--tools", "Read,Glob,Grep,Edit,Write"]
        }
    }

    config = {
        "name": "claude",
        "command": shlex.quote(str(claude_path)),
        "working_dir": str(workspace.resolve()),
        "timeout_seconds": 240,
        "additional_args": [
            "--model", model,
            "--restricted",
            "--settings", str(settings_path.resolve()),
            "--strict-mcp-config",
            "--permission-mode", "acceptEdits",
            "--permission-prompts", "none",
            "--disable-slash-commands"
        ],
        "env": {
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
        },
        "roles": roles
    }

    return config


def generate_role_prompt():
    """Generate role.txt prompt."""
    return """You are Claude Code, operating through GPT delegation via PAL MCP.

Work only on bounded tasks assigned to you within the workspace. Report disagreements with evidence, blockers, and incomplete work. Do not delegate further or perform commits, pushes, deployments, external communications, or unrelated changes.

Never inspect credential files. Return a concise account of changed files and verification evidence. You have no shell tools: mark suggested shell checks NOT RUN so the GPT lead can run them independently.
"""


def generate_launcher(pal_dir, workspace, config_dir, claude_path):
    """Generate launch-pal.sh script."""
    home = str(Path.home())
    claude_dir = str(claude_path.parent.resolve())
    # Keep venv Python path unresolved at final symlink
    pal_python = str(pal_dir / ".venv" / "bin" / "python")
    server_py = str((pal_dir / "server.py").resolve())
    config_path = str((config_dir / "claude.json").resolve())
    workspace_abs = str(workspace.resolve())

    # Only CLI delegation and mandatory PAL utilities remain enabled
    disabled_tools = "chat,thinkdeep,planner,consensus,codereview,precommit,debug,secaudit,docgen,analyze,refactor,tracer,testgen,challenge,apilookup"

    script = f"""#!/bin/bash
set -e

# Set environment
export HOME={shlex.quote(home)}
export PATH={shlex.quote(claude_dir)}:/usr/local/bin:/usr/bin:/bin

# Clear provider/auth overrides
unset ANTHROPIC_API_KEY
unset ANTHROPIC_AUTH_TOKEN
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_API_URL
unset ANTHROPIC_MODEL
unset ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL
unset ANTHROPIC_DEFAULT_HAIKU_MODEL
unset ANTHROPIC_SMALL_FAST_MODEL
unset CLAUDE_CODE_OAUTH_TOKEN
unset CLAUDE_CODE_USE_BEDROCK
unset CLAUDE_CODE_USE_VERTEX
unset CLAUDE_CODE_USE_FOUNDRY
unset CLAUDE_CONFIG_DIR
unset OPENAI_API_KEY
unset OPENAI_BASE_URL
unset GEMINI_API_KEY
unset GOOGLE_API_KEY
unset XAI_API_KEY
unset DIAL_API_KEY
unset OPENROUTER_API_KEY
unset CUSTOM_API_URL
unset CUSTOM_API_KEY
unset AZURE_OPENAI_API_KEY

# PAL configuration
export CLI_CLIENTS_CONFIG_PATH={shlex.quote(config_path)}
export LOG_LEVEL=WARNING
export PAL_MCP_FORCE_ENV_OVERRIDE=false
export DISABLED_TOOLS={shlex.quote(disabled_tools)}

# Launch PAL
cd {shlex.quote(workspace_abs)}
exec {shlex.quote(pal_python)} {shlex.quote(server_py)}
"""
    return script


def update_codex_config(codex_config_path, launcher_path, workspace, config_dir, dry_run=False):
    """Validate the merged document before any writes; preserve existing text."""
    content = codex_config_path.read_text() if codex_config_path.exists() else ""
    try:
        existing = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        raise ValueError("Existing Codex configuration is not valid TOML") from None
    servers = existing.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("Codex mcp_servers must be a table")
    if "pal" in servers:
        raise ValueError("Codex config already has mcp_servers.pal - refusing to replace")
    merged = content + "\n\n" + f"""[mcp_servers.pal]
command = {json.dumps(str(launcher_path))}
cwd = {json.dumps(str(workspace))}
enabled_tools = ["clink"]
startup_timeout_sec = 30
tool_timeout_sec = 300
"""
    try:
        parsed = tomllib.loads(merged)
    except tomllib.TOMLDecodeError:
        raise ValueError("Cannot safely append PAL to this TOML layout") from None
    parsed["mcp_servers"].pop("pal")
    if "mcp_servers" not in existing:
        parsed.pop("mcp_servers")
    if parsed != existing:
        raise ValueError("Merged configuration would change existing settings")
    if dry_run:
        return merged, False
    backup_created = codex_config_path.exists()
    mode = codex_config_path.stat().st_mode & 0o777 if backup_created else 0o600
    if backup_created:
        backup_dir = config_dir / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_dir.mkdir(parents=True, mode=0o700)
        backup = backup_dir / "config.toml"
        backup.touch(mode=0o600)
        backup.write_text(content)
    codex_config_path.parent.mkdir(parents=True, exist_ok=True)
    if not codex_config_path.exists():
        codex_config_path.touch(mode=mode)
    codex_config_path.write_text(merged)
    codex_config_path.chmod(mode)
    return merged, backup_created


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Configure GPT-led Claude Code delegation via PAL"
    )
    parser.add_argument("--pal-dir", required=True, help="PAL directory path")
    parser.add_argument("--claude", required=True, help="Claude executable path")
    parser.add_argument("--workspace", required=True, help="Workspace directory path")
    parser.add_argument("--model", required=True, help="Claude model name")
    parser.add_argument(
        "--claude-settings",
        default="~/.claude/settings.json",
        help="Claude settings JSON path"
    )
    parser.add_argument(
        "--codex-config",
        default="~/.codex/config.toml",
        help="Codex config TOML path"
    )
    parser.add_argument(
        "--config-dir",
        default="~/.config/gpt-opus-bridge",
        help="Configuration output directory"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply configuration (default is dry run)"
    )

    args = parser.parse_args()

    try:
        # Validate model
        validate_string_no_controls(args.model, "Model")

        # Validate and resolve paths
        for path_arg in [args.pal_dir, args.claude, args.workspace,
                         args.claude_settings, args.codex_config, args.config_dir]:
            validate_path_chars(path_arg)

        pal_dir = Path(args.pal_dir).expanduser().resolve()
        # Keep Claude path absolute but don't resolve final symlink for updates
        claude_path = Path(os.path.abspath(Path(args.claude).expanduser()))
        workspace = Path(args.workspace).expanduser().resolve()
        settings_path = Path(args.claude_settings).expanduser().resolve()
        codex_config_path = Path(args.codex_config).expanduser().resolve()
        config_dir = Path(args.config_dir).expanduser().resolve()

        # Validate requirements
        validate_pal_dir(pal_dir)

        if not claude_path.is_file():
            raise ValueError(f"Claude executable not found: {claude_path}")

        if not os.access(claude_path, os.X_OK):
            raise ValueError(f"Claude path not executable: {claude_path}")

        if not settings_path.is_file():
            raise ValueError(f"Claude settings file not found: {settings_path}")

        validate_claude_settings(settings_path)

        # Generate configurations
        claude_config = generate_claude_config(
            claude_path, workspace, args.model, settings_path, config_dir
        )
        role_prompt = generate_role_prompt()
        launcher_script = generate_launcher(pal_dir, workspace, config_dir, claude_path)

        # Prepare output paths
        claude_config_path = config_dir / "claude.json"
        role_path = config_dir / "role.txt"
        launcher_path = config_dir / "launch-pal.sh"

        outputs = [claude_config_path, role_path, launcher_path, codex_config_path]
        protected = {settings_path, claude_path.resolve(), pal_dir / "server.py"}
        if any(p.resolve() in protected for p in outputs) or len({p.resolve() for p in outputs}) != 4:
            raise ValueError("Output paths must not overlap each other or input files")
        if any(p.is_symlink() or (p.exists() and not p.is_file()) for p in outputs):
            raise ValueError("Output paths must be regular files, not directories or symlinks")
        for directory in [workspace, config_dir, codex_config_path.parent]:
            if directory.exists() and not directory.is_dir():
                raise ValueError("A required output directory is occupied by a file")
        update_codex_config(codex_config_path, launcher_path, workspace, config_dir, dry_run=True)

        if args.apply:
            # Create workspace if needed
            workspace.mkdir(parents=True, exist_ok=True)

            # Create config directory
            config_dir.mkdir(parents=True, exist_ok=True)

            # Backup existing generated files with microsecond precision
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = config_dir / "backups" / timestamp
            for generated_file in [claude_config_path, role_path, launcher_path]:
                if generated_file.exists():
                    backup_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
                    backup_file = backup_dir / generated_file.name
                    backup_file.touch(mode=0o600)
                    backup_file.write_bytes(generated_file.read_bytes())

            # Write configuration files
            claude_config_path.write_text(json.dumps(claude_config, indent=2) + "\n")
            claude_config_path.chmod(0o600)
            role_path.write_text(role_prompt)
            role_path.chmod(0o600)
            launcher_path.write_text(launcher_script)
            launcher_path.chmod(0o700)

            # Update Codex config
            codex_content, backup_created = update_codex_config(
                codex_config_path, launcher_path, workspace, config_dir, dry_run=False
            )

            print(f"Configuration applied successfully")
            print(f"Generated: {claude_config_path}")
            print(f"Generated: {role_path}")
            print(f"Generated: {launcher_path}")
            print(f"Updated: {codex_config_path}")
        else:
            # Dry run - validate only
            codex_content, _ = update_codex_config(
                codex_config_path, launcher_path, workspace, config_dir, dry_run=True
            )

            print("Dry run - no files created")
            print(f"Would generate: {claude_config_path}")
            print(f"Would generate: {role_path}")
            print(f"Would generate: {launcher_path}")
            print(f"Would update: {codex_config_path}")
            print(f"Selected model: {args.model}")

        return 0

    except tomllib.TOMLDecodeError:
        print("Configuration failed: invalid TOML input", file=sys.stderr)
        return 1
    except ValueError as e:
        # Generic error for validation failures (don't expose credential data)
        print(f"Configuration failed: {e}", file=sys.stderr)
        return 1
    except Exception:
        print("Configuration failed: check paths, permissions, and input formats", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
