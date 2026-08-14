from pathlib import Path

import pytest

from locuslab.ingest.pdf_reader import read_pdf
from locuslab.models import ParserWarningCode, SpanLocationKind


def test_read_pdf_extracts_one_span_per_text_page() -> None:
    result = read_pdf(
        Path("fixtures/demo_dossier/bibliography/source-study.pdf"),
        document_id="doc_test_pdf",
    )

    assert result.parser.startswith("pypdf:")
    page_spans = [s for s in result.spans if s.location.kind == SpanLocationKind.PAGE]
    assert len(page_spans) >= 2
    indexes = sorted(s.location.index for s in page_spans if s.location.index is not None)
    assert indexes == list(range(1, len(page_spans) + 1))


def test_read_pdf_links_spans_to_document_and_has_text() -> None:
    result = read_pdf(
        Path("fixtures/demo_dossier/bibliography/source-study.pdf"),
        document_id="doc_test_pdf",
    )

    for span in result.spans:
        assert span.document_id == "doc_test_pdf"
        assert span.text.strip()
        assert span.section is None
        assert span.span_id.startswith("span_")


def test_read_pdf_span_ids_are_stable_across_calls() -> None:
    path = Path("fixtures/demo_dossier/bibliography/source-study.pdf")

    first = read_pdf(path, document_id="doc_test_pdf")
    second = read_pdf(path, document_id="doc_test_pdf")

    assert tuple(s.span_id for s in first.spans) == tuple(s.span_id for s in second.spans)


def test_read_pdf_emits_no_text_layer_warning_for_image_only_page(tmp_path: Path) -> None:
    image_only_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000056 00000 n \n"
        b"0000000103 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n168\n%%EOF\n"
    )
    path = tmp_path / "scan.pdf"
    path.write_bytes(image_only_pdf)

    result = read_pdf(path, document_id="doc_scan")

    codes = {w.code for w in result.warnings}
    assert ParserWarningCode.EXTRACTION_NO_TEXT_LAYER in codes
    assert all(s.text.strip() for s in result.spans)


def test_read_pdf_emits_unreadable_warning_for_non_pdf_bytes(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.pdf"
    bogus.write_bytes(b"this is plain text, not a pdf")

    result = read_pdf(bogus, document_id="doc_bogus_pdf")

    assert result.spans == ()
    codes = {w.code for w in result.warnings}
    assert ParserWarningCode.EXTRACTION_UNREADABLE_FILE in codes


def test_read_pdf_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_pdf(tmp_path / "absent.pdf", document_id="doc_missing")
