from pathlib import Path

import pytest

from locuslab.ingest import DossierLoadError, load_dossier
from locuslab.models import DocumentKind, ParserWarningCode


def test_load_dossier_discovers_fixture_documents() -> None:
    dossier = Path("fixtures/demo_dossier")

    result = load_dossier(dossier)

    documents_by_path = {document.path: document for document in result.documents}
    assert documents_by_path["CER.docx"].kind == DocumentKind.CER
    assert documents_by_path["GSPR_mapping.xlsx"].kind == DocumentKind.GSPR_MAPPING
    assert documents_by_path["bibliography/source-study.pdf"].kind == DocumentKind.SOURCE_PDF
    assert all(document.sha256 for document in result.documents)


def test_document_ids_are_stable_across_repeated_loads() -> None:
    dossier = Path("fixtures/demo_dossier")

    first = load_dossier(dossier)
    second = load_dossier(dossier)

    first_ids = tuple(document.document_id for document in first.documents)
    second_ids = tuple(document.document_id for document in second.documents)
    assert first_ids == second_ids


def test_load_dossier_produces_content_spans_for_supported_formats() -> None:
    dossier = Path("fixtures/demo_dossier")

    result = load_dossier(dossier)

    document_ids_by_path = {d.path: d.document_id for d in result.documents}
    spans_by_document = {d.document_id: [] for d in result.documents}
    for span in result.spans:
        spans_by_document[span.document_id].append(span)

    for path in ("CER.docx", "GSPR_mapping.xlsx", "bibliography/source-study.pdf"):
        doc_id = document_ids_by_path[path]
        assert spans_by_document[doc_id], f"expected spans for {path}, got none"

    known_ids = {d.document_id for d in result.documents}
    assert all(span.document_id in known_ids for span in result.spans)
    assert all(span.text.strip() for span in result.spans)
    assert all(span.span_id.startswith("span_") for span in result.spans)


def test_span_ids_are_stable_across_repeated_loads() -> None:
    dossier = Path("fixtures/demo_dossier")

    first = load_dossier(dossier)
    second = load_dossier(dossier)

    assert tuple(s.span_id for s in first.spans) == tuple(s.span_id for s in second.spans)


def test_supported_format_documents_no_longer_emit_parser_not_implemented() -> None:
    dossier = Path("fixtures/demo_dossier")

    result = load_dossier(dossier)

    warnings_by_path = {
        document.path: {warning.code for warning in document.parse_warnings}
        for document in result.documents
    }
    for supported in ("CER.docx", "GSPR_mapping.xlsx", "bibliography/source-study.pdf"):
        assert ParserWarningCode.PARSER_NOT_IMPLEMENTED not in warnings_by_path[supported]

    assert ParserWarningCode.UNSUPPORTED_FILE_TYPE in warnings_by_path["README.md"]


def test_load_dossier_aggregates_span_warnings(tmp_path: Path) -> None:
    dossier = tmp_path / "small"
    dossier.mkdir()
    bad_docx = dossier / "broken.docx"
    bad_docx.write_bytes(b"not a docx")

    result = load_dossier(dossier)

    aggregated_codes = {w.code for w in result.warnings}
    assert ParserWarningCode.EXTRACTION_UNREADABLE_FILE in aggregated_codes
    broken_doc = next(d for d in result.documents if d.path == "broken.docx")
    assert broken_doc.parser == "unreadable-file"


def test_load_dossier_emits_empty_file_warning_for_zero_byte_input(tmp_path: Path) -> None:
    dossier = tmp_path / "zero"
    dossier.mkdir()
    (dossier / "empty.docx").write_bytes(b"")
    (dossier / "empty.txt").write_bytes(b"")

    result = load_dossier(dossier)

    warnings_by_path = {
        d.path: {w.code for w in d.parse_warnings} for d in result.documents
    }
    assert ParserWarningCode.EMPTY_FILE in warnings_by_path["empty.docx"]
    assert ParserWarningCode.EMPTY_FILE in warnings_by_path["empty.txt"]


def test_load_dossier_emits_file_read_failed_when_hashing_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier = tmp_path / "unreadable"
    dossier.mkdir()
    target = dossier / "ghost.docx"
    target.write_bytes(b"placeholder")

    from locuslab.ingest import loader as loader_module

    def boom(_path: Path) -> str:
        raise OSError("simulated read failure")

    monkeypatch.setattr(loader_module, "file_sha256", boom)

    result = load_dossier(dossier)

    warnings = {w.code for w in result.documents[0].parse_warnings}
    assert ParserWarningCode.FILE_READ_FAILED in warnings
    assert result.documents[0].parser == "unreadable-file"


def test_load_dossier_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(DossierLoadError):
        load_dossier(tmp_path / "missing")


def test_load_dossier_rejects_path_pointing_to_file(tmp_path: Path) -> None:
    path = tmp_path / "not_a_directory.docx"
    path.write_bytes(b"placeholder")

    with pytest.raises(DossierLoadError):
        load_dossier(path)
