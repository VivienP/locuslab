# Contributing

## Environment

Python 3.12+. From a clone, create a venv and install in editable mode
(`pip install -e ".[dev]"`). See the README for Windows and Unix snippets.

## Quality gates

Run these before sending a change:

```bash
python -m pytest
python -m ruff check src tests scripts
python -m mypy src/locuslab
```

Tests must stay offline. Do not add network calls to the default suite.

GitHub Actions (`.github/workflows/ci.yml`) runs the same three commands on
Python 3.12. Do not add the `guidance-extract` extra to that workflow.

## Scope

- Final findings come from deterministic checkers, not from an LLM.
- Do not generate CER, PMCF, PMS/PSUR, SSCP, GSPR, or other regulatory
  content. This project verifies exported documents.
- Original code is Apache-2.0. Do not treat files under
  `docs/guidance/sources/` as Apache-licensed. Do not add AGPL PDF libraries
  (`pymupdf`, `pymupdf4llm`, `marker`, `docling`).

See [`AI_CONTRACT.md`](AI_CONTRACT.md), `docs/architecture.md`, and
`docs/IMPLEMENTED.md`.
