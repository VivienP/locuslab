# Implemented surface

Status of the public-edition tree. This table is what a clone can run.

| Area | Status |
|---|---|
| CLI `locus verify <dossier> --out <run_dir>` | Implemented |
| Ingestion `.docx` / `.pdf` / `.xlsx` → spans | Implemented (`python-docx`, `pypdf`, `openpyxl`) |
| Claim / citation / source candidates | Implemented (deterministic; no LLM) |
| Evidence linking | Implemented (`resolved`, `source_unresolved`, `source_missing`, `manual_review_required`) |
| Checkers (4 families) | Implemented — see `docs/LIMITATIONS.md` |
| `findings.jsonl` + `findings.csv` | Implemented |
| `graph.jsonl` + `audit_manifest.json` | Implemented |
| `report.json` + `findings.xlsx` + `report.docx` | Implemented |
| SSCP guidance review artifacts | Implemented on SSCP-routed runs; not ECO findings |
| MDCG/EUR-Lex source inventory + MD spine | Implemented; third-party texts are not Apache-2.0 |
| Human adjudication CSV / workflow | Not implemented (stub package) |
| Numeric mismatch / contradiction / rate checkers | Not implemented |
| LLM candidate extraction | Not implemented |
| Wheel-packaged SSCP guidance JSON/MD | Implemented (`locuslab.resources`; PDFs stay in `docs/`) |

Demo fixture `fixtures/demo_dossier/` is the supported public sample.
`python scripts/run_demo.py` wraps the same verify path and lists artifacts.
See `docs/demo/WALKTHROUGH.md`.
