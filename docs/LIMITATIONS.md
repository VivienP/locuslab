# Limitations

This file matches the shipped `locus verify` behavior. It is not a roadmap.

## Checkers

Four deterministic families emit verification findings:

- `broken_citation_anchor`
- `unresolved_evidence_link`
- `source_availability_gap`
- `manual_review_required`

Not implemented (also recorded in `KNOWN_LIMITATIONS` in
`src/locuslab/audit/manifest.py` where listed there):

- numeric mismatch
- cross-document contradiction
- rate recomputation
- GSPR status-aware severity
- bibliography-to-sources resolution for in-document footnotes

## Guidance review

SSCP guidance items are review aids (`guidance_review.json` /
`guidance_review.md`). They are never verification findings. The SSCP rule pack,
inventory, and derived Markdown are packaged under `locuslab.resources`
(byte-equal to `docs/`). Official PDFs stay in `docs/guidance/sources/`
and are not installed into the wheel.

## Extraction and PDFs

- No LLM path in the V1 core. Extraction and findings are deterministic Python.
- Dossier PDFs use `pypdf` on the text layer only. There is no OCR. Pages
  without a text layer produce a warning and no span.
- Optional extra `guidance-extract` (`pdfplumber`) is for converting committed
  guidance PDFs to Markdown. It is not the dossier PDF reader.

## Adjudication and config

- `src/locuslab/adjudication/` is a package stub. There is no adjudication
  workflow artifact (`adjudication.csv` is not written).
- `RuntimeConfig.online_mode` exists and defaults to off. Nothing in the
  pipeline reads it.

## Persistence

- Graph output is `graph.jsonl` only. No graph database or SPARQL server.
- Audit output is `audit_manifest.json` hashes. No Merkle / DSSE / Sigstore /
  in-toto layer.
