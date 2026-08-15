"""Unit tests for ClaimExtractor - written before implementation (TDD)."""

from __future__ import annotations

import pytest

from locuslab.models import (
    ClaimType,
    Document,
    DocumentKind,
    Span,
    SpanLocation,
    SpanLocationKind,
)


def _make_span(
    span_id: str,
    document_id: str,
    text: str,
    kind: SpanLocationKind = SpanLocationKind.PARAGRAPH,
    index: int = 0,
    section: str | None = None,
) -> Span:
    return Span(
        span_id=span_id,
        document_id=document_id,
        location=SpanLocation(kind=kind, index=index),
        text=text,
        section=section,
    )


def _make_doc(document_id: str, kind: DocumentKind = DocumentKind.CER) -> Document:
    return Document(
        document_id=document_id,
        kind=kind,
        path="CER.docx",
        sha256="abc123",
        parser="python-docx",
    )


PIVOTAL_SPAN_ID = "span_d9abfffa43fb7cbf"
ADVERSE_SPAN_ID = "span_5066a18e9866378c"
TABLE_87_SPAN_ID = "span_0f469791718b865b"
TABLE_32_SPAN_ID = "span_cc33a9b3040be134"
DEVICE_DESC_SPAN_ID = "span_79b2f99f4a85ffbd"
SOURCE_P1_SPAN_ID = "span_34348cc49f123629"
SOURCE_P2_SPAN_ID = "span_d5adf35599369595"

DOC_ID_CER = "doc_082f6fd5afc0df84"
DOC_ID_SOURCE = "doc_faf32261b7e7f62a"

PIVOTAL_TEXT = (
    "The primary endpoint response rate of 87.4% (95% CI: 82.1-91.6) "
    "was achieved in (n=412) participants (Smith et al., 2023)."
)
ADVERSE_TEXT = "Adverse event rate was 3.2% (n=412)."
TABLE_87_TEXT = "87.4%"
TABLE_32_TEXT = "3.2%"
DEVICE_DESC_TEXT = (
    "DemoDevice X100 is classified as a Class IIa active medical device "
    "intended for continuous non-invasive monitoring in adult patients."
)
SOURCE_P1_TEXT = (
    "Smith J. et al. (2023) Pivotal study of DemoDevice X100. "
    "Response rate was 87.4 percent at 12 months (n=412)."
)
SOURCE_P2_TEXT = (
    "Adverse event rate was 3.2 percent of the n=412 cohort. "
    "95 percent: 82.1 to 91.6."
)

# FM-2 regression constants (cardiopatch-x1 dogfood 2026-05-22)
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

# MR-1 regression constants (cardiopatch-x1 dogfood 2026-05-22)
BIB_GSPR_REF010_SPAN_ID = "span_d211e0824453201d"
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


@pytest.fixture()
def extractor():  # type: ignore[return]
    from locuslab.extract.claim_extractor import ClaimExtractor

    return ClaimExtractor()


@pytest.fixture()
def cer_doc() -> Document:
    return _make_doc(DOC_ID_CER)


@pytest.fixture()
def source_doc() -> Document:
    return _make_doc(DOC_ID_SOURCE, kind=DocumentKind.SOURCE_PDF)


class TestNumericExtraction:
    def test_equal_percentages_for_distinct_endpoints_remain_distinct(
        self, extractor, cer_doc
    ):
        span = _make_span(
            "span_equal_percentages",
            DOC_ID_CER,
            "Sensitivity was 90.0%. Specificity was also 90.0%.",
        )

        claims = extractor.extract_claims([span], [cer_doc])

        percentages = [
            claim
            for claim in claims
            if claim.claim_type == ClaimType.NUMERIC and claim.text == "90.0%"
        ]
        assert len(percentages) == 2
        assert len({claim.claim_id for claim in percentages}) == 2

    def test_numeric_extraction_from_pivotal_endpoint(self, extractor, cer_doc):
        """GOLD-CLAIM-004: extracts 87.4%, CI, and n= numeric claims from pivotal span."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        claims = extractor.extract_claims([span], [cer_doc])
        numeric_texts = [c.text for c in claims if c.claim_type == ClaimType.NUMERIC]
        # Must find 87.4% somewhere in the extracted numeric claims
        assert any("87.4" in t for t in numeric_texts), f"No 87.4% found in: {numeric_texts}"

    def test_numeric_extraction_from_adverse_event_rate(self, extractor, cer_doc):
        """GOLD-CLAIM-007: extracts 3.2% from adverse event span."""
        span = _make_span(ADVERSE_SPAN_ID, DOC_ID_CER, ADVERSE_TEXT)
        claims = extractor.extract_claims([span], [cer_doc])
        numeric_texts = [c.text for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert any("3.2" in t for t in numeric_texts), f"No 3.2% found in: {numeric_texts}"

    def test_numeric_extraction_from_table_cell(self, extractor, cer_doc):
        """GOLD-CLAIM-009, GOLD-CLAIM-010: extracts from table cells."""
        span_87 = _make_span(
            TABLE_87_SPAN_ID,
            DOC_ID_CER,
            TABLE_87_TEXT,
            kind=SpanLocationKind.TABLE_CELL,
        )
        span_32 = _make_span(
            TABLE_32_SPAN_ID,
            DOC_ID_CER,
            TABLE_32_TEXT,
            kind=SpanLocationKind.TABLE_CELL,
        )
        claims = extractor.extract_claims([span_87, span_32], [cer_doc])
        texts = [c.text for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert any("87.4" in t for t in texts), f"87.4% not extracted: {texts}"
        assert any("3.2" in t for t in texts), f"3.2% not extracted: {texts}"

    def test_numeric_from_source_pdf(self, extractor, source_doc):
        """GOLD-CLAIM-013, GOLD-CLAIM-014: extracts 'percent' form numerics from PDF."""
        span_p1 = _make_span(
            SOURCE_P1_SPAN_ID,
            DOC_ID_SOURCE,
            SOURCE_P1_TEXT,
            kind=SpanLocationKind.PAGE,
        )
        span_p2 = _make_span(
            SOURCE_P2_SPAN_ID,
            DOC_ID_SOURCE,
            SOURCE_P2_TEXT,
            kind=SpanLocationKind.PAGE,
        )
        claims = extractor.extract_claims([span_p1, span_p2], [source_doc])
        texts = [c.text for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert any("87.4" in t for t in texts), f"87.4 percent not extracted: {texts}"
        assert any("3.2" in t for t in texts), f"3.2 percent not extracted: {texts}"


class TestClassificationExtraction:
    def test_classification_extraction(self, extractor, cer_doc):
        """GOLD-CLAIM-001: extracts Class IIa classification claim."""
        span = _make_span(DEVICE_DESC_SPAN_ID, DOC_ID_CER, DEVICE_DESC_TEXT)
        claims = extractor.extract_claims([span], [cer_doc])
        class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
        assert class_claims, f"No classification claim found; claims={[c.text for c in claims]}"
        assert any("Class IIa" in c.text for c in class_claims)

    def test_classification_multi_adjective_before_medical_device(self, extractor):
        """FM-2 RC-1: CLASS_IIA matches 'Class IIb non-invasive active medical device'.

        Dogfood 2026-05-22 cardiopatch-x1 span_7e7e95e42d14b4de (CER).
        """
        span = _make_span(CER_IIB_MULTI_ADJ_SPAN_ID, DOC_ID_CER_CPX1, CER_IIB_MULTI_ADJ_TEXT)
        doc = _make_doc(DOC_ID_CER_CPX1, kind=DocumentKind.CER)
        claims = extractor.extract_claims([span], [doc])
        class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
        assert class_claims, f"No classification claim; claims: {[c.text for c in claims]}"
        assert any("Class IIb" in c.text for c in class_claims)
        assert any("medical device" in c.text.lower() for c in class_claims)

    def test_classification_single_hyphenated_adjective(self, extractor, cer_doc):
        """FM-2 RC-1: tolerates single hyphenated adjective ('non-invasive medical device')."""
        text = (
            "The patch ECG is classified as a Class IIb non-invasive medical device "
            "per MDR Annex VIII rule 10."
        )
        span = _make_span("span_fm2_hyphen_fixture", DOC_ID_CER, text)
        claims = extractor.extract_claims([span], [cer_doc])
        class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
        assert class_claims, f"No classification claim; claims: {[c.text for c in claims]}"
        assert any("Class IIb" in c.text for c in class_claims)

    def test_classification_rejects_class_iic(self, extractor, cer_doc):
        """FM-2 false-positive gate: 'Class IIc' is not a valid MDR class."""
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

    def test_classification_rejects_class_action(self, extractor, cer_doc):
        """FM-2 false-positive gate: 'class action ... medical device' must not match."""
        text = "A class action lawsuit was filed regarding a recalled medical device."
        span = _make_span("span_fm2_classaction_fp_fixture", DOC_ID_CER, text)
        claims = extractor.extract_claims([span], [cer_doc])
        class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
        assert not class_claims, (
            f"CLASS_IIA falsely matched 'class action': {[c.text for c in class_claims]}"
        )

    def test_classification_bare_label_not_yet_matched(self, extractor):
        """FM-2 known gap: bare 'Class IIb (synthetic assumption)' yields 0 claims.

        No 'medical device' phrase. Must remain 0 until a bare-label pattern lands
        with its own false-positive review. Convert to positive when that pattern exists.
        """
        span = _make_span(CER_IIB_BARE_LABEL_SPAN_ID, DOC_ID_CER_CPX1, CER_IIB_BARE_LABEL_TEXT)
        doc = _make_doc(DOC_ID_CER_CPX1, kind=DocumentKind.CER)
        claims = extractor.extract_claims([span], [doc])
        class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
        assert class_claims == [], (
            f"Bare label unexpectedly matched (new pattern landed?): "
            f"{[c.text for c in class_claims]}"
        )

    def test_classification_device_without_medical_word_not_yet_matched(self, extractor):
        """FM-2 known gap: 'Class IIb non-implantable device' yields 0 claims.

        'medical' is absent. Must remain 0 until CLASS_IIA makes 'medical' optional
        with its own false-positive review.
        """
        span = _make_span(SSCP_IIB_NO_MEDICAL_SPAN_ID, DOC_ID_SSCP_CPX1, SSCP_IIB_NO_MEDICAL_TEXT)
        doc = _make_doc(DOC_ID_SSCP_CPX1, kind=DocumentKind.SSCP)
        claims = extractor.extract_claims([span], [doc])
        class_claims = [c for c in claims if c.claim_type == ClaimType.CLASSIFICATION]
        assert class_claims == [], (
            f"'device' (without 'medical') unexpectedly matched: "
            f"{[c.text for c in class_claims]}"
        )


class TestClinicalPerformanceExtraction:
    def test_clinical_performance_extraction(self, extractor, cer_doc):
        """GOLD-CLAIM-003: extracts clinical_performance claim from pivotal span."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        claims = extractor.extract_claims([span], [cer_doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims, f"No clinical_performance claim; claims={[c.claim_type for c in claims]}"


class TestIdStability:
    def test_claim_ids_are_stable_across_runs(self, extractor, cer_doc):
        """Stability invariant: two identical calls produce identical IDs."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        claims1 = extractor.extract_claims([span], [cer_doc])
        claims2 = extractor.extract_claims([span], [cer_doc])
        ids1 = {c.claim_id for c in claims1}
        ids2 = {c.claim_id for c in claims2}
        assert ids1 == ids2, "IDs differ across identical calls"

    def test_claim_ids_differ_for_mirror_spans(self, extractor, cer_doc):
        """Collision avoidance: same text in different spans gets distinct IDs."""
        span_body = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, TABLE_87_TEXT)
        span_table = _make_span(
            TABLE_87_SPAN_ID,
            DOC_ID_CER,
            TABLE_87_TEXT,
            kind=SpanLocationKind.TABLE_CELL,
        )
        claims = extractor.extract_claims([span_body, span_table], [cer_doc])
        numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        ids = [c.claim_id for c in numeric_claims]
        assert len(ids) == len(set(ids)), f"Duplicate claim IDs for mirror spans: {ids}"


class TestFalsePositives:
    def test_no_false_positive_on_parenthetical_statistics(self, extractor, cer_doc):
        """(n=412) must NOT be extracted as a citation claim."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        claims = extractor.extract_claims([span], [cer_doc])
        citation_texts = [c.text for c in claims if c.claim_type == ClaimType.CITATION]
        assert not any("n=412" in t for t in citation_texts), (
            f"(n=412) falsely matched as citation: {citation_texts}"
        )


class TestClinicalPerformanceDeduplication:
    """W3 regression: multiple keywords whose context windows yield the same
    normalized text must collapse into a single claim."""

    def test_overlapping_keywords_produce_single_claim(self, extractor, cer_doc):
        text = (
            "The pivotal study (Smith et al., 2023) reported a primary "
            "endpoint response rate of 87.4% (95% CI: 82.1-91.6) at 12 "
            "months in 412 patients."
        )
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, text)
        claims = extractor.extract_claims([span], [cer_doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        texts = [c.text for c in cp_claims]
        assert len(set(texts)) == len(texts), (
            f"Duplicate clinical_performance text on same span: {texts}"
        )

    def test_distinct_keyword_windows_still_emit_separate_claims(self, extractor, cer_doc):
        text = (
            "Section A. " + "x" * 200 + " primary endpoint achieved. "
            + "y" * 200 + " Adverse safety profile was observed."
        )
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, text)
        claims = extractor.extract_claims([span], [cer_doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        texts = {c.text for c in cp_claims}
        assert len(texts) == len(cp_claims), (
            f"Dedup collapsed claims that should remain distinct: {[c.text for c in cp_claims]}"
        )


class TestCompletenessGating:
    """W4 regression: COMPLETENESS only fires for GSPR rows lacking an
    Evidence_Document cell. Rows with a present-or-missing Evidence_Document
    value are a Phase 3 source-availability concern, not a Phase 2 claim."""

    def _gspr_doc(self) -> Document:
        return Document(
            document_id="doc_gspr_test",
            kind=DocumentKind.GSPR_MAPPING,
            path="GSPR.xlsx",
            sha256="x",
            parser="openpyxl",
        )

    def _req_span(self, row: int, text: str) -> Span:
        return Span(
            span_id=f"span_req_{row}",
            document_id="doc_gspr_test",
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=row * 5,
                label=f"GSPR:B{row}",
            ),
            text=text,
            section="GSPR:header:B=Requirement",
        )

    def _evidence_span(self, row: int, text: str) -> Span:
        return Span(
            span_id=f"span_ev_{row}",
            document_id="doc_gspr_test",
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=row * 5 + 2,
                label=f"GSPR:D{row}",
            ),
            text=text,
            section="GSPR:header:D=Evidence_Document",
        )

    def _applicable_span(self, row: int, text: str) -> Span:
        return Span(
            span_id=f"span_applicable_{row}",
            document_id="doc_gspr_test",
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=row * 5 + 1,
                label=f"GSPR:C{row}",
            ),
            text=text,
            section="GSPR:header:C=Applicable",
        )

    def _status_span(self, row: int, text: str) -> Span:
        return Span(
            span_id=f"span_status_{row}",
            document_id="doc_gspr_test",
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=row * 5 + 3,
                label=f"GSPR:E{row}",
            ),
            text=text,
            section="GSPR:header:E=Status",
        )

    def test_row_with_evidence_doc_does_not_emit_completeness(self, extractor):
        spans = [
            self._req_span(2, "Risk management process documented"),
            self._applicable_span(2, "Yes"),
            self._evidence_span(2, "CER.docx"),
        ]
        claims = extractor.extract_claims(spans, [self._gspr_doc()])
        completeness = [c for c in claims if c.claim_type == ClaimType.COMPLETENESS]
        assert completeness == [], (
            f"COMPLETENESS fired on row with evidence doc: {[c.text for c in completeness]}"
        )

    def test_row_without_evidence_doc_emits_completeness(self, extractor):
        spans = [
            self._req_span(6, "Software lifecycle per IEC 62304"),
            self._applicable_span(6, "Yes"),
        ]
        claims = extractor.extract_claims(spans, [self._gspr_doc()])
        completeness = [c for c in claims if c.claim_type == ClaimType.COMPLETENESS]
        assert len(completeness) == 1, (
            f"Expected one COMPLETENESS claim; got {[c.text for c in completeness]}"
        )

    def test_mixed_rows_only_gapped_row_emits(self, extractor):
        spans = [
            self._req_span(2, "Risk management process documented"),
            self._applicable_span(2, "Yes"),
            self._evidence_span(2, "CER.docx"),
            self._req_span(3, "Clinical evaluation according to Annex XIV"),
            self._applicable_span(3, "Yes"),
            self._evidence_span(3, "CER.docx"),
            self._req_span(6, "Software lifecycle per IEC 62304"),
            self._applicable_span(6, "Yes"),
        ]
        claims = extractor.extract_claims(spans, [self._gspr_doc()])
        completeness = [c for c in claims if c.claim_type == ClaimType.COMPLETENESS]
        assert len(completeness) == 1
        assert completeness[0].text == "Software lifecycle per IEC 62304"

    @pytest.mark.parametrize(
        ("applicable", "status"),
        [("No", "Not Applicable"), ("Yes", "Not Applicable"), ("", "")],
    )
    def test_non_applicable_or_ambiguous_row_does_not_emit_completeness(
        self, extractor, applicable: str, status: str
    ):
        spans = [self._req_span(7, "Requirement without evidence")]
        if applicable:
            spans.append(self._applicable_span(7, applicable))
        if status:
            spans.append(self._status_span(7, status))

        claims = extractor.extract_claims(spans, [self._gspr_doc()])

        completeness = [c for c in claims if c.claim_type == ClaimType.COMPLETENESS]
        assert completeness == []


class TestBibliographySuppression:
    """MR-1 regression: bibliography spans must not produce claims.

    Strategy C: combined section guard + REF-NNN. text-prefix guard.
    """

    def test_bib_span_ref_prefix_produces_zero_claims(self, extractor, cer_doc):
        span = _make_span("span_mr1_ref001_fixture", DOC_ID_CER, BIB_REF001_TEXT)
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims == [], (
            f"Expected 0 claims from bibliography span; got {len(claims)}: "
            f"{[c.text for c in claims]}"
        )

    def test_bib_span_leading_whitespace_produces_zero_claims(self, extractor, cer_doc):
        span = _make_span(
            "span_mr1_leading_ws_fixture", DOC_ID_CER, BIB_LEADING_WHITESPACE_TEXT
        )
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims == [], (
            f"Leading whitespace bypassed filter; got {len(claims)}: "
            f"{[c.text for c in claims]}"
        )

    def test_bib_section_with_percentage_produces_zero_claims(self, extractor, cer_doc):
        span = _make_span(
            "span_mr1_ref_section_pct_fixture",
            DOC_ID_CER,
            BIB_REF018_TEXT,
            section="References used in this synthetic dossier",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims == [], (
            f"Section guard failed; got {len(claims)}: {[c.text for c in claims]}"
        )

    def test_bib_section_bibliography_produces_zero_claims(self, extractor, cer_doc):
        span = _make_span(
            "span_mr1_bibliography_section_fixture",
            DOC_ID_CER,
            BIB_REF012_TEXT,
            section="Bibliography",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims == [], (
            f"'Bibliography' section did not suppress; got {len(claims)}: "
            f"{[c.text for c in claims]}"
        )

    def test_body_inline_ref_mention_still_extracts(self, extractor, cer_doc):
        """Sanity: inline REF-NNN mention in body must NOT be suppressed."""
        span = _make_span(
            "span_mr1_inline_ref_body_fixture",
            DOC_ID_CER,
            BODY_INLINE_REF_TEXT,
            section="6. Clinical performance evidence",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert numeric_claims, (
            f"Inline body REF mention incorrectly suppressed; got: {claims}"
        )
        assert any("94.8" in c.text for c in numeric_claims)

    def test_body_clinical_performance_section_not_suppressed(self, extractor, cer_doc):
        """Sanity: body span in a CP section must not be suppressed."""
        span = _make_span(
            "span_mr1_body_cp_fixture",
            DOC_ID_CER,
            BODY_CP_TEXT,
            section="5. Clinical Performance",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert numeric_claims, (
            f"Body CP span incorrectly suppressed; got: {claims}"
        )

    def test_corpus_anchor_gspr_ref010_produces_zero_claims(self, extractor):
        """Corpus-anchored: GSPR REF-010 span (cardiopatch-x1 2026-05-22)."""
        span = _make_span(
            BIB_GSPR_REF010_SPAN_ID,
            DOC_ID_GSPR_CPX1,
            BIB_REF010_TEXT,
            section="References used in this synthetic dossier",
        )
        doc = _make_doc(DOC_ID_GSPR_CPX1, kind=DocumentKind.GSPR_MAPPING)
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], (
            f"Corpus span {BIB_GSPR_REF010_SPAN_ID} produced {len(claims)} claims; "
            f"expected 0: {[c.text for c in claims]}"
        )


class TestHeadingSuppression:
    """MR-3 regression: paragraph spans that are section headings produce no claims.

    A heading paragraph is detected when span.text.strip() equals span.section.strip()
    and the location kind is paragraph. The docx_reader emits headings this way.
    """

    def test_heading_with_clinical_performance_keyword_yields_zero(self, extractor, cer_doc):
        span = _make_span(
            "span_mr3_heading_cp_fixture",
            DOC_ID_CER,
            "6. Clinical performance evidence",
            section="6. Clinical performance evidence",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims == [], (
            f"Heading produced claims: {[c.text for c in claims]}"
        )

    def test_heading_with_intended_purpose_keyword_yields_zero(self, extractor, cer_doc):
        span = _make_span(
            "span_mr3_heading_intent_fixture",
            DOC_ID_CER,
            "2. Device identification and intended purpose",
            section="2. Device identification and intended purpose",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims == [], (
            f"Intended-purpose heading produced claims: {[c.text for c in claims]}"
        )

    def test_body_paragraph_with_cp_keyword_still_extracts(self, extractor, cer_doc):
        """Sanity: body paragraph under a CP heading still extracts."""
        span = _make_span(
            "span_mr3_body_cp_fixture",
            DOC_ID_CER,
            (
                "The CardioPatch X1 demonstrated a primary endpoint response rate of "
                "91.2% in the PMCF registry cohort."
            ),
            section="6. Clinical performance evidence",
        )
        claims = extractor.extract_claims([span], [cer_doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims, f"Body CP paragraph incorrectly suppressed: {claims}"

    def test_heading_without_section_set_still_extracts(self, extractor, cer_doc):
        """A paragraph with no section cannot be a heading; extraction proceeds."""
        text = "The device exhibits a primary endpoint response rate of 91.2%."
        span = _make_span("span_mr3_no_section_fixture", DOC_ID_CER, text, section=None)
        claims = extractor.extract_claims([span], [cer_doc])
        assert claims, "Claims should extract from a non-heading paragraph"

    def test_corpus_anchor_cer_cp_heading_yields_zero(self, extractor, cer_doc):
        """Corpus-anchored: real CER heading span from cardiopatch-x1 dogfood 2026-05-22."""
        span = _make_span(
            "span_75b813d7ac3a2f53",
            "doc_2ec6b7b9fdadb3d4",
            "6. Clinical performance evidence",
            section="6. Clinical performance evidence",
        )
        doc = _make_doc("doc_2ec6b7b9fdadb3d4", kind=DocumentKind.CER)
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"Corpus heading produced claims: {[c.text for c in claims]}"


class TestPhase2ANativeNoiseGates:
    """Phase 2A native-extractor gates for PDF and guidance-shaped noise."""

    def test_pdf_table_of_contents_page_yields_zero_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_toc_page",
            "doc_mdcg_guidance_other",
            (
                "Table of contents\n"
                "1 Scope ................................................ 3\n"
                "2 Device identification and intended purpose ............ 5\n"
                "5 Clinical performance and PMCF information ............ 13\n"
                "7 References ........................................... 21\n"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"TOC page produced claims: {[c.text for c in claims]}"

    def test_pdf_numbered_references_page_yields_zero_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_numbered_refs",
            "doc_mdcg_guidance_other",
            (
                "References\n"
                "1. Smith J. et al. Clinical performance review of cardiac monitors. 2023. "
                "Sensitivity was 94.8% in the validation cohort.\n"
                "2. Patel R. Post-market clinical follow-up methods. 2024. "
                "Specificity was 96.1% in Table 4.\n"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"References page produced claims: {[c.text for c in claims]}"

    def test_pdf_headerless_numbered_references_page_yields_zero_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_headerless_numbered_refs",
            "doc_mdcg_guidance_other",
            (
                "1. Smith J. et al. Clinical performance review of cardiac monitors. 2023. "
                "Sensitivity was 94.8% in the validation cohort.\n"
                "2. Patel R. Post-market clinical follow-up methods. 2024. "
                "Specificity was 96.1% in Table 4.\n"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], (
            f"Headerless numbered references page produced claims: {[c.text for c in claims]}"
        )

    def test_pdf_heading_without_section_yields_zero_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_pdf_heading",
            "doc_mdcg_guidance_other",
            "5. Clinical performance and post-market clinical follow-up",
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"PDF heading produced claims: {[c.text for c in claims]}"

    def test_short_pdf_chrome_with_page_marker_yields_zero_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_pdf_chrome",
            "doc_mdcg_guidance_other",
            (
                "Medical Device Coordination Group Document MDCG 2019-9 Rev.1\n"
                "Clinical performance\n"
                "3(24)"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"PDF chrome produced claims: {[c.text for c in claims]}"

    def test_appendix_template_placeholder_yields_zero_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_appendix_template",
            "doc_mdcg_guidance_other",
            (
                "Appendix A\n"
                "[Insert device name]\n"
                "[Insert clinical performance summary]\n"
                "[Insert source basis]"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"Appendix template produced claims: {[c.text for c in claims]}"

    def test_guidance_meta_text_yields_zero_manufacturer_claims(self, extractor):
        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_guidance_meta",
            "doc_mdcg_guidance_other",
            (
                "This guidance describes how the SSCP should present clinical performance "
                "information. The manufacturer should ensure that the summary is objective "
                "and aligned with the clinical evaluation report."
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        assert claims == [], f"Guidance meta text produced claims: {[c.text for c in claims]}"

    def test_manufacturer_clinical_performance_body_still_extracts(self, extractor):
        doc = _make_doc("doc_manufacturer_cer", kind=DocumentKind.CER)
        span = _make_span(
            "span_phase2a_manufacturer_body",
            "doc_manufacturer_cer",
            (
                "The CardioPatch X1 demonstrated clinical performance with sensitivity "
                "of 94.8% and specificity of 96.1% in the pivotal validation cohort."
            ),
            kind=SpanLocationKind.PARAGRAPH,
            section="6. Clinical performance evidence",
        )
        claims = extractor.extract_claims([span], [doc])
        assert any(c.claim_type == ClaimType.CLINICAL_PERFORMANCE for c in claims), (
            f"Manufacturer body span was over-suppressed: {[c.text for c in claims]}"
        )

    def test_guidance_suppression_is_observable_with_reason(self):
        from locuslab.extract.span_filters import classify_span_for_claim_extraction

        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_guidance_reason",
            "doc_mdcg_guidance_other",
            "This guidance should describe clinical performance information.",
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        decision = classify_span_for_claim_extraction(span, doc)
        assert decision.suppress_claim_extraction is True
        assert decision.reasons == ("guidance_meta",)
        assert decision.retain_as_source_anchor is True

    def test_guidance_claim_suppression_preserves_citation_markers(self, extractor):
        from locuslab.extract.citation_parser import CitationParser

        doc = _make_doc("doc_mdcg_guidance_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_guidance_with_citation",
            "doc_mdcg_guidance_other",
            (
                "This guidance should summarize clinical performance information "
                "from the clinical evaluation (Smith et al., 2023)."
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        mentions = CitationParser().parse_citations([span])
        assert claims == [], f"Guidance span produced manufacturer claims: {claims}"
        assert any(m["normalized_key"] == "smith_2023" for m in mentions), (
            f"Guidance citation marker was lost: {mentions}"
        )

    def test_manufacturer_body_mentions_guidance_still_extracts(self, extractor):
        doc = _make_doc("doc_manufacturer_cer", kind=DocumentKind.CER)
        span = _make_span(
            "span_phase2a_manufacturer_guidance_body",
            "doc_manufacturer_cer",
            (
                "Following MDCG guidance, the manufacturer should present the device "
                "clinical performance results. The CardioPatch X1 demonstrated "
                "sensitivity of 94.8% in the pivotal validation cohort."
            ),
            kind=SpanLocationKind.PARAGRAPH,
            section="6. Clinical performance evidence",
        )
        claims = extractor.extract_claims([span], [doc])
        assert any(c.claim_type == ClaimType.CLINICAL_PERFORMANCE for c in claims), (
            f"Manufacturer guidance-context body was over-suppressed: {claims}"
        )

    def test_manufacturer_guidance_path_token_still_extracts(self, extractor):
        doc = Document(
            document_id="doc_manufacturer_cer_guidance_path",
            kind=DocumentKind.CER,
            path="templates/guidance/CER.docx",
            sha256="abc123",
            parser="python-docx",
        )
        span = _make_span(
            "span_phase2a_manufacturer_guidance_path",
            "doc_manufacturer_cer_guidance_path",
            (
                "Following MDCG guidance, the manufacturer should present the device "
                "clinical performance results. The CardioPatch X1 demonstrated "
                "sensitivity of 94.8% in the pivotal validation cohort."
            ),
            kind=SpanLocationKind.PARAGRAPH,
            section="6. Clinical performance evidence",
        )
        claims = extractor.extract_claims([span], [doc])
        assert any(c.claim_type == ClaimType.CLINICAL_PERFORMANCE for c in claims), (
            f"Manufacturer path token caused over-suppression: {claims}"
        )

    def test_numbered_manufacturer_body_page_still_extracts(self, extractor):
        doc = _make_doc("doc_manufacturer_cer", kind=DocumentKind.CER)
        span = _make_span(
            "span_phase2a_numbered_body",
            "doc_manufacturer_cer",
            (
                "1. The 2023 pivotal validation cohort demonstrated sensitivity of "
                "94.8% for the primary endpoint.\n"
                "2. The 2024 PMCF registry demonstrated specificity of 96.1% during "
                "clinical performance follow-up.\n"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert any("94.8" in c.text for c in numeric_claims), (
            f"Numbered body page lost 94.8% claim: {claims}"
        )
        assert any("96.1" in c.text for c in numeric_claims), (
            f"Numbered body page lost 96.1% claim: {claims}"
        )

    def test_numbered_body_with_author_initial_still_extracts(self, extractor):
        doc = _make_doc("doc_manufacturer_cer", kind=DocumentKind.CER)
        span = _make_span(
            "span_phase2a_numbered_body_author_initial",
            "doc_manufacturer_cer",
            (
                "1. Jones A. validated the 2023 protocol and the CardioPatch X1 "
                "achieved sensitivity of 94.8% in the validation cohort.\n"
                "2. Smith J. confirmed the 2024 PMCF cohort and the device "
                "achieved specificity of 96.1% across the registry.\n"
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert any("94.8" in c.text for c in numeric_claims), (
            f"Author-initial body page over-suppressed 94.8% claim: {claims}"
        )
        assert any("96.1" in c.text for c in numeric_claims), (
            f"Author-initial body page over-suppressed 96.1% claim: {claims}"
        )

    def test_other_doc_mentions_guidance_without_modal_still_extracts(self, extractor):
        doc = _make_doc("doc_manufacturer_ifu_other", kind=DocumentKind.OTHER)
        span = _make_span(
            "span_phase2a_other_doc_guidance_no_modal",
            "doc_manufacturer_ifu_other",
            (
                "According to guidance document MDCG 2019-9, the CardioPatch X1 "
                "demonstrated sensitivity of 94.8% in the pivotal validation "
                "cohort and achieved specificity of 96.1% in the PMCF registry."
            ),
            kind=SpanLocationKind.PAGE,
            section=None,
        )
        claims = extractor.extract_claims([span], [doc])
        numeric_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        assert any("94.8" in c.text for c in numeric_claims), (
            f"OTHER-doc body mentioning guidance was over-suppressed: {claims}"
        )
