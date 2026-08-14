# DRAFT - REVIEW REQUIRED

## MR-1 Regression Notes — Bibliography Span Suppression

**Run:** 2026-05-22 / synthetic-cardiopatch-x1
**Failure category:** `manual_review_boundary`
**Failure subtype:** system overclaimed — bibliography spans produce spurious claims
**Strategy:** C (combined section + text-prefix filter) — LOCKED by founder
**Implementation target:** `src/locuslab/extract/claim_extractor.py` — new `_is_bibliography_span` gate in `_extract_from_span`

---

### Failure mode

The corpus has 5 documents. Each document has a `References used in this synthetic dossier`
section containing 18 bibliography entries (REF-001 through REF-018, extended to REF-020
in the live ingestion). Each entry follows the form:

```
REF-NNN. Author Surname, Given. Title. Year. [annotation]
```

Some entries include percentages or clinical-performance keywords inside their annotation
brackets. Because `_extract_from_span` applies no bibliography guard, the numeric and
clinical_performance extractors fire on these spans.

Observed in `claims.jsonl` (66 total claims, 30 from bibliography spans — 45%):

- `8.7%` appears 5 times, once per document, all from REF-018 (`Signal loss...` study).
- `94.8%` and `96.1%` appear across 4 documents via REF-012 (`Clinical study report CPX1-VAL-01`).
- `clinical_performance` claims are produced from REF-010 (`Instructions for Use`) in all 5
  documents via the `Intended purpose` keyword in the annotation text.
- Additional `clinical_performance` claims come from REF-012 annotation text in 4 documents.

An RA reviewer consuming `claims.jsonl` would encounter the same percentage values
appearing in both dossier body sections and bibliography entries, requiring manual
cross-referencing to discard bibliography artifacts. This is the overclaim.

The failing spans are documented in `regression.jsonl` as 6 representative records
(one per document per pattern pair — CER REF-018, CER REF-012, PMCF REF-018, PMS REF-012,
GSPR REF-010, SSCP REF-018). All span IDs were verified by live ingestion on 2026-05-22.

---

### Strategy C rationale (recap)

Four strategies were evaluated. The founder selected Strategy C. This section recaps the
rationale only; the design is not open for re-evaluation here.

Strategy C uses two complementary guards:

1. **Section name guard (`_BIB_SECTION`):** if `span.section` contains the word `references`,
   `bibliography`, `bibliographies`, or `sources`, the span is a bibliography span. This
   catches the entire corpus bibliography section by matching the heading text injected as
   `span.section` by the docx reader.

2. **Text prefix guard (`_BIB_PREFIX`):** if `span.text.lstrip()` starts with `REF-\d+\.`
   followed by a space, the span is a bibliography entry by its own content. This is a
   redundant catch for entries that appear in sections not matching the section guard (e.g.,
   embedded reference lists mid-document).

Both guards are regex-based, deterministic, and produce no LLM calls.

Implementation (locked, do not modify):

```python
_BIB_SECTION = re.compile(
    r"\b(?:references?|bibliograph(?:y|ies)|sources)\b",
    re.IGNORECASE,
)
_BIB_PREFIX = re.compile(r"^\s*REF-\d+\.\s", re.IGNORECASE)

def _is_bibliography_span(span: Span) -> bool:
    section = span.section or ""
    if _BIB_SECTION.search(section):
        return True
    return bool(_BIB_PREFIX.match(span.text))
```

Gate in `_extract_from_span` (locked):

```python
def _extract_from_span(self, span, doc):
    if _is_bibliography_span(span):
        return []
    # ... existing extractors
```

---

### Edge cases the filter MUST handle correctly

**1. Leading whitespace before REF-NNN**

The docx reader may preserve indented paragraphs with a leading space or tab character.
`_BIB_PREFIX` uses `^\s*` to tolerate any amount of leading whitespace before `REF-`.
`  REF-018. Author...` must match.

**2. Mixed case**

The pattern uses `re.IGNORECASE`. `ref-018.` (lowercase) and `REF-018.` (uppercase) must
both match. In practice the corpus uses uppercase only, but the filter should be robust.

**3. Multi-digit REF-NNN**

`_BIB_PREFIX` uses `\d+` (not `\d{3}`). REF-1, REF-12, REF-018, REF-100 must all match.
The corpus uses REF-001 through REF-020 (zero-padded three digits). The pattern must not be
artificially constrained to three digits.

**4. Section heading `"References used in this synthetic dossier"`**

The section name in the corpus is long. `_BIB_SECTION` uses `\b` word boundaries and
matches `references` anywhere in the section string. This matches the full section title
without anchoring to the start.

---

### Edge cases the filter MUST NOT over-trigger on

**1. Inline body mentions of REF-NNN**

Body paragraph and table-cell spans may reference bibliography entries inline:

```
span_6f422a702198cc7b | section "4. Target population" | text "REF-001; REF-012"
span_2c7b0332a29562b5 | section "6. Clinical performance evidence" | text "REF-012"
```

These spans do NOT start with `REF-\d+\.` — they are bare mention tokens, not entry
prefixes. `_BIB_PREFIX` requires the period+space suffix (`REF-012.` not `REF-012`), so
inline mentions like `REF-012`, `REF-001; REF-012` are not suppressed.

A body span like `"As shown in REF-012, sensitivity was 94.8%"` also does not match
`_BIB_PREFIX` because the text does not start with `REF-\d+\.`.

**2. Section name `"References"` in body prose**

If a body paragraph has section heading `"8. References for further reading"` or a section
named `"User references for support"`, the `_BIB_SECTION` pattern would match because
`references` appears in the string. This is an accepted false-positive risk.

**Accepted false-positive risk (marked explicitly):** A section whose name contains the
word `references`, `bibliography`, or `sources` but is not a bibliography list will have
all its spans suppressed. This is unlikely in MDR dossier structure, where these words
appear in headings only when the section is actually a reference list. The risk is
documented here and accepted by the founder for V1. If a real corpus triggers it, the
section guard can be made anchor-sensitive (e.g., require the word at the start of the
section name) in a future iteration.

**3. Section `"User references for support"`**

This hypothetical section name contains `references`. Under Strategy C, all spans in it
would be suppressed. This is the primary known false-positive surface. Accepted per above.

**4. Table of contents entry named `"References"`**

A TOC entry whose `span.section` is `"References"` but whose `span.text` is `"References"
12` (a page number reference) would be suppressed. Acceptable for V1 — TOC entries do not
carry claims worth extracting.

---

### Implementation note

`_is_bibliography_span` is a module-level predicate (not a method), consistent with the
locked design. It takes a `Span` object and returns `bool`. The gate is the first check in
`_extract_from_span`, before any extractor runs. An early return of `[]` means zero claims
of any type are produced, including numeric, classification, clinical_performance,
citation, and completeness.
