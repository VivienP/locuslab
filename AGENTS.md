# AGENTS.md

Contributor and coding-agent guide for LocusLab Engine.

## Authorities

When instructions conflict, follow this order:

1. direct user instructions for the current task;
2. [`AI_CONTRACT.md`](AI_CONTRACT.md);
3. this file;
4. `docs/architecture.md` and `docs/IMPLEMENTED.md`.

Read [`AI_CONTRACT.md`](AI_CONTRACT.md) before changing the repository.
Then read the relevant sections of:

- [`docs/architecture.md`](docs/architecture.md) for the product pipeline and artifacts;
- [`docs/IMPLEMENTED.md`](docs/IMPLEMENTED.md) for the shipped public surface;
- [`docs/roadmap.md`](docs/roadmap.md) for the active delivery slice on this branch;
- [`docs/development_workflow.md`](docs/development_workflow.md) for Git and verification practice.

Report contradictions instead of choosing the most convenient interpretation.
Do not copy a phase label from this file, a chat, or a hook. On this branch,
`docs/IMPLEMENTED.md` is product truth and `docs/roadmap.md` is the slice pointer.

## Mission

LocusLab is a local-first MDR/IVDR evidence verification engine. It ingests exported dossiers,
traces claims to sources, runs deterministic checks, supports human adjudication, and emits an
Evidence Trace Audit package for RA/QA review.

It verifies documents. It does not author CER, PMCF, PMS/PSUR, SSCP, GSPR, or other regulatory content.

Primary CLI:

```text
locus verify <dossier_dir> --out <run_dir>
```

## Working rules

- Inspect the existing implementation, tests, fixtures, and docs before editing.
- Keep each change to the smallest coherent unit that satisfies the requested outcome.
- Add or update tests at the layer required by the claim. Do not weaken an invariant to make a test pass.
- Run the relevant gates and inspect their output before reporting completion.
- Preserve unrelated worktree changes. Do not stage, commit, push, change branches, bypass hooks, or
  perform destructive cleanup without explicit authorisation for that action.
- Keep secrets, machine-local configuration, session state, and generated logs out of version control.

## Product invariants

These are encoded because the current code, tests, and artifacts enforce them. Do not treat a stale
roadmap comment as an invariant.

1. **Deterministic core.** Checkers, graph export, audit manifest construction, and report generation
   are pure Python. They do not call an LLM. See `src/locuslab/checkers/findings.py`.
2. **Deterministic ECO IDs.** `make_eco_id` hashes the checker short token plus sorted affected object
   IDs: `ECO-{CHECKER_SHORT}-{8 hex}`. Re-running the same artifacts must yield the same ID.
3. **Provenance.** Findings carry `checker_id`, `finding_type`, `affected_object_ids`, evidence text,
   and `adjudication_state`. Graph records and the audit manifest must remain reconstructable from
   those objects.
4. **Byte-stable artifacts where promised.** `audit_manifest.json` hashes other run artifacts with
   SHA-256, uses no wall-clock, and does not hash itself. Canonical writers must not depend on
   unordered `dict`/`set` iteration or local clocks.
5. **No LLM verdicts.** Optional LLM use is limited to labelled, cached, reviewable candidate
   extraction. Final support, contradiction, compliance, or severity must not come from an LLM.
6. **Local-first.** Default `RuntimeConfig.online_mode` is false (`LOCUSLAB_ONLINE_MODE`). Unit tests
   stay offline. Any network-capable path needs an explicit offline result, not a silent `None`.
7. **Conservative finding language.** Do not emit "non-compliant", "NB will reject", "unsupported",
   "must", or "shall" in finding evidence or remediation unless a deterministic rule actually
   establishes that claim.
8. **Guidance review is not an ECO finding.** SSCP/guidance checklist output
   (`guidance_review.json` / `.md`) is a human-review aid. Do not promote a guidance item to an ECO
   finding without a fixture-backed deterministic checker.
9. **Synthetic and approved public fixtures.** Do not commit private customer dossiers. Dogfood uses
   approved public fragments under `reports/dogfood/` (gitignored).
10. **Honest limitations.** Unfinished checkers and known gaps belong in `KNOWN_LIMITATIONS` and docs
    as limitations, not as implied features.
11. **Engineering gates.** `python -m pytest`, `python -m ruff check src tests scripts`, and
    `python -m mypy src/locuslab` (`mypy` strict in `pyproject.toml`) are the live quality gates.

## Default-out-of-scope product surface

Do not add a new product surface unless `docs/IMPLEMENTED.md`, `docs/roadmap.md`, and an accepted
spec say so. In particular, do not silently turn the local CLI into a service platform, put an LLM
in a checker, or make network access mandatory for `locus verify`.

Do not add FastAPI, MCP, SaaS dashboards, multi-tenant auth, RDF/SPARQL servers, graph databases,
solver-first checkers, embedding verdicts, or Annex VIII automation unless `docs/IMPLEMENTED.md`
is explicitly updated.

## Git authority

An implementation request is not approval to commit. Approval for one of these actions does not
extend to the others:

- stage
- commit
- push
- create or switch branch
- open a pull request
- merge

Never force-push. Never pass `--no-verify`. Never push directly to `main`.
Never mention an AI product, vendor, model, or co-author trailer in a commit or PR.

See `AI_CONTRACT.md` for commit and push authorisation. Never stage, commit, or push
without an explicit request for that action.

## Verification

Run the narrowest live set that supports the claim. Never report a gate as passing if it was not run.

Typical live gates:

```bash
python -m ruff check src tests scripts
python -m mypy src/locuslab
python -m pytest
python scripts/check_project_state_docs.py --check
```

Unit tests must stay offline. Do not add network calls to default verification.

All committed code, comments, identifiers, schemas, and technical documentation are written in
English and describe project facts rather than a particular development session.

## License

Original code and project docs are Apache-2.0 (`LICENSE`, `NOTICE`).
Third-party EU/MDCG texts under `docs/guidance/sources/` are **not** Apache-2.0;
see `docs/THIRD_PARTY.md`.

## Docs

- Architecture: `docs/architecture.md`
- Implemented surface: `docs/IMPLEMENTED.md`
- Limitations: `docs/LIMITATIONS.md`
- Development workflow: `docs/development_workflow.md`
- Guidance rule packs: `docs/rules/guidance/`
- License / third-party texts: `LICENSE`, `NOTICE`, `docs/THIRD_PARTY.md`
