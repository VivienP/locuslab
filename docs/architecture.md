# LocusLab V1 Architecture

## Product Shape

LocusLab V1 is a local-first Evidence Trace Audit engine for MDR/IVDR dossiers. It runs on exported files, not inside authoring platforms, and produces artifacts RA/QA teams can inspect.

Canonical flow:

```text
dossier/
-> ingestion
-> span model
-> claim candidates
-> citation/source mapping
-> deterministic checks
-> human adjudication
-> evidence graph
-> report package
-> audit manifest
```

## Input Contract

V1 accepts a local dossier folder containing some or all of:

- CER, PMS/PSUR, PMCF, SSCP, GSPR mapping documents.
- Evidence tables.
- Local bibliography or source files.
- Optional config for filename mapping.

Missing expected documents may surface as `source_availability_gap` or
`manual_review_required` findings. Broader document-completeness checking is
not implemented. See `docs/LIMITATIONS.md`.

## Output Contract

Every `locus verify` run writes:

- `claims.jsonl`, `citations.jsonl`, `sources.jsonl`, `evidence_links.jsonl`
- `findings.jsonl`, `findings.csv`
- `graph.jsonl`, `audit_manifest.json`
- `report.json`, `findings.xlsx`, `report.docx`

SSCP-routed runs also write `guidance_review.json` and `guidance_review.md`
(review aids, not ECO findings).

When an output directory is reused, the pipeline preflights and replaces only
the artifact names in this contract. Optional artifacts from the previous run
are removed, while files with unrelated names are preserved. A directory or
other non-file occupying a generated artifact name aborts the run before any
previous artifact is removed.

Not written: `extracted_claims.csv`, `adjudication.csv`.

## Core Object Model

- `Document`: local input file, type, parser metadata, hash, warnings.
- `Span`: extracted text/table/cell region with stable source location.
- `Claim`: candidate assertion with source span, type, extraction method, and confidence label.
- `Source`: bibliography or local evidence source.
- `EvidenceLink`: claim-to-source mapping and status.
- `Finding`: ECO issue with severity, affected objects, evidence, remediation hint, and adjudication state.
- `AdjudicationEvent`: human decision that accepts, rejects, or defers a finding.
- `AuditRun`: run metadata and artifact hashes.

## Ingestion Layer

Ingestion converts each supported file into spans:

- `.docx` via `python-docx`: paragraphs (with nearest heading as section) and
  table cells, traversed in document body order.
- `.pdf` via `pypdf`: one span per page that has extractable text. Pages with
  no text layer emit `EXTRACTION_NO_TEXT_LAYER` and produce no span; OCR is out
  of V1 scope.
- `.xlsx` via `openpyxl`: one span per non-empty cell. Header row context is
  propagated onto each data cell via `Span.section`.

Dossier PDF ingestion stays on `pypdf`. The optional extra `guidance-extract`
uses `pdfplumber` only to derive Markdown from committed guidance PDFs.
Readers must remain offline; network access is forbidden inside ingestion.
The loader preserves parser diagnostics even for unreadable files. The
verification pipeline fails before writing a run when the complete dossier
yields zero usable spans, so corrupt or empty inputs cannot produce a
successful zero-content audit.

## Checker Philosophy

Shipped checkers are deterministic Python:

- broken citation anchors;
- unresolved evidence links;
- source availability gaps;
- manual-review classification.

Not shipped: numeric mismatch, rate recomputation, cross-document
contradiction, GSPR status-aware severity, general document completeness.

Do not use embeddings, LLMs, or semantic similarity as final verdict machinery.

## Graph And Audit Posture

V1 persists graph-ready data in `graph.jsonl` or SQLite. IDs and records must remain compatible with later RDF/SPARQL export, but V1 does not run a graph server.

V1 uses `audit_manifest.json` for reproducibility metadata and SHA-256 hashes
of every generated run artifact except the manifest itself. Reports embed the
hashes of the source artifacts used to build them; the manifest is finalized
after the byte-stable report package is written. Cryptographic proof
infrastructure is deferred until finding quality and buyer demand justify it.

## Engine Domain Discipline

The MDR/IVDR document families are the V1 application surface. The engine underneath should stay domain-agnostic so the same pipeline can later verify other scientific outputs (for example CSR, protocol, SAP, clinical-trial claims, biomarker claims, safety narratives, and literature claims) without rewriting ingestion, linking, graph, or audit primitives.

Domain-agnostic layers — must not encode MDR/IVDR vocabulary, enums, or assumptions:

- Core object model: `Document`, `Span`, `Claim`, `Source`, `EvidenceLink`, `Finding`, `AdjudicationEvent`, `AuditRun`.
- Ingestion readers (`.docx`, `.pdf`, `.xlsx`) and `SpanLocation`.
- Claim extraction primitives (numeric, citation, classification, performance) and their extraction-method labels.
- Citation parsing and bibliography resolution.
- Evidence link status vocabulary (`resolved`, `source_unresolved`, `source_missing`, `manual_review_required`).
- Graph record shape (`graph.jsonl`/SQLite) and audit manifest schema.

MDR/IVDR-specific layers — domain knowledge belongs here:

- ECO category codes, severity rules, and finding wording.
- Document-taxonomy heuristics for CER, PMS/PSUR, PMCF, SSCP, GSPR.
- Checker rule packs and fixtures.
- Buyer-facing report templates and section labels.

Changes should not push MDR/IVDR vocabulary into the generic primitives, and should not move generic verification logic into the MDR-specific layers. A future non-MDR rule pack should be addable without modifying the domain-agnostic layers above.

## Deferred Complexity

Deferred for V1: FastAPI, MCP, SaaS dashboard, multi-tenant auth, EBOM, CycloneDX, in-toto, DSSE, Sigstore, Merkle DAG, RDF/SPARQL server, Neo4j, Tree-sitter as primary parser, ColBERT verdicts, z3/MiniZinc default checks, Annex VIII automation, and full enterprise air-gap certification.
