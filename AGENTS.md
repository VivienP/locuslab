# AGENTS.md

Tool-neutral contributor router for LocusLab Engine.

## Mission

LocusLab is a local-first MDR/IVDR evidence verification engine. It ingests
exported dossiers, traces claims to sources, runs deterministic checks, and
emits an Evidence Trace Audit package for RA/QA review. Findings carry
adjudication fields and an event model, but the full human adjudication workflow
is not implemented.

It verifies documents. It does not author CER, PMCF, PMS/PSUR, SSCP, GSPR, or
other regulatory content.

Primary CLI:

```text
locus verify <dossier_dir> --out <run_dir>
```

## Authorities

When instructions conflict, follow this order:

1. direct instructions for the current task;
2. [`docs/engineering_contract.md`](docs/engineering_contract.md);
3. this file;
4. [`docs/architecture.md`](docs/architecture.md),
   [`docs/IMPLEMENTED.md`](docs/IMPLEMENTED.md), and
   [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

Report contradictions instead of choosing a convenient interpretation.
`docs/IMPLEMENTED.md` is product truth; `docs/roadmap.md` is the current slice
pointer.

## Critical invariants

- Checkers, graph export, audit-manifest construction, and report generation are
  deterministic Python and do not call an LLM.
- LLM output cannot determine support, contradiction, compliance, or severity.
- ECO IDs, provenance, and promised artifact bytes remain reproducible.
- Default operation and unit tests remain local-first and offline.
- Finding language stays conservative and deterministic.
- Guidance-review items are human-review aids, not ECO findings.
- Public capability claims match evidence status and known limitations.
- Private dossiers, secrets, local settings, and session artifacts are never
  committed.

## Working and Git safety

- Inspect the relevant implementation, tests, fixtures, and docs before editing.
- Use the smallest coherent change and add tests at the layer required by the
  claim.
- Preserve unrelated worktree changes and do not bypass hooks.
- Stage, commit, push, branch creation or switching, pull-request creation, and
  merge each require explicit authorization for that specific action.
- Never force-push, pass `--no-verify`, or push directly to `main`.

## Verification

Run the narrowest live gates that support the claim and inspect their output:

```bash
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/locuslab
python scripts/check_project_state_docs.py --check
```

Never report an unrun gate as passing. Unit tests remain offline.

## Licence boundary

Original code and project documentation are Apache-2.0 (`LICENSE`, `NOTICE`).
Third-party EU/MDCG texts under `docs/guidance/sources/` are not Apache-2.0; see
[`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md).

## Documentation map

- [Engineering contract](docs/engineering_contract.md)
- [Architecture](docs/architecture.md)
- [Implemented surface](docs/IMPLEMENTED.md)
- [Limitations](docs/LIMITATIONS.md)
- [Current slice pointer](docs/roadmap.md)
- [Development workflow](docs/development_workflow.md)
- [Public agentic development kit](docs/agentic/README.md)
