# LocusLab Engine

Local CLI that verifies exported MDR/IVDR dossiers: it extracts claim and
citation candidates, links them to local sources, runs deterministic checkers,
and writes an Evidence Trace Audit package. It does not author CER, SSCP, or
other regulatory submissions. It is not a notified-body tool and is not legal
advice.

## Install

Python 3.12 or newer. From a git clone:

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Unix:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Dependency ranges and development extras are declared in `pyproject.toml`,
which is also the installation source used by CI. The repository does not
claim a fully locked transitive environment.

## Demo

```bash
locus verify fixtures/demo_dossier --out tmp/demo
```

Equivalent runner with artifact-path listing:

```bash
python scripts/run_demo.py --out tmp/demo
```

Expected summary line:

```text
18 claims, 5 citations, 3 sources, 18 evidence links, 7 findings, 104 graph records
```

Equivalent without the console script: `python -m locuslab.cli verify ...`.

## Artifacts written today

Every run:

| File | Role |
|---|---|
| `claims.jsonl` | Claim candidates |
| `citations.jsonl` | Parsed citation markers |
| `sources.jsonl` | Local bibliography / source files |
| `evidence_links.jsonl` | Claim-to-source links |
| `findings.jsonl` | ECO findings (JSONL) |
| `findings.csv` | ECO findings (CSV) |
| `graph.jsonl` | Graph-compatible records |
| `audit_manifest.json` | Run metadata and artifact hashes |
| `report.json` | Machine-readable report |
| `findings.xlsx` | Reviewer working matrix |
| `report.docx` | Primary Evidence Trace Audit |

SSCP runs (filename or content routed as SSCP) also write
`guidance_review.json` and `guidance_review.md`. Those are source-backed
review aids, not ECO findings. The SSCP rule pack, inventory, and derived
Markdown travel with the installed package (`locuslab.resources`).

**Not produced:** `extracted_claims.csv`, `adjudication.csv`. Adjudication
columns on `findings.xlsx` are empty stubs.

## Quality gates

```bash
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/locuslab
```

The same three commands run on GitHub Actions (`.github/workflows/ci.yml`).
Default CI installs `.[dev]` only; it does not install the optional
`guidance-extract` extra.

[![CI](https://github.com/VivienP/locuslab/actions/workflows/ci.yml/badge.svg)](https://github.com/VivienP/locuslab/actions/workflows/ci.yml)

## License

Original code and project documentation: [Apache-2.0](LICENSE).
EU/MDCG texts under `docs/guidance/sources/` are **not** Apache-2.0.
See [NOTICE](NOTICE) and [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).

## Docs

- [Engineering contract](AI_CONTRACT.md)
- [What is implemented](docs/IMPLEMENTED.md)
- [Limitations](docs/LIMITATIONS.md)
- [Demo walkthrough](docs/demo/WALKTHROUGH.md)
- [Architecture](docs/architecture.md)
- [Contributing](CONTRIBUTING.md)
