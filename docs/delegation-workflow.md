# Delegation instructions

Adapt these instructions to your authorized project and configured workspace.

1. GPT/Codex owns planning, decisions, acceptance criteria, integration, and final verification. Delegate substantial independent work when useful; keep trivial work local.
2. Call PAL clink with cli_name=claude. Preserve the explicit provider-supported model and the existing CC Switch route. Stop if the reported model differs.
3. Include the objective, acceptance criteria, exact owned files, read-only context, relevant project instructions, constraints, and verification commands in each assignment.
4. Stage only the necessary files inside the configured workspace. Never stage credentials. Keep a clear mapping to the authorized target. No concurrent edits to the same files.
5. Choose codereviewer for routine review, planner for difficult analysis, default for routine edits, or implementer for substantial edits.
6. Ask for concise findings, changed files, blockers, incomplete work, and evidence-backed disagreements. Claude cannot run shell checks on this route; it must mark them NOT RUN.
7. Independently inspect changes, run focused acceptance checks, and integrate accepted results. Do not repeat full suites without a relevant change or unresolved concern.
8. Resolve a concrete disagreement through evidence and at most one focused follow-up before deciding or requesting necessary user input.
9. Reuse a PAL continuation ID only within the same live server process. Across new processes, provide a concise evidence summary.
10. Delegation does not authorize commits, pushes, deployments, external messages, provider changes, or unrelated actions.
11. Prefer medium GPT effort for routine coordination and higher supported effort for difficult work. Do not claim automatic active-turn switching, invent configuration_update, or infer that a saved default changed the current turn.
12. If the native GUI tool is absent, use the local MCP helper when available. Report the distinction accurately and preserve a running app that has a known restart problem.
