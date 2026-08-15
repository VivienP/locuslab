"""Unit tests for BibliographyResolver - written before implementation (TDD)."""

from __future__ import annotations

import pytest

from locuslab.models import Document, DocumentKind, Span, SpanLocation, SpanLocationKind


def _make_span(
    span_id: str,
    document_id: str,
    text: str,
    kind: SpanLocationKind = SpanLocationKind.PAGE,
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


def _make_doc(
    document_id: str,
    path: str,
    kind: DocumentKind = DocumentKind.SOURCE_PDF,
    sha256: str = "abc",
) -> Document:
    return Document(
        document_id=document_id,
        kind=kind,
        path=path,
        sha256=sha256,
        parser="pypdf",
    )


DOC_ID_SOURCE = "doc_faf32261b7e7f62a"
DOC_ID_GSPR = "doc_84039664cf6a7d66"

SOURCE_P1_TEXT = (
    "Smith J. et al. (2023) Pivotal study of DemoDevice X100. "
    "Response rate was 87.4 percent at 12 months (n=412)."
)


@pytest.fixture()
def resolver():  # type: ignore[return]
    from locuslab.linking.bibliography_resolver import BibliographyResolver

    return BibliographyResolver()


@pytest.fixture()
def source_doc() -> Document:
    return _make_doc(DOC_ID_SOURCE, "bibliography/source-study.pdf")


@pytest.fixture()
def gspr_doc() -> Document:
    return _make_doc(
        DOC_ID_GSPR,
        "GSPR_mapping.xlsx",
        kind=DocumentKind.GSPR_MAPPING,
        sha256="def",
    )


@pytest.fixture()
def source_page1_span(source_doc: Document) -> Span:
    return _make_span("span_34348cc49f123629", DOC_ID_SOURCE, SOURCE_P1_TEXT)


@pytest.fixture()
def pms_gspr_span(gspr_doc: Document) -> Span:
    # GSPR-03 evidence document cell
    return _make_span(
        "span_ecbca6c827a929d4",
        DOC_ID_GSPR,
        "PMS.docx",
        kind=SpanLocationKind.TABLE_CELL,
        section="GSPR:D=Evidence_Document",
    )


@pytest.fixture()
def labeling_gspr_span(gspr_doc: Document) -> Span:
    # GSPR-04 evidence document cell
    return _make_span(
        "span_48f8fa48bdf57f24",
        DOC_ID_GSPR,
        "Labeling.pdf",
        kind=SpanLocationKind.TABLE_CELL,
        section="GSPR:D=Evidence_Document",
    )


class TestResolvesSourceStudy:
    def test_resolves_source_study_pdf(
        self, resolver, source_doc, source_page1_span
    ):
        """GOLD-BIB-001: produces Source with citation_key=smith_2023 and local_fulltext."""
        from locuslab.extract.citation_parser import CitationParser

        parser = CitationParser()
        citations = parser.parse_citations([source_page1_span])

        sources = resolver.resolve(
            documents=[source_doc],
            spans=[source_page1_span],
            citations=citations,
        )
        assert sources, "No sources produced"
        smith_sources = [s for s in sources if s.citation_key == "smith_2023"]
        assert smith_sources, (
            f"No smith_2023 source; sources={[(s.path, s.citation_key) for s in sources]}"
        )
        s = smith_sources[0]
        assert s.path == "bibliography/source-study.pdf"
        assert s.availability_status == "local_fulltext"


class TestGsprMissingFiles:
    def test_gspr_missing_file_pms_docx(
        self, resolver, gspr_doc, source_doc, pms_gspr_span, source_page1_span
    ):
        """GOLD-BIB-EXT-001: PMS.docx reference produces missing_file Source."""
        from locuslab.extract.citation_parser import CitationParser

        parser = CitationParser()
        all_spans = [source_page1_span, pms_gspr_span]
        citations = parser.parse_citations(all_spans)

        sources = resolver.resolve(
            documents=[source_doc, gspr_doc],
            spans=all_spans,
            citations=citations,
        )
        pms_sources = [s for s in sources if s.path == "PMS.docx"]
        assert pms_sources, f"No PMS.docx source; paths={[s.path for s in sources]}"
        assert pms_sources[0].availability_status == "missing_file"
        assert pms_sources[0].origin_span_ids == (pms_gspr_span.span_id,)

    def test_gspr_missing_file_labeling_pdf(
        self, resolver, gspr_doc, source_doc, labeling_gspr_span, source_page1_span
    ):
        """GOLD-BIB-EXT-002: Labeling.pdf reference produces missing_file Source."""
        from locuslab.extract.citation_parser import CitationParser

        parser = CitationParser()
        all_spans = [source_page1_span, labeling_gspr_span]
        citations = parser.parse_citations(all_spans)

        sources = resolver.resolve(
            documents=[source_doc, gspr_doc],
            spans=all_spans,
            citations=citations,
        )
        labeling_sources = [s for s in sources if s.path == "Labeling.pdf"]
        assert labeling_sources, f"No Labeling.pdf source; paths={[s.path for s in sources]}"
        assert labeling_sources[0].availability_status == "missing_file"
        assert labeling_sources[0].origin_span_ids == (labeling_gspr_span.span_id,)

    def test_duplicate_gspr_reference_retains_all_origin_spans(
        self, resolver, gspr_doc
    ):
        first = _make_span(
            "span_first_origin",
            gspr_doc.document_id,
            "PMS.docx",
            kind=SpanLocationKind.TABLE_CELL,
            section="GSPR:D=Evidence_Document",
        )
        second = _make_span(
            "span_second_origin",
            gspr_doc.document_id,
            "PMS.docx",
            kind=SpanLocationKind.TABLE_CELL,
            section="GSPR:D=Evidence_Document",
        )

        sources = resolver.resolve([gspr_doc], [second, first], [])

        assert len(sources) == 1
        assert sources[0].origin_span_ids == (
            "span_first_origin",
            "span_second_origin",
        )


class TestSourceIdStability:
    def test_source_ids_are_stable(self, resolver, source_doc, source_page1_span):
        """Stability invariant: two identical calls produce identical source IDs."""
        from locuslab.extract.citation_parser import CitationParser

        parser = CitationParser()
        citations = parser.parse_citations([source_page1_span])

        sources1 = resolver.resolve(
            documents=[source_doc],
            spans=[source_page1_span],
            citations=citations,
        )
        sources2 = resolver.resolve(
            documents=[source_doc],
            spans=[source_page1_span],
            citations=citations,
        )
        ids1 = {s.source_id for s in sources1}
        ids2 = {s.source_id for s in sources2}
        assert ids1 == ids2, "Source IDs differ across identical calls"
