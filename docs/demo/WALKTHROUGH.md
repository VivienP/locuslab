# Demo walkthrough

Technical order for inspecting a successful demo run. This is not a sales
script.

## Run

From a clone with `pip install -e ".[dev]"`:

```bash
python scripts/run_demo.py --out tmp/demo
```

or:

```bash
locus verify fixtures/demo_dossier --out tmp/demo
```

Expected summary counts:

```text
18 claims, 5 citations, 3 sources, 18 evidence links, 8 findings, 105 graph records
```

## Inspect

Open artifacts in this order:

1. `report.docx` — Evidence Trace Audit (cover, run summary, findings, sources).
2. `findings.xlsx` — reviewer matrix. Adjudication columns are empty stubs.
3. `audit_manifest.json` — run metadata and SHA-256 hashes of the other artifacts.

Then optionally `report.json`, `graph.jsonl`, and the JSONL candidate files.

## Gaps

See [`docs/LIMITATIONS.md`](../LIMITATIONS.md). Guidance-review files appear
only on SSCP-routed dossiers; the bundled CER demo does not write them.
