# DRAFT - REVIEW REQUIRED

## Test Plan — FM-2 Classification Pattern Regression Gates

**Target file:** `tests/test_extract_claim_extractor.py`
**Class to extend:** `TestClassificationExtraction`
**Style reference:** existing `test_classification_extraction` in that class (dataclass-based,
`_make_span` / `_make_doc` helpers, `extractor` fixture).

All tests below are GATED — they must FAIL on the current `patterns.py` and PASS after the
RC-1 regex fix lands. Do not add these tests before verifying the red-green cycle.

---

### New constants to add alongside existing span/doc constants

```python
# FM-2 regression: multi-adjective classification spans (corpus: cardiopatch-x1, 2026-05-22)
CER_IIB_MULTI_ADJ_SPAN_ID = "span_7e7e95e42d14b4de"
CER_IIB_BARE_LABEL_SPAN_ID = "span_668416228dda6a2b"
SSCP_IIB_NO_MEDICAL_SPAN_ID = "span_da304b49e8591d07"
DOC_ID_CER_CPX1 = "doc_2ec6b7b9fdadb3d4"
DOC_ID_SSCP_CPX1 = "doc_d66317f5eb97d245"

CER_IIB_MULTI_ADJ_TEXT = (
    "The CardioPatch X1 is classified as a Class IIb non-invasive active medical device "
    "under MDR rule 10. The product is supplied sterile-free, single-patient use, and "
    "communicates with a validated reader application."
)
CER_IIB_BARE_LABEL_TEXT = "Class IIb (synthetic assumption)"
SSCP_IIB_NO_MEDICAL_TEXT = (
    "This synthetic document is inspired by SSCP structure but CardioPatch X1 is "
    "modelled as a Class IIb non-implantable device. It is included only to test "
    "cross-document consistency and public-facing claim control."
)
```

---

### Tests to add inside `TestClassificationExtraction`

#### Test 1 — Primary RC-1 gate (span 1: multi-adjective chain before `medical device`)

```python
def test_classification_multi_adjective_before_medical_device(self, extractor, cer_doc):
    """RC-1 regression gate: CLASS_IIA must match 'Class IIb non-invasive active medical device'.

    Dogfood run 2026-05-22 / cardiopatch-x1 FM-2.
    Span: span_7e7e95e42d14b4de in doc_2ec6b7b9fdadb3d4 (CER).

    Fails on current CLASS_IIA (single \\w+ token only).
    Passes after CLASS_IIA is relaxed to (?:[\\w-]+\\s+)* before 'medical device'.
    """
    span = _make_span(CER_IIB_MULTI_ADJ_SPAN_ID, DOC_ID_CER_CPX1, CER_IIB_MULTI_ADJ_TEXT)
    doc = _make_doc(DOC_ID_CER_CPX1, kind=DocumentKind.CER)
    claims = extractor.extract_claims([span], [doc])
    class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
    assert class_claims, (
        f"No classification claim; all claims: {[c.text for c in claims]}"
    )
    assert any("Class IIb" in c.text for c in class_claims), (
        f"No 'Class IIb' in classification claims: {[c.text for c in class_claims]}"
    )
    assert any("non-invasive" in c.text or "medical device" in c.text for c in class_claims), (
        f"Matched fragment does not include adjectival chain or 'medical device': "
        f"{[c.text for c in class_claims]}"
    )
```

#### Test 2 — Single-token baseline preserved (existing test, verify not broken by fix)

This test already exists as `test_classification_extraction` using `DEVICE_DESC_TEXT =
"DemoDevice X100 is classified as a Class IIa active medical device ..."`. The RC-1 fix
must not break it. No new test needed — ensure CI runs the existing test after the fix.

#### Test 3 — Hyphenated single adjective (intermediate case)

```python
def test_classification_single_hyphenated_adjective(self, extractor, cer_doc):
    """CLASS_IIA must match 'Class IIb non-invasive medical device' (one hyphenated adjective).

    Validates the (?:[\\w-]+\\s+)* syntax handles \\w-containing tokens correctly.
    Not a corpus span; a constructed regression fixture.
    """
    text = (
        "The patch ECG is classified as a Class IIb non-invasive medical device "
        "per MDR Annex VIII rule 10."
    )
    span = _make_span("span_fm2_hyphen_fixture", DOC_ID_CER, text)
    claims = extractor.extract_claims([span], [cer_doc])
    class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
    assert class_claims, f"No classification claim; claims: {[c.text for c in claims]}"
    assert any("Class IIb" in c.text for c in class_claims)
```

#### Test 4 — False positive gate: `Class IIc` must not match

```python
def test_classification_rejects_class_iic(self, extractor, cer_doc):
    """CLASS_IIA must NOT match 'Class IIc'; IIc is not a valid MDR classification.

    Validates that the character class II[ab]? remains intact after the RC-1 fix.
    """
    text = (
        "The device would theoretically be classified as a Class IIc active medical "
        "device, but this classification does not exist under MDR."
    )
    span = _make_span("span_fm2_iic_fp_fixture", DOC_ID_CER, text)
    claims = extractor.extract_claims([span], [cer_doc])
    class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
    assert not class_claims, (
        f"CLASS_IIA falsely matched 'Class IIc': {[c.text for c in class_claims]}"
    )
```

#### Test 5 — False positive gate: `Class action` must not match

```python
def test_classification_rejects_class_action(self, extractor, cer_doc):
    """CLASS_IIA must NOT match 'Class action ... medical device'."""
    text = (
        "A class action lawsuit was filed regarding a recalled medical device."
    )
    span = _make_span("span_fm2_classaction_fp_fixture", DOC_ID_CER, text)
    claims = extractor.extract_claims([span], [cer_doc])
    class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
    assert not class_claims, (
        f"CLASS_IIA falsely matched 'class action': {[c.text for c in class_claims]}"
    )
```

#### Test 6 — Known gap: bare label `Class IIb (synthetic assumption)` (currently 0, expected 0 until separate pattern lands)

```python
def test_classification_bare_label_not_yet_matched(self, extractor):
    """Negative regression: bare 'Class IIb (synthetic assumption)' produces 0 claims.

    Dogfood 2026-05-22 FM-2 span_668416228dda6a2b. No 'medical device' phrase.
    This is a KNOWN GAP, not a bug that RC-1 fixes. This test documents the boundary:
    it must PASS (remain 0) until a separate bare-label pattern is specified and reviewed.
    Convert to a positive assertion when that pattern lands.
    """
    text = "Class IIb (synthetic assumption)"
    span = _make_span(CER_IIB_BARE_LABEL_SPAN_ID, DOC_ID_CER_CPX1, text)
    doc = _make_doc(DOC_ID_CER_CPX1, kind=DocumentKind.CER)
    claims = extractor.extract_claims([span], [doc])
    class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
    # Known gap: 0 is the correct current result. Remove this assertion when the
    # bare-label pattern is introduced.
    assert class_claims == [], (
        f"Bare label unexpectedly matched (was a new pattern added?): "
        f"{[c.text for c in class_claims]}"
    )
```

#### Test 7 — Known gap: `Class IIb non-implantable device` (no `medical` word)

```python
def test_classification_device_without_medical_word_not_yet_matched(self, extractor):
    """Negative regression: 'Class IIb non-implantable device' (no 'medical') produces 0 claims.

    Dogfood 2026-05-22 FM-2 span_da304b49e8591d07. 'medical' is absent.
    Known gap until CLASS_IIA is further relaxed to make 'medical' optional.
    Convert to a positive assertion with false-positive review when that fix lands.
    """
    text = (
        "CardioPatch X1 is modelled as a Class IIb non-implantable device for "
        "public-facing claim control purposes."
    )
    span = _make_span(SSCP_IIB_NO_MEDICAL_SPAN_ID, DOC_ID_SSCP_CPX1, text)
    doc = _make_doc(DOC_ID_SSCP_CPX1, kind=DocumentKind.SSCP)
    claims = extractor.extract_claims([span], [doc])
    class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
    # Known gap: 0 is the correct current result.
    assert class_claims == [], (
        f"'device' (without 'medical') unexpectedly matched: "
        f"{[c.text for c in class_claims]}"
    )
```

---

### Red-green protocol

Before adding tests 1, 3, 4, 5 to the production test file:

1. Add the test to `tests/test_extract_claim_extractor.py` with the current code.
2. Run `python -m pytest tests/test_extract_claim_extractor.py::TestClassificationExtraction -v`.
3. Confirm test 1 and test 3 FAIL (red). Tests 4, 5 should PASS (no false positives currently either).
4. Apply the RC-1 pattern fix to `patterns.py`.
5. Rerun — tests 1 and 3 must now PASS (green). Tests 4, 5 must still PASS.
6. Tests 6 and 7 must PASS before and after the RC-1 fix (boundary documentation).

---

### `DocumentKind.SSCP` note

Test 7 uses `DocumentKind.SSCP`. Verify this value exists in `locuslab.models.DocumentKind`
before adding the test. If it does not exist yet, use `DocumentKind.OTHER` as a temporary
fallback and file a note to add `SSCP` to the enum.
