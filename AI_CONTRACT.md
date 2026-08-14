# AI_CONTRACT.md — LocusLab Engine

Engineering contract for AI development agents working in this repository.

**Status:** normative implementation contract  
**Applies to:** source code, tests, scripts, fixtures, documentation, and generated reports  
**Project purpose:** local-first MDR/IVDR evidence verification — ingest exported
dossiers, trace claims to sources, run deterministic checkers, and emit an
Evidence Trace Audit package.

Read this document before changing the repository. It defines **how** LocusLab
MUST be built.

The companion documents define:

- `docs/architecture.md`: pipeline, objects, and layer boundaries;
- `docs/IMPLEMENTED.md`: what a clone can run today;
- `docs/LIMITATIONS.md`: explicit non-capabilities;
- `docs/THIRD_PARTY.md`: EU/MDCG texts that are not Apache-2.0;
- `docs/roadmap.md`: delivery-slice pointer for this branch (not a phase diary).

When documents conflict, precedence is:

1. invariants in this contract;
2. `docs/architecture.md`;
3. `docs/IMPLEMENTED.md` and `docs/LIMITATIONS.md`;
4. `docs/THIRD_PARTY.md`;
5. README and CONTRIBUTING.

An implementation agent MUST report a contradiction rather than silently choosing
the easier interpretation.

---

## 1. Communication and working behaviour

### Communication

- Reply in the language used for the request unless asked otherwise.
- Write code, comments, identifiers, schemas, commit messages, and technical
  documentation in English.
- Be short and direct. Do not add promotional narration.
- Ask a question only when an ambiguity materially changes architecture, evidence
  integrity, licence boundaries, or public claims.
- When a safe, simpler interpretation exists within the current slice, use it and
  state the assumption instead of blocking progress.
- Present alternatives when they carry meaningfully different trade-offs.

### Behavioural guidelines

1. **Think before coding.** Identify the invariant, evidence boundary, and proof
   required before implementation.
2. **Simplicity first.** Build the smallest change that satisfies the requested
   outcome. Reliability and clarity matter more than feature count.
3. **Surgical changes.** Touch only what the task requires, preserve existing
   style, and remove only orphaned code created by the change.
4. **Goal-driven execution.** Convert each task into a verifiable claim and
   continue until the relevant verification passes or a blocker is demonstrated.
5. **Inspect before assuming.** Read existing code, tests, fixtures, and docs
   before proposing or implementing changes.
6. **Evidence before completion.** Run the command, inspect the output, and report
   the exact evidence before claiming success.

### Public repository stewardship

Treat every tracked file, commit, pull request, comment, and document as public
engineering material. Before adding or retaining tracked content, ask:

> Does this materially help a user, contributor, maintainer, or reviewer
> understand, use, verify, or maintain LocusLab Engine?

If not, keep it ephemeral or local. A tracked file MUST NOT contain prompts,
conversation history, session notes, private deliberation, scratchpads,
owner-specific reminders, workstation paths, private service state, or execution
constraints that are not intrinsic project constraints. Claude session plans
MUST stay under `.claude/plans/` (gitignored), never under `reports/` or `docs/`.
Shared repository instructions and automation configuration MAY describe how
supported development tools must operate; they MUST NOT narrate how a particular
session generated or reviewed a change.

A local operating constraint MAY guide one execution. It MUST NOT become a
product requirement, public limitation, or contributor obligation unless the
engine independently requires it and the public rationale stands on its own.
Authorship, maintainer contact, repository ownership, licence attribution, and
reproducible environment requirements are legitimate project metadata.

Repository hygiene is an engineering requirement:

- prefer an existing appropriate file over a new document or abstraction;
- remove files, rules, imports, comments, TODOs, debug artifacts, and generated
  output made obsolete by the current change;
- do not preserve implementation diaries, temporary plans, internal reminders, or
  historical inconsistencies in tracked documentation;
- do not mix unrelated formatting, cleanup, or prose polish into a functional
  change;
- do not add speculative infrastructure or abstractions without a current proof
  obligation;
- keep every tracked comment and link intelligible in a fresh clone;
- name tests, specs, and docs by **feature**, not by internal delivery-phase
  numbers.

Commits SHOULD represent one coherent, independently reviewable change. Messages
use a concise imperative Conventional Commit title, describe the actual change
rather than the working process, and contain no prompt, session, generated-by, or
co-author narration. Avoid WIP, generic, and implementation-diary messages.
Never mention an AI product, vendor, model, or co-author trailer in a commit or
pull request.

Pull-request titles MUST be precise and professional. Descriptions state what
changed, why it is needed, important design decisions, exact validation evidence,
and material limitations or follow-up work. They MUST NOT contain private
reasoning, prompts, session attribution, or a chronological implementation diary.

---

## 2. Mission and scope

### Mission

LocusLab verifies exported MDR/IVDR dossiers locally. It extracts claim and
citation candidates, links them to local sources, runs deterministic checkers,
and writes an Evidence Trace Audit package for RA/QA review.

Primary CLI:

```text
locus verify <dossier_dir> --out <run_dir>
```

It verifies documents. It does not author CER, PMCF, PMS/PSUR, SSCP, GSPR, or
other regulatory content. It is not a notified-body tool and is not legal advice.

### Evaluation criterion

LocusLab is judged on:

- deterministic, reconstructable findings;
- provenance from findings to spans, sources, checkers, and audit data;
- honest public claims (`planned` / `implemented` / `demonstrated` / `deferred`);
- offline unit tests and local-first verify;
- clarity of architecture and limitations.

It is not judged on completing every deferred checker family, LLM novelty, or
SaaS packaging.

---

## 3. Non-negotiable invariants

Violating any invariant breaks the project's credibility.

### Invariant 1 — deterministic core

Checkers, graph export, audit-manifest construction, and report generation are
pure Python. They MUST NOT call an LLM. See `src/locuslab/checkers/findings.py`.

### Invariant 2 — no LLM verdicts

Optional LLM use, if ever added, is limited to labelled, cached, reviewable
candidate extraction. Final support, contradiction, compliance, or severity MUST
NOT come from an LLM.

### Invariant 3 — deterministic ECO IDs

`make_eco_id` hashes the checker short token plus sorted affected object IDs:
`ECO-{CHECKER_SHORT}-{8 hex}`. Re-running the same artifacts MUST yield the same
ID.

### Invariant 4 — provenance

Findings carry `checker_id`, `finding_type`, `affected_object_ids`, evidence
text, and `adjudication_state`. Graph records and the audit manifest MUST remain
reconstructable from those objects. Every finding MUST trace to spans, source
rows, deterministic rules, or human adjudication.

### Invariant 5 — byte-stable artifacts where promised

`audit_manifest.json` hashes other run artifacts with SHA-256, uses no
wall-clock, and does not hash itself. Canonical writers MUST NOT depend on
unordered `dict`/`set` iteration or local clocks.

### Invariant 6 — local-first and offline tests

Default `RuntimeConfig.online_mode` is false (`LOCUSLAB_ONLINE_MODE`). Unit tests
MUST stay offline. Any network-capable path needs an explicit offline result, not
a silent `None`.

### Invariant 7 — conservative finding language

Do not emit "non-compliant", "NB will reject", "unsupported", "must", or "shall"
in finding evidence or remediation unless a deterministic rule actually
establishes that claim. See `src/locuslab/report/language.py`.

### Invariant 8 — guidance review is not an ECO finding

SSCP/guidance checklist output (`guidance_review.json` / `.md`) is a human-review
aid. Do not promote a guidance item to an ECO finding without a fixture-backed
deterministic checker.

### Invariant 9 — public claims follow evidence status

Capabilities use exactly one of these statuses:

- `planned`: specified but not implemented;
- `implemented`: code exists and relevant local automated tests pass;
- `demonstrated`: a reproducible artifact or operational experiment proves the
  claim;
- `deferred`: intentionally outside the current release.

Documentation MUST NOT use “demonstrates”, “guarantees”, “production-ready”, or
equivalent language for a merely planned capability. A README number or claim
MUST point to an inspectable artifact, test, or documented limitation.

### Invariant 10 — licence boundary

Original code and project docs are Apache-2.0. Third-party EU/MDCG texts under
`docs/guidance/sources/` are **not** Apache-2.0. Do not claim Apache on those
files. Do not add AGPL PDF libraries (`pymupdf`, `pymupdf4llm`, `marker`,
`docling`). Do not commit TEAM-NB binaries.

### Invariant 11 — synthetic and approved public fixtures

Do not commit private customer dossiers. Dogfood uses approved public fragments
under `reports/dogfood/` (gitignored). Public tests MUST NOT depend on those
paths.

---

## 4. Approved V1 architecture and stack

The V1 stack is intentionally small:

- Python 3.12 or later;
- local CLI (`locus`);
- `python-docx`, `pypdf`, `openpyxl`;
- optional extra `guidance-extract` (`pdfplumber`) for deriving Markdown from
  committed guidance PDFs only;
- pytest, ruff, mypy strict.

The implementation MUST NOT introduce FastAPI, MCP, SaaS dashboards, multi-tenant
auth, RDF/SPARQL servers, graph databases, solver-first checkers, embedding
verdicts, Annex VIII automation, or authoring-system integrations unless
`docs/IMPLEMENTED.md` and an accepted spec say so.

---

## 5. Required architectural boundaries

Domain-agnostic layers MUST NOT encode MDR/IVDR vocabulary:

- core objects (`Document`, `Span`, `Claim`, `Source`, `EvidenceLink`, `Finding`,
  `AdjudicationEvent`, `AuditRun`);
- ingestion readers and `SpanLocation`;
- claim-extraction primitives and citation/bibliography linking;
- evidence-link status vocabulary;
- graph record shape and audit-manifest schema.

MDR/IVDR-specific layers own ECO codes, document-family heuristics, checker rule
packs, and buyer-facing report labels.

API/CLI code translates inputs into pipeline calls and renders results. It MUST
NOT invent findings.

---

## 6. Code quality and implementation style

- Use type hints on public and internal function signatures unless a documented
  exception is required.
- Keep `python -m mypy src/locuslab` clean (`strict = true` in `pyproject.toml`).
- Run `python -m ruff check src tests scripts`.
- Do not use `except:`. Catch specific exceptions.
- Prefer test-first development for invariants, bug fixes, and checker behaviour.
- Match existing module boundaries before creating new abstractions.
- Do not generate CER, PMCF, PMS/PSUR, SSCP, GSPR, or other regulatory content.

---

## 7. Test and proof requirements

Each invariant MUST have automated tests at the narrowest appropriate level.

The repository MUST include offline tests for:

- ingestion and span IDs;
- claim, citation, and source mapping;
- the four shipped checker families;
- graph and audit-manifest determinism;
- report package artifacts;
- SSCP guidance review as a non-finding;
- packaged guidance assets;
- the demo runner on `fixtures/demo_dossier`.

A test that requires a private dogfood PDF does not prove the public clone.

---

## 8. Definition of done

A change is complete only when:

1. it is in scope for the current slice (`docs/roadmap.md` + `docs/IMPLEMENTED.md`);
2. relevant failure modes are explicit;
3. relevant unit tests pass;
4. documentation is updated when interfaces, behaviour, or public claims change;
5. no invariant is weakened;
6. fresh verification output has been inspected.

Required gates, when relevant:

```bash
python -m ruff check src tests scripts
python -m mypy src/locuslab
python -m pytest
python scripts/check_project_state_docs.py --check
```

Never report a gate as passing if it was not run.

An agent MUST NOT claim completion based solely on code inspection or an earlier
test run.

### Evidence status

A feature is `implemented` only when code exists and its relevant local automated
tests pass.

A feature is `demonstrated` only when a reproducible command or committed
artifact proves it.

---

## 9. Forbidden patterns

Implementation agents MUST NOT:

- emit a final support, contradiction, compliance, or severity verdict from an
  LLM;
- put an LLM in a checker, graph writer, audit manifest, or report builder;
- promote a guidance-review item to an ECO finding without a fixture-backed
  checker;
- invent missing dossier evidence;
- present synthetic fixtures as real-customer data;
- claim Apache-2.0 on EU/MDCG source texts;
- commit TEAM-NB binaries or private dogfood PDFs;
- add FastAPI, MCP, SaaS, RDF servers, solvers, or embedding verdicts in V1;
- publish README numbers without inspectable evidence;
- change a claim from `planned` to `demonstrated` without a reproducible artifact;
- write secrets or credentials into source, fixtures, logs, or documentation;
- stage, commit, push, or change branches without explicit authorisation for
  that action;
- use destructive raw deletion commands when a reversible alternative is
  available;
- name new public tests or docs after internal delivery-phase numbers.

---

## 10. Agent execution protocol

Before coding a slice, an implementation agent MUST:

1. read this contract and the relevant architecture / IMPLEMENTED / LIMITATIONS
   sections;
2. confirm that the task belongs to the current slice;
3. identify the invariants touched;
4. list the tests that will prove the exit criterion;
5. inspect existing code, tests, and fixtures;
6. implement only the requested slice;
7. run all relevant quality gates;
8. inspect their output;
9. report evidence, limitations, and unresolved risks without promotional
   language.

When a requested change conflicts with this contract, the agent MUST stop and
request a specification update rather than bypassing an invariant.

For small changes, the agent MAY combine steps in one concise execution note, but
MUST still perform the relevant verification.

Git mutation requires per-action authorisation. An implementation request is
not approval to stage, commit, or push.
