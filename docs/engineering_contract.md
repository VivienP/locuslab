# LocusLab Engineering Contract

**Status:** normative implementation contract
**Applies to:** source code, tests, scripts, fixtures, documentation, and
generated reports

LocusLab is a local-first MDR/IVDR evidence verification engine. It ingests
exported dossiers, traces claims to sources, runs deterministic checks, and
emits an Evidence Trace Audit package for RA/QA review.

Companion documents define the product pipeline and public surface:

- [`architecture.md`](architecture.md): pipeline, objects, and boundaries;
- [`IMPLEMENTED.md`](IMPLEMENTED.md): what a clone can run today;
- [`LIMITATIONS.md`](LIMITATIONS.md): explicit non-capabilities;
- [`THIRD_PARTY.md`](THIRD_PARTY.md): licence boundaries for EU/MDCG texts;
- [`roadmap.md`](roadmap.md): current delivery-slice pointer.

When instructions conflict, follow this order:

1. direct instructions for the current task;
2. this engineering contract;
3. the root `AGENTS.md` router;
4. `docs/architecture.md`, `docs/IMPLEMENTED.md`, and
   `docs/LIMITATIONS.md`.

Report contradictions instead of choosing a convenient interpretation.
`docs/IMPLEMENTED.md` is product truth; `docs/roadmap.md` is the current slice pointer.

## Mission and scope

The primary interface is:

```text
locus verify <dossier_dir> --out <run_dir>
```

LocusLab verifies documents. It does not author CER, PMCF, PMS/PSUR, SSCP,
GSPR, or other regulatory content. It is not a notified-body system and is not
legal advice.

LocusLab V1 is MDR/IVDR-specific. Reusable mechanics such as readers, hashing,
stable identifiers, and canonical artifact writers do not imply cross-domain compatibility.
Support for another domain requires an explicit product
specification, public-surface update, implementation, tests, and fixtures.

## Engineering principles

- Inspect existing code, tests, fixtures, and documentation before changing a
  behavior or public claim.
- Implement the smallest coherent change that satisfies the accepted outcome.
- Preserve established module boundaries and unrelated worktree changes.
- Encode failure modes explicitly and prove relevant invariants at the narrowest
  useful test layer.
- Keep tracked material useful to users, contributors, maintainers, or reviewers.
  Do not commit prompts, deliberation, scratchpads, workstation paths, private
  service state, secrets, or temporary execution artifacts.
- Public claims use evidence status honestly: `planned`, `implemented`,
  `demonstrated`, or `deferred`.

## Product invariants

### Deterministic core and verdicts

Checkers, graph export, audit-manifest construction, and report generation are
pure Python and must not call an LLM. Optional LLM use is limited to labelled,
cached, reviewable candidate extraction. Final support, contradiction,
compliance, or severity must not come from an LLM.

### Deterministic identifiers

`make_eco_id` hashes the checker short token plus sorted affected object IDs:
`ECO-{CHECKER_SHORT}-{8 hex}`. Re-running the same artifacts must yield the same
identifier.

### Provenance and adjudication state

Findings carry `checker_id`, `finding_type`, `affected_object_ids`, evidence
text, and `adjudication_state`. Graph records and the audit manifest remain
reconstructable from those objects. Adjudication fields and the
`AdjudicationEvent` model exist, but a full human adjudication workflow and
`adjudication.csv` are not implemented.

### Byte-stable artifacts

`audit_manifest.json` hashes every other generated run artifact with SHA-256,
uses no wall-clock value, and does not hash itself. Canonical writers must not
depend on unordered `dict` or `set` iteration or local clocks.

### Local-first and offline behavior

Default `RuntimeConfig.online_mode` is false (`LOCUSLAB_ONLINE_MODE`). Unit
tests stay offline. A network-capable path must produce an explicit offline
result rather than a silent `None`.

### Conservative finding language

Finding evidence and remediation must not emit "non-compliant", "NB will
reject", "unsupported", "must", or "shall" unless a deterministic rule
establishes that statement. See `src/locuslab/report/language.py`.

### Guidance review boundary

SSCP guidance checklist output (`guidance_review.json` and
`guidance_review.md`) is a human-review aid. It must not become an ECO finding
without a fixture-backed deterministic checker.

### Evidence-aligned public claims

- `planned`: specified but not implemented;
- `implemented`: code exists and relevant local automated tests pass;
- `demonstrated`: a reproducible artifact or operational experiment proves the
  claim;
- `deferred`: intentionally outside the current release.

Documentation must not describe a merely planned or implemented capability as
demonstrated, guaranteed, or production-ready. Public numbers and claims must
point to inspectable evidence or a documented limitation.

### Licence and fixture boundaries

Original code and project documentation are Apache-2.0. Third-party EU/MDCG
texts under `docs/guidance/sources/` are not Apache-2.0. Do not claim Apache-2.0
for those files, add AGPL PDF libraries (`pymupdf`, `pymupdf4llm`, `marker`,
`docling`), or commit TEAM-NB binaries.

Do not commit private customer dossiers. Dogfood uses approved public fragments
under `reports/dogfood/`, which is ignored. Public tests must not depend on that
path.

## Approved V1 boundaries

The V1 stack is Python 3.12 or later, the local `locus` CLI, `python-docx`,
`pypdf`, `openpyxl`, and the optional `guidance-extract` extra (`pdfplumber`) for
deriving Markdown from committed guidance PDFs. Quality gates are pytest, Ruff,
and strict mypy.

Do not introduce FastAPI, MCP, SaaS dashboards, multi-tenant authentication,
RDF/SPARQL servers, graph databases, solver-first checkers, embedding verdicts,
Annex VIII automation, or authoring-system integrations unless
`docs/IMPLEMENTED.md` and an accepted specification include them.

Core models and general mechanics must not acquire MDR/IVDR vocabulary that
belongs in ECO codes, document-family heuristics, checker rules, and report
labels. CLI code translates inputs into pipeline calls and renders results; it
must not invent findings. This separation is an internal maintenance boundary,
not a claim of compatibility with another domain.

## Code quality

- Write code, comments, identifiers, schemas, and technical documentation in
  English.
- Use type hints on public and internal function signatures unless a documented
  exception is necessary, and keep strict mypy clean.
- Catch specific exceptions; do not use a bare `except:`.
- Match existing module boundaries before adding abstractions.
- Name public tests and documentation by feature rather than internal delivery
  labels.
- Do not generate regulatory content.

## Test and proof requirements

Relevant changes require offline automated evidence at the narrowest useful
layer. The public repository covers ingestion and span IDs; claim, citation, and
source mapping; the four shipped checker families; graph and audit-manifest
determinism; report package artifacts; SSCP guidance review as a non-finding;
packaged guidance assets; and the demo runner on `fixtures/demo_dossier`.

A test that requires a private dogfood PDF does not prove the public clone.

Typical gates are:

```bash
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/locuslab
python scripts/check_project_state_docs.py --check
```

A change is complete only when it is in the current public slice, relevant
failure modes are explicit, affected tests pass, public documentation is
aligned, no invariant is weakened, and fresh verification output has been
inspected. An unrun gate must never be reported as passing.

## Repository and Git safety

- Keep secrets, credentials, private evidence, generated logs, and local
  configuration out of tracked files.
- Do not use destructive cleanup when a reversible alternative is available.
- Do not bypass hooks with `--no-verify`, force-push, or push directly to
  `main`.
- Stage, commit, push, branch creation or switching, pull-request creation, and
  merge each require explicit authorization for that specific action. Approval
  for one action does not authorize another.
- Commits and pull requests describe the public change, rationale, validation,
  and limitations without private process narration.
