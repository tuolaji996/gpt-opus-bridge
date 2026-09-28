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

**Start here:** [How to install](#how-to-install) · [How to use](#how-to-use) · [Troubleshooting](#installation-troubleshooting)

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

## How to install

Follow these steps in a terminal on the **same machine that runs Codex**. The commands below target Ubuntu/Linux and install the bridge under your user account. They do not require running Codex, Claude, or PAL as root.

### 1. Check prerequisites

Confirm that Git and Python 3.11 or newer are available:

~~~bash
git --version
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"; print(sys.version.split()[0])'
~~~

On Ubuntu, if Git, Python, or curl is missing, install the missing packages through your package manager. For example:

~~~bash
sudo apt install git python3 curl
~~~

Install Claude Code and uv **only if they are missing**. These are their official installation endpoints:

~~~bash
# Claude Code: native stable installation
curl -fsSL https://claude.ai/install.sh | bash -s -- stable

# uv: Python environment and package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Make user-installed commands available in this terminal
export PATH="$HOME/.local/bin:$PATH"
~~~

If both tools are already installed, skip the installers and confirm their versions:

~~~bash
claude --version
uv --version
~~~

Use the official links in [Status and requirements](#status-and-requirements) to install Codex and CC Switch if needed. Keep your existing Codex login and provider. The bridge does not require an Anthropic subscription login when your third-party Claude provider is already configured.

### 2. Select the Claude provider in CC Switch

Open CC Switch, select its **Claude** application, and activate your intended provider. For the reference setup, this is Sui-Xiang (随想), with **claude-opus-5-5** configured as the intended model.

Keep Codex's provider unchanged. Add any missing credential inside CC Switch itself. Do not paste it into chat, scripts, or repository files.

This installer targets **direct Claude settings** mode: CC Switch writes the provider URL and credential to ~/.claude/settings.json. The installer checks that those settings exist without printing them. Local proxy mode and alternate cloud backends are not validated by this guide.

Use a model ID your provider explicitly supports. The name in these examples is not a guarantee that every provider serves that model.

### 3. Clone the bridge and install PAL

Choose a parent directory for the repository, then run:

~~~bash
git clone https://github.com/tuolaji996/gpt-opus-bridge.git
cd gpt-opus-bridge
~~~

Keep subsequent commands in this repository directory. The following block installs the pinned PAL release and applies its compatibility patch. It stops at the first failed step:

~~~bash
(
  set -e
  mkdir -p "$HOME/.local/share"
  git clone --branch v9.8.2 --depth 1 \
    https://github.com/BeehiveInnovations/pal-mcp-server.git \
    "$HOME/.local/share/pal-mcp-server"

  test "$(git -C "$HOME/.local/share/pal-mcp-server" rev-parse HEAD)" = \
    "fa78edca0b6bc04ab00ddf5694d855f1b946b87d"

  git -C "$HOME/.local/share/pal-mcp-server" apply --check \
    "$PWD/patches/pal-9.8.2-clink-only.patch"
  git -C "$HOME/.local/share/pal-mcp-server" apply \
    "$PWD/patches/pal-9.8.2-clink-only.patch"

  uv venv --python python3 "$HOME/.local/share/pal-mcp-server/.venv"
  uv pip install \
    --python "$HOME/.local/share/pal-mcp-server/.venv/bin/python" \
    -e "$HOME/.local/share/pal-mcp-server"
)
~~~

**Already have PAL?** Inspect that installation before proceeding. Do not overwrite existing changes or apply the patch twice. Use a separate PAL directory if you need to preserve an installation for another workflow, and pass that same directory to the configuration command below.

Also inspect any ~/.pal/cli_clients overrides and any PAL .env file: they can change client routing or enable direct API providers.

The patch allows CLI-only startup, supplies a bounded local budget for continuation history, corrects the clink permission annotation, constrains MCP to the compatible 1.x API, and removes unused Codex/Gemini presets. See [the implementation article](docs/how-it-works.md).

### 4. Preview the configuration

This is a **dry run**. It validates your paths and existing provider settings, then lists planned output files without writing them:

~~~bash
python3 scripts/configure.py \
  --pal-dir "$HOME/.local/share/pal-mcp-server" \
  --claude "$HOME/.local/bin/claude" \
  --workspace "$HOME/Documents/opus-workspace" \
  --model claude-opus-5-5
~~~

If your Claude executable or model differs, change the corresponding argument. For a nonstandard Codex configuration location, include --codex-config with the actual config.toml path. In particular, if you use CODEX_HOME, pass its config.toml explicitly. Use the same arguments in the apply step.

### 5. Apply the configuration

After the dry run succeeds, run the same command with **--apply**:

~~~bash
python3 scripts/configure.py \
  --pal-dir "$HOME/.local/share/pal-mcp-server" \
  --claude "$HOME/.local/bin/claude" \
  --workspace "$HOME/Documents/opus-workspace" \
  --model claude-opus-5-5 \
  --apply
~~~

The utility backs up existing affected files before editing and refuses to replace an existing pal MCP entry. It preserves the selected GPT model, reasoning default, other MCP servers, and provider settings.

| Default path | Purpose |
|---|---|
| ~/.claude/settings.json | Existing CC Switch-managed provider settings; read only. |
| ~/.codex/config.toml | Receives the new mcp_servers.pal registration. |
| ~/.config/gpt-opus-bridge/ | Generated launcher, Claude preset, and worker instructions. |
| ~/.config/gpt-opus-bridge/backups/ | Private backups of existing affected files. |
| ~/Documents/opus-workspace/ | Designated staging workspace for Claude. |

Use --claude-settings, --codex-config, --config-dir, and --workspace to override these locations. Never commit generated provider settings or configuration backups.

### 6. Verify the installation

Run the offline tests first. They use temporary files and make no provider calls:

~~~bash
python3 -m unittest discover -s tests -v
~~~

If the Codex CLI is available in your terminal, inspect the registration with:

~~~bash
codex mcp get pal
~~~

A desktop installation may not put the Codex CLI on PATH. In that case, check the app's MCP settings instead. A visible registration confirms configuration, not a successful Claude request.

For one small live coding consultation, run the command in [When the GUI does not expose PAL](#when-the-gui-does-not-expose-pal). It also works as a connection test when GUI discovery is available. The expected result is JSON containing the requested model, the matching reported model, and a reply. The call may incur a provider charge.

Do not restart an app with a known startup problem to perform this test. The local MCP client can use the configured bridge while the app remains open.

### Installation troubleshooting

| Symptom | Next step |
|---|---|
| claude or uv is not found | Add ~/.local/bin to this terminal's PATH, or use the installed executable's absolute path. |
| Missing provider URL or credential | Activate the intended Claude profile in CC Switch and check that it writes direct Claude settings. |
| Existing mcp_servers.pal entry | Inspect the existing registration. The installer deliberately refuses to replace it; use [Rollback](#rollback) only if you intend to remove that registration. |
| PAL patch does not apply | Check the pinned commit and existing changes. Do not apply it to a different release or apply it twice. |
| PAL is missing from the active chat | Use the local MCP helper below; native GUI discovery is a separate check. |
| Consultation fails or reports a different model | Check the exact provider-supported model and current CC Switch route. Do not silently switch providers or models. |

## How to use

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

## Contributors

This project was built with human direction and AI assistance:

| Contributor | Role |
|---|---|
| [TuoLaji](https://github.com/tuolaji996) | Project owner; defined the goals and approved publication. |
| **Claude** (via Claude Code) | AI contributor; implemented the configuration utility and its initial tests, then revised them after review. |
| **ChatGPT (Codex)** | AI contributor; led planning and integration, reviewed and corrected the code, ran verification, and wrote and edited the README and article. |

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for attribution details.

## License and upstream credits

Configuration code and documentation are MIT licensed. The PAL patch is a modification of Apache-2.0-licensed PAL; see [NOTICE](NOTICE) and [PAL's license](third_party/PAL-LICENSE). Claude Code and Codex remain separate products.
