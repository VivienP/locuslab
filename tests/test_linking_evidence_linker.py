"""Unit tests for EvidenceLinker - written before implementation (TDD)."""

from __future__ import annotations

import pytest

from locuslab.models import (
    Claim,
    ClaimType,
    ConfidenceLabel,
    Source,
    Span,
    SpanLocation,
    SpanLocationKind,
)


def _make_span(
    span_id: str,
    document_id: str,
    text: str,
    kind: SpanLocationKind = SpanLocationKind.PARAGRAPH,
    section: str | None = None,
) -> Span:
    return Span(
        span_id=span_id,
        document_id=document_id,
        location=SpanLocation(kind=kind, index=0),
        text=text,
        section=section,
    )


def _make_claim(
    claim_id: str,
    document_id: str,
    span_id: str,
    text: str,
    claim_type: ClaimType,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        document_id=document_id,
        span_id=span_id,
        text=text,
        claim_type=claim_type,
        extraction_method="test",
        confidence_label=ConfidenceLabel.HIGH,
    )


def _make_source(
    source_id: str,
    path: str | None,
    citation_key: str | None,
    availability_status: str,
) -> Source:
    return Source(
        source_id=source_id,
        path=path,
        citation_key=citation_key,
        availability_status=availability_status,
    )


DOC_ID_CER = "doc_1dd5a3cd674157b5"
PIVOTAL_SPAN_ID = "span_b0fecd4907e13acc"
BENEFIT_RISK_SPAN_ID = "span_05f0a0e4c6224e9f"
DEVICE_DESC_SPAN_ID = "span_a3d42d0561575263"
GSPR03_SPAN_ID = "span_ecbca6c827a929d4"


@pytest.fixture()
def linker():  # type: ignore[return]
    from locuslab.linking.evidence_linker import EvidenceLinker

    return EvidenceLinker()


@pytest.fixture()
def parser():  # type: ignore[return]
    from locuslab.extract.citation_parser import CitationParser

    return CitationParser()


class TestResolvedLink:
    def test_resolved_link_for_pivotal_endpoint(self, linker, parser):
        """GOLD-EVIDENCE-001: claim from pivotal span with (Smith et al., 2023) gets resolved."""
        pivotal_text = (
            "The primary endpoint response rate of 87.4% (95% CI: 82.1-91.6) "
            "was achieved in (n=412) participants (Smith et al., 2023)."
        )
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, pivotal_text)
        citations = parser.parse_citations([span])

        claim = _make_claim(
            "claim_test_001",
            DOC_ID_CER,
            PIVOTAL_SPAN_ID,
            "87.4% response rate",
            ClaimType.CLINICAL_PERFORMANCE,
        )
        smith_source = _make_source(
            "src_test_001",
            "bibliography/source-study.pdf",
            "smith_2023",
            "local_fulltext",
        )

        links = linker.link(
            claims=[claim],
            citations=citations,
            sources=[smith_source],
        )
        resolved_links = [lk for lk in links if lk.status == "resolved"]
        assert resolved_links, (
            f"No resolved links; all links={[(lk.status, lk.claim_id) for lk in links]}"
        )
        assert resolved_links[0].claim_id == "claim_test_001"
        assert resolved_links[0].source_id == "src_test_001"

    def test_duplicate_citation_key_is_ambiguous_and_order_independent(
        self, linker, parser
    ):
        span = _make_span(
            PIVOTAL_SPAN_ID,
            DOC_ID_CER,
            "Performance was reported by (Smith et al., 2023).",
        )
        citations = parser.parse_citations([span])
        claim = _make_claim(
            "claim_ambiguous",
            DOC_ID_CER,
            PIVOTAL_SPAN_ID,
            "Performance was reported",
            ClaimType.CLINICAL_PERFORMANCE,
        )
        sources = [
            _make_source("src_b", "bibliography/b.pdf", "smith_2023", "local_fulltext"),
            _make_source("src_a", "bibliography/a.pdf", "smith_2023", "local_fulltext"),
        ]

        first = linker.link([claim], citations, sources)[0]
        second = linker.link([claim], citations, list(reversed(sources)))[0]

        assert first == second
        assert first.status == "source_ambiguous"
        assert first.source_id is None
        assert first.linking_method == "explicit_citation_ambiguous"
        assert first.candidate_source_ids == ("src_a", "src_b")


class TestSourceUnresolved:
    def test_source_unresolved_for_bracketed_numeric(self, linker, parser):
        """GOLD-EVIDENCE-004: [1] citation with no numbered references = source_unresolved."""
        benefit_risk_text = (
            "The benefit-risk profile of DemoDevice X100 is considered acceptable [1]."
        )
        span = _make_span(BENEFIT_RISK_SPAN_ID, DOC_ID_CER, benefit_risk_text)
        citations = parser.parse_citations([span])

        claim = _make_claim(
            "claim_test_004",
            DOC_ID_CER,
            BENEFIT_RISK_SPAN_ID,
            "benefit-risk profile is acceptable",
            ClaimType.BENEFIT_RISK,
        )
        links = linker.link(
            claims=[claim],
            citations=citations,
            sources=[],
        )
        unresolved_links = [lk for lk in links if lk.status == "source_unresolved"]
        assert unresolved_links, (
            f"No source_unresolved links; all={[(lk.status,) for lk in links]}"
        )


class TestManualReviewRequired:
    def test_manual_review_for_classification(self, linker, parser):
        """GOLD-EVIDENCE-005: classification claim with no citation = manual_review_required."""
        device_text = "DemoDevice X100 is classified as a Class IIa active medical device."
        span = _make_span(DEVICE_DESC_SPAN_ID, DOC_ID_CER, device_text)
        citations = parser.parse_citations([span])

        claim = _make_claim(
            "claim_test_005",
            DOC_ID_CER,
            DEVICE_DESC_SPAN_ID,
            "Class IIa active medical device",
            ClaimType.CLASSIFICATION,
        )
        links = linker.link(
            claims=[claim],
            citations=citations,
            sources=[],
        )
        manual_links = [lk for lk in links if lk.status == "manual_review_required"]
        assert manual_links, (
            f"No manual_review_required links; all={[(lk.status,) for lk in links]}"
        )


class TestSourceMissing:
    def test_source_missing_for_gspr_reference(self, linker, parser):
        """GOLD-EVIDENCE-GSPR-03: missing file Source produces source_missing link.

        GSPR row 3 has a Requirement cell at B3 and an Evidence_Document cell
        at D3. The linker pairs them by the row number parsed from
        ``SpanLocation.label`` (Phase 1b xlsx_reader provenance), not by
        serial cell index.
        """
        req_span = Span(
            span_id=GSPR03_SPAN_ID,
            document_id=DOC_ID_CER,
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=16,
                label="GSPR:B3",
            ),
            text="Post-market surveillance plan in place",
            section="GSPR:header:B=Requirement",
        )
        evdoc_span = Span(
            span_id="span_evdoc_pms",
            document_id=DOC_ID_CER,
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=18,
                label="GSPR:D3",
            ),
            text="PMS.docx",
            section="GSPR:header:D=Evidence_Document",
        )
        spans = [req_span, evdoc_span]
        citations = parser.parse_citations(spans)

        pms_source = _make_source(
            "src_test_pms",
            "PMS.docx",
            None,
            "missing_file",
        )
        # Completeness claim anchored on the requirement span
        claim = _make_claim(
            "claim_test_gspr",
            DOC_ID_CER,
            GSPR03_SPAN_ID,
            "Post-market surveillance plan in place",
            ClaimType.COMPLETENESS,
        )
        links = linker.link(
            claims=[claim],
            citations=citations,
            sources=[pms_source],
            spans=spans,
        )
        missing_links = [lk for lk in links if lk.status == "source_missing"]
        assert missing_links, (
            f"No source_missing links; all={[(lk.status,) for lk in links]}"
        )


class TestSparseGsprPairing:
    """W3 regression: GSPR row pairing must be anchored on Phase 1b span
    label provenance, not on serial cell index. Index-based pairing
    (`req_idx + 2 == evdoc_idx`) silently desynchronizes when the
    xlsx_reader skips empty intermediate cells or when row numbers are
    non-contiguous."""

    DOC_ID = "doc_gspr_sparse"

    def _req(self, row: int, idx: int, text: str, document_id: str | None = None) -> Span:
        return Span(
            span_id=f"span_req_{document_id or self.DOC_ID}_{row}",
            document_id=document_id or self.DOC_ID,
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=idx,
                label=f"Sheet1:B{row}",
            ),
            text=text,
            section="GSPR:header:B=Requirement",
        )

    def _evdoc(
        self, row: int, idx: int, text: str, document_id: str | None = None
    ) -> Span:
        return Span(
            span_id=f"span_evdoc_{document_id or self.DOC_ID}_{row}",
            document_id=document_id or self.DOC_ID,
            location=SpanLocation(
                kind=SpanLocationKind.TABLE_CELL,
                index=idx,
                label=f"Sheet1:D{row}",
            ),
            text=text,
            section="GSPR:header:D=Evidence_Document",
        )

    def _completeness_claim(
        self, row: int, text: str, document_id: str | None = None
    ) -> Claim:
        doc = document_id or self.DOC_ID
        return _make_claim(
            f"claim_row_{doc}_{row}",
            doc,
            f"span_req_{doc}_{row}",
            text,
            ClaimType.COMPLETENESS,
        )

    def test_sparse_row_pairs_by_label_not_index(self, linker):
        """Row 5 has B5 and D5 but no C5. xlsx_reader skips empty C5, so the
        running index gap between B5 and D5 is 1, not 2. Index-based pairing
        (`req_idx + 2`) would miss D5. Label-based pairing finds D5 by row."""
        req = self._req(5, 10, "Software lifecycle compliance")
        evdoc = self._evdoc(5, 11, "MissingDoc.pdf")  # idx 11, not 12
        spans = [req, evdoc]
        claim = self._completeness_claim(5, "Software lifecycle compliance")
        source = _make_source("src_missing", "MissingDoc.pdf", None, "missing_file")

        links = linker.link(
            claims=[claim],
            citations=[],
            sources=[source],
            spans=spans,
        )
        assert len(links) == 1
        assert links[0].status == "source_missing"
        assert links[0].source_id == "src_missing"
        assert links[0].linking_method == "filename_reference"

    def test_row_without_evidence_doc_yields_source_missing_with_none(self, linker):
        """Row 6 has B6 only — no D6 at all. Result: source_missing,
        source_id=None, linking_method=no_link_found."""
        req = self._req(6, 20, "Requirement with no evidence doc")
        claim = self._completeness_claim(6, "Requirement with no evidence doc")

        links = linker.link(
            claims=[claim],
            citations=[],
            sources=[],
            spans=[req],
        )
        assert len(links) == 1
        assert links[0].status == "source_missing"
        assert links[0].source_id is None
        assert links[0].linking_method == "no_link_found"

    def test_non_contiguous_row_numbers_paired_correctly(self, linker):
        """Rows 3, 5, 8 each pair with their own D cell — missing rows
        4, 6, 7 do not break alignment."""
        rows = [
            (3, "Req at row 3", "EvA.docx"),
            (5, "Req at row 5", "EvB.docx"),
            (8, "Req at row 8", "EvC.docx"),
        ]
        spans: list[Span] = []
        claims: list[Claim] = []
        sources: list[Source] = []
        running_idx = 100
        for row, req_text, ev_text in rows:
            spans.append(self._req(row, running_idx, req_text))
            running_idx += 1
            spans.append(self._evdoc(row, running_idx, ev_text))
            running_idx += 1
            claims.append(self._completeness_claim(row, req_text))
            sources.append(_make_source(f"src_{row}", ev_text, None, "missing_file"))

        links = linker.link(
            claims=claims,
            citations=[],
            sources=sources,
            spans=spans,
        )
        by_claim = {lk.claim_id: lk for lk in links}
        assert len(links) == 3
        for row, _req, _ev_text in rows:
            claim_id = f"claim_row_{self.DOC_ID}_{row}"
            assert by_claim[claim_id].status == "source_missing"
            assert by_claim[claim_id].source_id == f"src_{row}", (
                f"Row {row} paired with wrong source: {by_claim[claim_id].source_id}"
            )

    def test_multi_document_gspr_no_cross_pair(self, linker):
        """Two GSPR documents both have row 5. Pairing must not cross
        document boundaries — doc1's B5 must not pair with doc2's D5."""
        doc1_req = self._req(5, 10, "Doc1 row 5 requirement", document_id="doc1")
        doc2_evdoc = self._evdoc(5, 11, "Doc2EvFile.docx", document_id="doc2")
        spans = [doc1_req, doc2_evdoc]
        claim = self._completeness_claim(
            5, "Doc1 row 5 requirement", document_id="doc1"
        )
        source = _make_source("src_doc2_ev", "Doc2EvFile.docx", None, "missing_file")

        links = linker.link(
            claims=[claim],
            citations=[],
            sources=[source],
            spans=spans,
        )
        assert len(links) == 1
        # Doc1 row 5 has no D cell in doc1 at all -> source_missing with None,
        # NOT paired with doc2's D5.
        assert links[0].status == "source_missing"
        assert links[0].source_id is None, (
            f"Cross-document pairing happened: source_id={links[0].source_id}"
        )

    def test_no_duplicate_source_missing_from_index_drift(self, linker):
        """Two adjacent rows packed at indexes 10, 11, 12, 13.

        Under the old `req_idx + 2` heuristic:
        - req3 (idx 10) + 2 = idx 12, which is req5 (wrong cell type) → None
        - req5 (idx 12) + 2 = idx 14, which does not exist → None
        Both rows would emit source_missing with source_id=None, losing
        the per-row anchor to the actual evidence-doc filename.

        Under label-based pairing, each row pairs with its own D cell.
        """
        spans = [
            self._req(3, 10, "Req3"),
            self._evdoc(3, 11, "File3.pdf"),
            self._req(5, 12, "Req5"),
            self._evdoc(5, 13, "File5.pdf"),
        ]
        claims = [
            self._completeness_claim(3, "Req3"),
            self._completeness_claim(5, "Req5"),
        ]
        sources = [
            _make_source("src_3", "File3.pdf", None, "missing_file"),
            _make_source("src_5", "File5.pdf", None, "missing_file"),
        ]
        links = linker.link(
            claims=claims,
            citations=[],
            sources=sources,
            spans=spans,
        )
        by_claim = {lk.claim_id: lk for lk in links}
        assert by_claim[f"claim_row_{self.DOC_ID}_3"].source_id == "src_3"
        assert by_claim[f"claim_row_{self.DOC_ID}_5"].source_id == "src_5"
        none_anchored = [lk for lk in links if lk.source_id is None]
        assert none_anchored == [], (
            f"Row-index drift produced source_missing with no source: {none_anchored}"
        )


class TestEvidenceLinkIdStability:
    def test_evidence_link_ids_are_stable(self, linker, parser):
        """Stability invariant: identical calls produce identical evidence_link_id values."""
        pivotal_text = (
            "The primary endpoint response rate of 87.4% (95% CI: 82.1-91.6) "
            "was achieved in (n=412) participants (Smith et al., 2023)."
        )
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, pivotal_text)
        citations = parser.parse_citations([span])
        claim = _make_claim(
            "claim_stable_test",
            DOC_ID_CER,
            PIVOTAL_SPAN_ID,
            "87.4% response rate",
            ClaimType.CLINICAL_PERFORMANCE,
        )
        smith_source = _make_source(
            "src_stable_test",
            "bibliography/source-study.pdf",
            "smith_2023",
            "local_fulltext",
        )

        links1 = linker.link(claims=[claim], citations=citations, sources=[smith_source])
        links2 = linker.link(claims=[claim], citations=citations, sources=[smith_source])
        ids1 = {lk.evidence_link_id for lk in links1}
        ids2 = {lk.evidence_link_id for lk in links2}
        assert ids1 == ids2, "Evidence link IDs differ across identical calls"
