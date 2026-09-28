# gpt-opus-bridge

**Keep GPT/Codex in charge. Delegate bounded work to Claude Opus through PAL and the real Claude Code CLI.**

This project packages a working local delegation setup for the Codex desktop app. GPT plans, defines acceptance criteria, assigns work to Claude, reviews the changes, runs checks, and integrates the result. Claude uses your existing CC Switch-managed provider configuration.

The reference setup requests **claude-opus-5-5** through Sui-Xiang (随想). The model ID must be supported by your provider. This project neither supplies API credentials nor verifies the provider's underlying model identity.

~~~mermaid
flowchart LR
    U[You in Codex] --> G[GPT lead]
    G --> P[PAL clink]
    P --> C[Claude Code CLI]
    C --> S[Existing CC Switch provider]
    S --> C
    C --> G
    G --> V[Review, test, and integrate]
~~~

## What works

- Real Claude Code calls through PAL's clink tool.
- Explicit model selection, with no configured fallback model.
- Separate read-only and editing roles.
- A designated workspace and a limited set of Claude file tools.
- Existing credentials read from Claude settings, without copying them into PAL.
- An optional local MCP client for installations where PAL is not exposed in the active GUI chat.
- GPT-led review and verification after delegated work.

**What this project does not claim:** automatic changes to an active GPT turn's reasoning effort, independent verification of a provider's backend model, or guaranteed PAL discovery in every Codex desktop version.

## Status and requirements

The reference installation was tested on Ubuntu 26.04 x86_64 with Claude Code 2.1.274, PAL 9.8.2, Python 3.14.4, and MCP Python SDK 1.30.0. The configuration utility requires Python 3.11 or newer. Other operating systems and version combinations have not been validated.

Install these separately:

- [Codex](https://developers.openai.com/codex/app/) with an existing working login/provider.
- [Claude Code](https://github.com/anthropics/claude-code) using its supported native installer.
- [CC Switch](https://github.com/farion1231/cc-switch), with your intended Claude provider already active.
- Python 3.11+, Git, and [uv](https://docs.astral.sh/uv/getting-started/installation/).

The selected Claude Code version must support --restricted, --effort, and the other flags shown by claude --help. The bridge does not initiate Anthropic OAuth, change your provider, or downgrade Claude Code based on provider marketing claims.

## Setup

### 1. Confirm the existing Claude route

In CC Switch, select the intended **Claude** provider. Keep Codex's provider unchanged. The utility checks that your Claude settings include a provider URL and an API key or auth token; it does not print those credentials.

This version targets CC Switch's **direct Claude settings** mode. Local proxy mode and alternate cloud backends are not validated. Configure missing credentials in CC Switch itself, never in a prompt or a GitHub file.

### 2. Install the pinned PAL release

~~~bash
git clone https://github.com/tuolaji996/gpt-opus-bridge.git
cd gpt-opus-bridge

git clone --branch v9.8.2 --depth 1 \
  https://github.com/BeehiveInnovations/pal-mcp-server.git \
  "$HOME/.local/share/pal-mcp-server"

git -C "$HOME/.local/share/pal-mcp-server" rev-parse HEAD
# Expected: fa78edca0b6bc04ab00ddf5694d855f1b946b87d

git -C "$HOME/.local/share/pal-mcp-server" apply --check \
  "$PWD/patches/pal-9.8.2-clink-only.patch"
git -C "$HOME/.local/share/pal-mcp-server" apply \
  "$PWD/patches/pal-9.8.2-clink-only.patch"

uv venv --python python3 "$HOME/.local/share/pal-mcp-server/.venv"
uv pip install \
  --python "$HOME/.local/share/pal-mcp-server/.venv/bin/python" \
  -e "$HOME/.local/share/pal-mcp-server"
~~~

If PAL is already installed, inspect that installation first. Also inspect any ~/.pal/cli_clients overrides and any PAL .env file: they can change client routing or enable API providers. Do not overwrite existing modifications or apply the patch twice.

The patch allows a CLI-only PAL instance to start without unrelated API credentials, gives continuation history a bounded local text budget, corrects the clink permission annotation, constrains MCP to the compatible 1.x API, and removes the unused Codex/Gemini presets. See [the implementation article](docs/how-it-works.md).

### 3. Preview and apply the configuration

Set the arguments to your actual paths and provider-supported model ID. The command below is a **dry run**:

~~~bash
python3 scripts/configure.py \
  --pal-dir "$HOME/.local/share/pal-mcp-server" \
  --claude "$HOME/.local/bin/claude" \
  --workspace "$HOME/Documents/opus-workspace" \
  --model claude-opus-5-5
~~~

Add --apply to write the configuration. The utility backs up existing files before editing, appends a pal MCP entry, and preserves your selected GPT model, reasoning default, existing MCP servers, and provider settings. It refuses to replace an existing pal entry.

By default it reads ~/.claude/settings.json, edits ~/.codex/config.toml, and writes bridge files under ~/.config/gpt-opus-bridge. Override these with --claude-settings, --codex-config, and --config-dir when necessary. If you use CODEX_HOME, explicitly pass its config.toml through --codex-config.

### 4. Use the workflow

See [the delegation instructions](docs/delegation-workflow.md). Start with:

> Plan this task and define acceptance criteria. Use PAL clink with cli_name=claude to delegate a bounded part to Opus. Review its changes and run the relevant checks yourself. Keep trivial work local.

Claude works in the configured staging workspace. GPT copies only the necessary files there, assigns exclusive file ownership, reviews the result, and integrates accepted changes into the authorized target repository.

| PAL role | Claude effort | Tools |
|---|---|---|
| codereviewer | medium | Read, Glob, Grep |
| planner | high | Read, Glob, Grep |
| default | medium | Read, Glob, Grep, Edit, Write |
| implementer | high | Read, Glob, Grep, Edit, Write |

Claude has no shell or external MCP tools through these presets. GPT runs tests. No role authorizes commits, pushes, deployments, or unrelated external actions.

## When the GUI does not expose PAL

A saved MCP entry does not prove that the active GUI chat has loaded it. Check the chat's actual tool catalog.

You can test or use the same PAL server through the local MCP client without restarting the desktop app:

~~~bash
"$HOME/.local/share/pal-mcp-server/.venv/bin/python" scripts/consult.py \
  --launcher "$HOME/.config/gpt-opus-bridge/launch-pal.sh" \
  --role codereviewer \
  --expect-model claude-opus-5-5 \
  --prompt 'Read-only consultation: explain the difference between str.strip() and str.lower() in Python. Do not edit files. Answer in two sentences.'
~~~

This makes a live provider call and may incur a charge. It still uses **PAL → Claude Code → your configured provider**. It does not prove native GUI integration. Do not restart an app with a known startup problem merely to run this check.

Each invocation creates a new PAL process. PAL continuation IDs cannot be reused across separate invocations. Within one live MCP connection, PAL supports history replay; PAL 9.8.2 does not resume the underlying Claude session.

## Reasoning settings

A practical policy is medium GPT effort for routine coordination, and higher supported effort for difficult architecture, debugging, or an unresolved disagreement backed by evidence.

The installer does **not** change GPT effort. An instruction to “think harder” or a config-file edit does not establish that the active turn changed settings. This project has no configuration_update tool and does not implement automatic root-effort switching. Claude's medium/high flags succeeded in the reference tests; whether the provider honors their semantics remains unverified.

## Verification

Run the offline configuration tests:

~~~bash
python3 -m unittest discover -s tests -v
~~~

The reference setup also passed a live read-only consultation, a one-line delegated edit, and independent GPT acceptance checks. Those results establish a working route at the time of testing, not a provider SLA or a backend identity guarantee.

## Rollback

Remove only the mcp_servers.pal registration using codex mcp remove pal for the same Codex configuration, or carefully remove that table manually. The utility's backups are under the configured bridge directory's backups/ folder. Restore individual affected files rather than overwriting later unrelated configuration.

Keep your Claude settings, CC Switch profiles, and workspace files. Removing the bridge does not require deleting credentials or uninstalling either client.

## Credits and license

Configuration code and documentation are MIT licensed. The PAL patch is a modification of Apache-2.0-licensed PAL; see [NOTICE](NOTICE) and [PAL's license](third_party/PAL-LICENSE). Claude Code and Codex remain separate products.

Claude assisted with the configuration utility and tests. Codex reviewed the implementation, ran the checks, and edited the README and article for technical accuracy and grammar.
