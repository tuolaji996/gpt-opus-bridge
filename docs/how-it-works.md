# Building a GPT-led Claude delegation workflow

A useful multi-model workflow needs clear ownership. In this setup, GPT/Codex owns the plan, the acceptance criteria, and the final decision. Claude Opus handles a bounded assignment and returns its findings or file changes. GPT then checks the evidence and integrates the result.

The user continues working in Codex. PAL provides the connection between the lead and a background Claude Code process.

## Why the bridge launches Claude Code

Some third-party services accept requests only from Claude Code. Calling a provider directly from a generic SDK may therefore fail even when the same credentials work in the CLI.

PAL's clink tool launches the actual Claude Code executable. Claude loads the provider settings already maintained by CC Switch. PAL needs no copy of the API credential, and the bridge does not change Codex's provider or authentication.

In the reference installation, CC Switch writes directly to Claude's settings file. A local proxy is unnecessary. Other installations may use a proxy; this project does not pretend that the direct-settings setup automatically covers them.

## Why a small PAL patch is included

PAL 9.8.2 originally refuses to start without at least one direct API provider. That requirement is unnecessary when the only worker is an external CLI that already handles authentication.

The patch permits provider-free startup only when the remaining tools are clink and PAL's mandatory version/listmodels utilities. It also supplies a conservative local budget for reconstructing CLI conversation history. That budget governs how much text PAL forwards; it is not a claim about the provider's context window.

Two compatibility details matter. The release needs the MCP 1.x server API, so its dependency is constrained below 2. The shipped clink annotation says the tool is read-only even though it can launch an editing agent; the patch corrects that annotation.

The unused Codex and Gemini presets are removed from this dedicated installation. They ship with broader permission flags and are unnecessary for this route. Users should inspect their own PAL user overrides as well.

## Permissions and ownership

Claude runs in a designated workspace with restricted file tools. A review assignment receives Read, Glob, and Grep. An implementation assignment also receives Edit and Write. Shell execution, web tools, and additional MCP servers are not part of these presets.

This restriction makes responsibilities concrete: Claude proposes or edits; GPT runs verification commands. Before integration, GPT inspects which files changed and confirms that the worker stayed within its assignment.

These controls rely on the installed Claude Code version and are not an operating-system sandbox. The lead must still avoid staging secrets or granting an unnecessarily broad workspace.

## Reasoning effort has separate layers

Three different operations are often described as “changing reasoning”:

1. Selecting effort for a new worker.
2. Selecting effort for a subsequent root turn.
3. Changing the root model's effort during an active turn.

Support for the first two does not establish support for the third. A model saying it will think harder is not evidence that the client changed an API setting. Similarly, editing a default configuration does not prove the active GUI session adopted it.

The working policy is to keep routine coordination moderate and reserve higher supported effort for difficult architecture, debugging, or a disputed claim backed by evidence. Opus disagreement alone is not a reason to select the highest setting. Ask what claim is disputed, inspect the evidence, and run a focused check when appropriate.

This project does not implement automatic root-effort switching. Claude's medium/high settings were accepted in successful reference calls, but their backend effect cannot be independently established from that fact.

## What the tests establish

The reference workflow completed a read-only consultation and a tiny edit. The example function trimmed whitespace but did not lowercase its input. Opus identified the missing operation, then added .lower(). GPT inspected the one-line diff and ran assertions for a mixed-case string and an empty string.

The calls requested and reported claude-opus-5-5. Claude Code also emitted an unrecognized-model warning for that provider model name. Successful responses demonstrate that the configured route accepted it; they do not prove an independent model identity or validate the provider's marketing claims.

The portable configuration utility has separate offline tests. Those tests exercise safe configuration merging, dry-run behavior, backup handling, and validation without contacting any provider.

## GUI integration and session continuity

An MCP server can work through a local client while remaining absent from an active GUI chat's tool catalog. That is why the repository distinguishes a tested local route from native GUI discovery. A restart is not a prerequisite for using the local client, especially when restarting the desktop app has a known failure mode.

PAL's conversation memory belongs to its running process. Keeping one MCP connection open allows related calls to reuse a continuation ID. Starting a new helper process loses that memory. PAL 9.8.2 forwards reconstructed history but does not pass Claude's native resume flag.

## An efficient working loop

The lead gives Opus the smallest assignment that can produce useful evidence. The worker reports changed files, findings, blockers, and checks it could not run. The lead reviews the result, performs the relevant checks, and makes the decision.

One focused follow-up is usually enough to resolve a concrete disagreement. Repeated full test runs, broad re-exploration, and open-ended debates add cost without necessarily improving the outcome.
