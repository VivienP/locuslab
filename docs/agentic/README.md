# Agentic Development Kit

LocusLab publishes a small, repository-local development layer that
is intended for discovery by multiple compatible clients without changing the
product runtime. The public layer is configuration and documentation only: it
does not place an LLM in verification, checking, graph, manifest, or report code.

## Layout

| Surface | Purpose | Authority |
|---|---|---|
| `.agents/skills/<name>/SKILL.md` | Canonical reusable development workflows | Canonical |
| `.claude/skills/<name>/SKILL.md` | Checked-in generated mirrors | Must match canonical bytes |
| `docs/agentic/roles/*.md` | Tool-neutral role specifications | Canonical |
| `.codex/agents/*.toml` | Thin Codex role adapters | Adapter |
| `.claude/agents/*.md` | Thin Claude role adapters | Adapter |

Edit a skill only under `.agents/skills/`, then regenerate its checked-in
`.claude/skills/` mirror and validate byte identity. Role behavior belongs in
`docs/agentic/roles/`; client adapters contain only identity, permission posture,
and canonical references.

## Discovery and invocation

The checked-in surfaces are intended for discovery by repository-aware clients
from the project root. Examples of intended invocation are:

```text
Use the locuslab-reviewer role to review this change.
Use the release-auditor role to audit this release candidate.
Use the verify-change skill before reporting verification.
```

Exact client syntax can vary. Treat these examples as discovery cues, not as
evidence that a particular client smoke test has run.

## Trust and permissions

Read the canonical role or skill before invoking it. Reviewers and release
auditors are intentionally read-only: they inspect repository evidence and do
not edit files or mutate Git state. Thin adapters reinforce that posture with
the most restrictive compatible client setting.

Repository instructions do not grant broader operating-system, network, or
account permissions. A client or operator remains responsible for reviewing
requested permissions and limiting access to the repository and evidence needed
for the task.

Public agentic files must not contain secrets, credentials, tokens, private
dossiers, absolute workstation paths, machine-local settings, logs, state, or
session plans. Keep local overrides in ignored local-only files such as
`CLAUDE.local.md` or the existing client-specific local settings paths.

## Compatibility status

| Capability | Status | Evidence boundary |
|---|---|---|
| Static checker | PASS locally | On 2026-08-15, `python scripts/check_agentic_layer.py --check` passed; CI runs the same command after the project-state check and before Pytest |
| Codex CLI 0.128.0 release scenario | PASS | On 2026-08-15, Codex discovered and invoked `audit-release`, classified the target as `source repository publication`, returned `HOLD` for a dirty or identity-unproven target, and made no mutation. This proves fail-closed invocation, not self-contained `PUBLISHABLE` execution: the read-only sandbox supplied neither an external temporary workspace nor an immutable evidence bundle. |
| Codex CLI 0.128.0 reviewer scenario | PARTIAL/BLOCKED | On 2026-08-15, `verify-change` and `review-finding-language` were discovered and `.codex/agents/locuslab-reviewer.toml` was found, but custom-agent spawn failed with `unknown agent_type 'locuslab-reviewer'`; Python checks were unavailable in the observed read-only sandbox, and no mutation occurred |
| Claude Code | UNAVAILABLE | On 2026-08-15, the client was not installed, so no live discovery or invocation is claimed; only static structural compatibility is established |

Static validity does not prove skill invocation, and skill invocation does not
prove custom-agent spawning. These results therefore do not demonstrate the
multi-tool layer as a whole. The static checker is CI-enforced. Update a live
compatibility status only when it is actually run and reproducible evidence
from the named client has been inspected.

## Reproduce the smoke checks

Run the two static CI checks from the repository root:

```bash
python scripts/check_project_state_docs.py --check
python scripts/check_agentic_layer.py --check
```

The observed Codex scenarios used these prompts with Codex CLI 0.128.0:

```text
Audit this source repository publication candidate with audit-release. Do not mutate files or Git state.
Use the locuslab-reviewer role with verify-change and review-finding-language to review the current change. Do not mutate files or Git state.
```

When Claude Code is installed, check availability and use the same reviewer
prompt before recording any live compatibility claim:

```bash
claude --version
```

Missing required roles, skills, mirrors, or adapters are validation failures and
must be resolved before the public agentic layer is considered complete.
