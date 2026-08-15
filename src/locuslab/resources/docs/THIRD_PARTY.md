# Third-party regulatory sources

This file inventories **non-original** files shipped in the repository so that
the Apache-2.0 license on LocusLab Engine is not mistaken for a license on
EU/MDCG texts.

This is **not legal advice**. Confirm reproduction terms with the issuer before
redistributing these files outside this repository. Local SHA-256 values are
hashes of the committed bytes; they are **not** a proof that a remote URL still
serves an identical file.

TEAM-NB documents are **not** included. The inventory entry
`team-nb-sscp-interpretation` stays `not_uploaded`.

## Original work vs third-party text

| Kind | License |
|---|---|
| `src/`, `tests/`, `scripts/`, project docs authored here | Apache-2.0 (`LICENSE`) |
| Official PDFs / EUR-Lex HTML / statutory extracts under `docs/guidance/sources/` | Issuer rights; **not** Apache-2.0 |
| Derived `.md` siblings produced by this project's extractors | Contain quoted third-party text. Treat the quoted content as third-party; the extraction tooling remains Apache-2.0 |

## Recorded sources

URLs below are public lookup locators. The locally recorded SHA-256 values
identify committed copies and do not attest to the current remote objects.

### MDCG 2019-9 Rev.1 (SSCP)

- Inventory id: `mdcg-sscp-public-guidance`
- Issuer: Medical Device Coordination Group
- Local PDF: `docs/guidance/sources/mdcg/md_mdcg_2019_9_sscp_en.pdf`
- Local SHA-256: `0148f179b063e260771648f48086cfd3d8dacc903dcff27ff0ccf9775e898859`
- Derived Markdown: `docs/guidance/sources/mdcg/md_mdcg_2019_9_sscp_en.md`
- Lookup URL: https://health.ec.europa.eu/document/download/5f082b2f-8d51-495c-9ab9-985a9f39ece4_en?filename=md_mdcg_2019_9_sscp_en.pdf
- Status: committed; used by SSCP rule excerpts

### MDCG 2022-9 Rev.1 (IVDR SSP)

- Inventory id: `mdcg-2022-9-ivdr-ssp`
- Issuer: Medical Device Coordination Group
- Local PDF: `docs/guidance/sources/mdcg/mdcg_2022-9_en.pdf`
- Local SHA-256: `d45c3df63bcdec452cb5b8396ffd94790be3625bfc94272e0c756e34d053c786`
- Derived Markdown: `docs/guidance/sources/mdcg/mdcg_2022-9_en.md`
- Lookup URL: https://health.ec.europa.eu/document/download/b7cf356f-733f-4dce-9800-0933ff73622a_en?filename=mdcg_2022-9_en.pdf
- Status: committed; inventory anchor, not quoted by the current SSCP pack

### Regulation (EU) 2017/745 (MDR)

- Inventory ids: `eu-mdr-2017-745-full-text`, `eu-mdr-2017-745-art-32`,
  `eu-mdr-2017-745-art-61-annex-xiv`, `eu-mdr-2017-745-pms-psur`
- Issuer: European Parliament and Council
- Full-text local copy: `docs/guidance/sources/eurlex/L_2017117EN.01000101.xml.html`
- Full-text SHA-256: `8045bc32fcaa29e33b0dff270fddde31ffcbcebd1ee9990c44d126c5b7ffb1bf`
- Article 32 extract: `docs/guidance/sources/eurlex/article_32.txt` (+ `.md`)
- Article 61 extract: `docs/guidance/sources/eurlex/article_61.txt` (+ `.md`)
- Lookup URL: https://eur-lex.europa.eu/eli/reg/2017/745/oj
- Also: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32017R0745
- Status: full HTML and article extracts committed; PMS/PSUR article extract
  not yet produced (`not_uploaded`)

EUR-Lex HTML may include site chrome that is not part of the OJ text.

### Commission CTR layperson summaries (2017-01-26)

- Inventory id: `eu-lay-summary-guidance-536-2014`
- Issuer: European Commission
- Local PDF: `docs/guidance/sources/eu-commission/2017_01_26_summaries_of_ct_results_for_laypersons_0.pdf`
- Local SHA-256: `850300f8372e22f640d255002778b89146744128429952d12c1ce0a1c63123c6`
- Lookup URL: https://health.ec.europa.eu/system/files/2020-02/2017_01_26_summaries_of_ct_results_for_laypersons_0.pdf
- Status: committed as a reference; **not quoted** by current SSCP rules

### EUDAMED SSCP module guidance

- Inventory id: `eudamed-sscp-upload-guidance`
- Status: `not_uploaded`; `official_url` remains null until a specific document
  is pinned

### TEAM-NB

- Inventory id: `team-nb-sscp-interpretation`
- Status: `not_uploaded`; no local path; redistribution not confirmed
- Do not add TEAM-NB PDFs to this tree

## Runtime Python dependencies

Declared in `pyproject.toml` (not vendored):

| Package | Typical license (verify on PyPI) | Role |
|---|---|---|
| python-docx | MIT | DOCX ingestion / `report.docx` |
| pypdf | BSD-3-Clause | PDF page text |
| openpyxl | MIT | XLSX ingestion / `findings.xlsx` |
| pdfplumber (optional extra `guidance-extract`) | MIT | Guidance PDF → Markdown |

Do **not** add AGPL PDF stacks (`pymupdf`, `pymupdf4llm`, `marker`, `docling`)
to this project.

## Replacement strategy

A future packet may replace committed binaries with a fetch script plus the
SHA-256 values above. Until then, keep the local files so offline tests and
SSCP excerpt hashing remain deterministic.
