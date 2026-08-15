---
name: verify-change
description: Use when verifying a LocusLab change before review, handoff, integration, or completion claims.
---

# Verify change

Verify the change that actually exists, with fresh evidence proportional to its
affected surfaces. Do not edit files or mutate Git state; do not stage, commit,
push, switch branches, or open pull requests.

## Establish scope

1. Read `AGENTS.md` and `docs/engineering_contract.md`.
2. Inspect the exact diff, base, and dirty state. Preserve the distinction
   between the target change and unrelated worktree changes.
3. Classify every changed path: Python/runtime, tests, project-state docs,
   agentic configuration, packaged byte resource, or release/public claim.

## Select fresh gates

Run new commands in the current worktree and inspect their output. Do not treat
an earlier run, code inspection, or another agent's summary as passing evidence.
Choose the matrix rows touched by the classified diff; not every change requires
every repository gate.

| Affected surface | Required evidence |
|---|---|
| Python/runtime | Relevant `pytest`, Ruff, and mypy scopes; widen only when coupling or risk requires it. |
| Tests | Run the directly changed tests and the nearest affected regression scope; run a broader suite only when shared behavior or invariants justify it. |
| Project-state docs | `python scripts/check_project_state_docs.py --check` and focused project-state tests. |
| Agentic files | `python scripts/check_agentic_layer.py --check` plus focused agentic tests. Record live-client discovery/invocation as run, not run, or unavailable; static success is not live-client evidence. |
| Packaged byte resources | Relevant byte and EOL checks, checksum/package tests, and consumer tests. |
| Release or public capability claims | Stop and use `audit-release`; verification alone cannot approve the claim. |

When a command cannot run, capture the exact blocker. Never convert an omission
or environment failure into a pass.

## Stop and report

Stop when all changed paths are classified and each applicable row has fresh,
inspected evidence, or when a blocker prevents that evidence. Stop immediately
for scope/contract conflict, unexplained generated-byte drift, or a release/public
claim requiring `audit-release`.

Report:

- **Scope/base/dirty state:** target diff and unrelated changes.
- **Commands run:** exact commands and relevant output summary.
- **Pass/fail:** result per applicable surface.
- **Omissions:** unrun gates and why they were not applicable or available.
- **Blockers:** exact unresolved failures or evidence gaps.
- **Conclusion:** verified, not verified, or blocked; never “safe to merge” from
  conditional or incomplete evidence.
