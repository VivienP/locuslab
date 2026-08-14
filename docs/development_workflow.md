# Development Workflow

## Current surface

See `docs/IMPLEMENTED.md` and `docs/LIMITATIONS.md`. The shipped CLI runs
ingestion, deterministic extraction and linking, four checker families, graph
export, audit manifest, and the report package. SSCP-routed runs may add
guidance-review artifacts that are not ECO findings.

## Current Phase

Public Edition - see docs/IMPLEMENTED.md

Confirm scope against `docs/roadmap.md` and `docs/IMPLEMENTED.md`. Do not copy
private `main` phase labels into this file.

## Standard Flow

1. Confirm the change matches `docs/IMPLEMENTED.md`, `docs/LIMITATIONS.md`, `AI_CONTRACT.md`, and the slice in `docs/roadmap.md`.
2. Write tests before implementation.
3. Implement the smallest useful change.
4. Run the live gates that the change can affect.
5. Review against architecture, offline/local-first behavior, deterministic
   checkers, provenance, and RA/QA usefulness.
6. Update docs only when the implementation or accepted plan changed.
7. Do not stage, commit, or push without explicit authorisation for that action.

## Test Strategy

- Unit tests stay offline.
- Mock or fixture every external dependency.
- Prefer golden fixtures under `tests/fixtures/` and `fixtures/`.
- Do not call the network from pytest.

## Verification Commands

Use what is available in the current environment:

```bash
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/locuslab
python scripts/check_project_state_docs.py --check
```

## Docs

- `AI_CONTRACT.md` — engineering contract
- `docs/architecture.md` — pipeline and object model
- `docs/IMPLEMENTED.md` — what a clone can run
- `docs/LIMITATIONS.md` — explicit non-capabilities
- `docs/THIRD_PARTY.md` — EU/MDCG file attribution
