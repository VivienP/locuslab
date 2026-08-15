---
name: audit-release
description: Use when deciding whether a LocusLab source repository snapshot or Python distribution release is publishable.
---

# Audit release

Do not edit repository or source files or mutate Git state; do not stage,
commit, push, switch branches, open pull requests, or fix findings.

## Establish the target

Classify the exact target before running gates: `source repository publication`
or `Python distribution release`. Record the exact target ref and commit,
comparison base, dirty state, clean status, remote ref correspondence, and CI
run identity/status/commit/freshness. Unknown/stale facts are omissions.

## Acquire evidence safely

- **A:** Path A permits ephemeral writes only inside the approved external
  temporary workspace. Create a clean export with tracked-byte identity matching the
  exact target commit and ref; run gates, build, install, and demo there. Record
  repository status before and after; prove it is unchanged.
- **B:** Path B remains strictly read-only. In the agent sandbox, require a
  trusted CI- or operator-prepared immutable evidence bundle with the exact target commit and
  ref, tracked-byte identity, commands and results, artifacts and hashes, and
  freshness. The auditor verifies bundle binding, freshness, and readability;
  it does not prepare the bundle.

If neither path is available or bundle identity or freshness is unproven, the
verdict is `HOLD`. Never treat the current dirty repository as the clean target.
Never write build or demo outputs into the repository.

## Gather fresh evidence

Run fresh full gates:

```text
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/locuslab
python scripts/check_project_state_docs.py --check
python scripts/check_agentic_layer.py --check
```

For source repository publication, audit that clean target tree under A or
bundle evidence under B: public documentation, public claims, licence and
third-party attribution, repository hygiene, and the supported public demo.
Align claims and `docs/LIMITATIONS.md` with implemented/demonstrated evidence.
Exclude private data, secrets, generated logs, local settings, and session
artifacts.

For a Python distribution release, build from that clean target tree under A
and install the artifact produced from it; under B, verify bundled evidence:

1. Build the wheel and sdist.
2. Inspect archive contents, metadata, licence, and packaged resources.
3. In a clean temporary environment, install the built wheel non-editably,
   prove no repository import leakage, and run an installed `locus` demo.

Do not require distribution-only gates for source repository publication, but
source publication still requires supported public demo evidence.

Each demo uses the public fixture; record the artifact inventory, verify
openability and manifest hashes, and compare a deterministic rerun.

## Decide

Use exactly one verdict:

- `PUBLISHABLE`: every requirement applicable to the classified target has
  fresh passing evidence and no blocker.
- `HOLD`: evidence is missing, omitted, unrun, unavailable, stale,
  inconclusive, or identity-unproven, and there is no proven target failure.
- `NOT PUBLISHABLE`: fresh target-matched failing gate, build, install, demo, or
  hash check, or a documented contradiction, proves the target fails.

Missing required evidence can never yield `PUBLISHABLE`. Deadlines and requests
to skip gates do not lower the evidence threshold.

Report:

- **Target/ref/base/dirty/remote/CI:** classification and provenance.
- **Commands and results:** exact commands and pass/fail.
- **Omissions:** unrun/stale/inapplicable checks and reasons.
- **Blockers:** unresolved blockers.
- **Limitations:** evidence boundaries.
- **Verdict:** one allowed verdict with evidence.
