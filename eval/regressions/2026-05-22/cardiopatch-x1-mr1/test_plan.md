# DRAFT - REVIEW REQUIRED

## Test Plan — MR-1 Bibliography Span Suppression Regression Gates

**Target file:** `tests/test_extract_claim_extractor.py`
**Class to add:** `TestBibliographySuppression` (new class, do not modify existing classes)
**Style reference:** existing `_make_span` / `_make_doc` helpers and `extractor` fixture in
that file.

All suppression tests below must FAIL on the current code (no `_is_bibliography_span` gate)
and PASS after Strategy C lands. The two sanity tests (body span tests) must PASS before
and after the fix — they protect against over-firing.

---

### New constants to add at module level alongside existing constants

```python
# MR-1 regression: bibliography span suppression (corpus: cardiopatch-x1, 2026-05-22)
# Corpus-verified span IDs (live ingestion 2026-05-22)
BIB_GSPR_REF010_SPAN_ID = "span_d211e0824453201d"
BIB_CER_REF018_SPAN_ID = "span_862159e5e696e01b"
BIB_CER_REF012_SPAN_ID = "span_6b7d9c9b88c5ff45"

DOC_ID_GSPR_CPX1 = "doc_921318243dfcba8b"

BIB_REF001_TEXT = (
    "REF-001. Martin A., De Smet J., Rinaldi C. et al. Prospective multicentre "
    "validation of a single-lead ambulatory ECG patch. 2023."
)
BIB_REF018_TEXT = (
    "REF-018. Data Science Team. Signal loss and uninterpretable segment analysis "
    "by BMI and skin phototype subgroup, DS-CPX1-2025-07. 2025. "
    "[Data science subgroup analysis; BMI >35 subgroup shows 8.7% uninterpretable segments.]"
)
BIB_REF012_TEXT = (
    "REF-012. Clinical Operations Unit. Clinical study report CPX1-VAL-01, comparison "
    "to 3-lead Holter. 2024. [Clinical study report; Pivot performance: AF sensitivity "
    "94.8%, specificity 96.1%.]"
)
BIB_REF010_TEXT = (
    "REF-010. LocusLab Demo Medical SAS. Instructions for Use CardioPatch X1, "
    "IFU rev.4, English. 2025. [IFU; Intended purpose and 7-day use duration.]"
)
BIB_LEADING_WHITESPACE_TEXT = (
    "  REF-018. Data Science Team. Signal loss subgroup analysis. 2025. "
    "[BMI >35 subgroup shows 8.7% uninterpretable segments.]"
)
BODY_INLINE_REF_TEXT = (
    "As shown in REF-012, sensitivity was 94.8% and specificity was 96.1% "
    "in the pivotal study population."
)
BODY_CP_TEXT = (
    "The CardioPatch X1 demonstrated a sensitivity of 91.2% in the primary "
    "clinical performance analysis of the PMCF registry cohort."
)
```

---

### Tests in `TestBibliographySuppression`

#### Test 1 — Bibliography span starting with `REF-001.` produces 0 claims

```python
def test_bib_span_ref_prefix_produces_zero_claims(self, extractor, cer_doc):
    """MR-1 suppression gate: span starting with 'REF-NNN.' must produce 0 claims.

    Dogfood run 2026-05-22 / cardiopatch-x1 MR-1. RC-3 regression gate.
    Fails on current code (no _is_bibliography_span gate).
    Passes after Strategy C lands in _extract_from_span.
    """
    span = _make_span("span_mr1_ref001_fixture", DOC_ID_CER, BIB_REF001_TEXT)
    claims = extractor.extract_claims([span], [cer_doc])
    assert claims == [], (
        f"Expected 0 claims from bibliography span; got {len(claims)}: "
        f"{[c.text for c in claims]}"
    )
```

#### Test 2 — Bibliography span with leading whitespace (`  REF-018.`) produces 0 claims

```python
def test_bib_span_leading_whitespace_produces_zero_claims(self, extractor, cer_doc):
    """MR-1 suppression gate: leading whitespace before REF-NNN. must not bypass filter.

    Validates _BIB_PREFIX uses '^\\s*REF-\\d+\\.\\s' (anchored with whitespace tolerance).
    Span text starts with two spaces before 'REF-018.'.
    Fails on current code; passes after Strategy C.
    """
    span = _make_span(
        "span_mr1_leading_ws_fixture", DOC_ID_CER, BIB_LEADING_WHITESPACE_TEXT
    )
    claims = extractor.extract_claims([span], [cer_doc])
    assert claims == [], (
        f"Leading whitespace bypassed bibliography filter; got {len(claims)} claims: "
        f"{[c.text for c in claims]}"
    )
```

#### Test 3 — Span in section `"6. References used in this synthetic dossier"` with percentage produces 0 claims

```python
def test_bib_section_with_percentage_produces_zero_claims(self, extractor, cer_doc):
    """MR-1 suppression gate: section name containing 'references' suppresses all claims.

    The section guard (_BIB_SECTION) matches 'references' anywhere in the section string.
    Even a span whose text contains a percentage (8.7%) must produce 0 claims.
    Fails on current code; passes after Strategy C.
    """
    span = _make_span(
        "span_mr1_ref_section_pct_fixture",
        DOC_ID_CER,
        BIB_REF018_TEXT,
        section="References used in this synthetic dossier",
    )
    claims = extractor.extract_claims([span], [cer_doc])
    assert claims == [], (
        f"Section-guard failed on 'References used in this synthetic dossier'; "
        f"got {len(claims)} claims: {[c.text for c in claims]}"
    )
```

#### Test 4 — Span in section `"Bibliography"` produces 0 claims

```python
def test_bib_section_bibliography_produces_zero_claims(self, extractor, cer_doc):
    """MR-1 suppression gate: section named 'Bibliography' suppresses all claims.

    Validates _BIB_SECTION matches the word 'bibliography' (not just 'references').
    Fails on current code; passes after Strategy C.
    """
    span = _make_span(
        "span_mr1_bibliography_section_fixture",
        DOC_ID_CER,
        BIB_REF012_TEXT,
        section="Bibliography",
    )
    claims = extractor.extract_claims([span], [cer_doc])
    assert claims == [], (
        f"Section 'Bibliography' did not suppress claims; "
        f"got {len(claims)} claims: {[c.text for c in claims]}"
    )
```

#### Test 5 — Body span with inline `REF-012` mention still extracts claims (anti-regression)

```python
def test_body_inline_ref_mention_still_extracts(self, extractor, cer_doc):
    """Sanity gate: inline REF-NNN mention in a body span must NOT be suppressed.

    'As shown in REF-012, sensitivity was 94.8%...' does not start with 'REF-\\d+.'
    and is in a body section, so _is_bibliography_span returns False.
    Must PASS before and after Strategy C lands (filter must not over-fire).
    """
    span = _make_span(
        "span_mr1_inline_ref_body_fixture",
        DOC_ID_CER,
        BODY_INLINE_REF_TEXT,
        section="6. Clinical performance evidence",
    )
    claims = extractor.extract_claims([span], [cer_doc])
    numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
    assert numeric_claims, (
        f"Inline body REF mention was incorrectly suppressed; "
        f"expected numeric claims for 94.8%/96.1%, got: {claims}"
    )
    assert any("94.8" in c.text for c in numeric_claims), (
        f"94.8% not found in numeric claims: {[c.text for c in numeric_claims]}"
    )
```

#### Test 6 — Body span in section `"5. Clinical Performance"` with percentage still extracts (sanity)

```python
def test_body_clinical_performance_section_not_suppressed(self, extractor, cer_doc):
    """Sanity gate: body span in a CP section must not be suppressed.

    Section name '5. Clinical Performance' does not contain 'references', 'bibliography',
    or 'sources'. Span text does not start with 'REF-\\d+.'.
    Must PASS before and after Strategy C (filter must not over-fire on clinical sections).
    """
    span = _make_span(
        "span_mr1_body_cp_fixture",
        DOC_ID_CER,
        BODY_CP_TEXT,
        section="5. Clinical Performance",
    )
    claims = extractor.extract_claims([span], [cer_doc])
    numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
    assert numeric_claims, (
        f"Body CP span was incorrectly suppressed; "
        f"expected numeric claim for 91.2%, got: {claims}"
    )
```

#### Test 7 — Corpus-anchored: GSPR REF-010 span (span_d211e0824453201d) produces 0 claims

```python
def test_corpus_anchor_gspr_ref010_produces_zero_claims(self, extractor):
    """Corpus-anchored MR-1 regression gate.

    Span: span_d211e0824453201d in doc_921318243dfcba8b (GSPR document).
    Section: 'References used in this synthetic dossier'
    Text: 'REF-010. LocusLab Demo Medical SAS. Instructions for Use ...'
    Current behavior: 1 clinical_performance claim (from 'Intended purpose' keyword
    in annotation text).
    Expected after fix: 0 claims.

    Span ID and text verified by live ingestion on 2026-05-22.
    See eval/regressions/2026-05-22/cardiopatch-x1-mr1/regression.jsonl
    record reg_mr1_gspr_ref010.
    """
    span = _make_span(
        BIB_GSPR_REF010_SPAN_ID,
        DOC_ID_GSPR_CPX1,
        BIB_REF010_TEXT,
        section="References used in this synthetic dossier",
    )
    doc = _make_doc(DOC_ID_GSPR_CPX1, kind=DocumentKind.GSPR_MAPPING)
    claims = extractor.extract_claims([span], [doc])
    assert claims == [], (
        f"Corpus span {BIB_GSPR_REF010_SPAN_ID} (GSPR REF-010 bibliography entry) "
        f"produced {len(claims)} claims; expected 0: "
        f"{[c.text for c in claims]}"
    )
```

---

### Control note — existing tests

No existing tests in `TestNumericExtraction`, `TestClassificationExtraction`, or
`TestClinicalPerformanceExtraction` need modification. After Strategy C lands, run the
full test suite to confirm they still pass. Bibliography suppression must not affect any
test that uses spans with no bibliography markers (no `REF-\d+.` prefix and no
bibliography section name).

---

### Red-green protocol

Before adding tests 1-4 and 7 to the production test file:

1. Add the tests to `tests/test_extract_claim_extractor.py` with current code.
2. Run `python -m pytest tests/test_extract_claim_extractor.py::TestBibliographySuppression -v`.
3. Confirm tests 1, 2, 3, 4, 7 FAIL (red — no filter exists yet).
4. Confirm tests 5 and 6 PASS (green — no over-firing should exist before or after).
5. Apply Strategy C to `src/locuslab/extract/claim_extractor.py` (add `_BIB_SECTION`,
   `_BIB_PREFIX`, `_is_bibliography_span`, gate in `_extract_from_span`).
6. Rerun — tests 1-4 and 7 must now PASS (green).
7. Rerun full suite `python -m pytest tests/ -v` — all pre-existing tests must still PASS.

---

### `DocumentKind.GSPR_MAPPING` note

Test 7 uses `DocumentKind.GSPR_MAPPING`. Verify this enum value exists in
`locuslab.models.DocumentKind` before adding the test. It is used in the completeness
extractor guard and is expected to exist. If it does not, use `DocumentKind.OTHER` as
a temporary fallback and file a note.
