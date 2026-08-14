from pathlib import Path

import pytest
from openpyxl import Workbook

from locuslab.ingest.xlsx_reader import read_xlsx
from locuslab.models import ParserWarningCode, SpanLocationKind


def test_read_xlsx_extracts_one_span_per_non_empty_cell() -> None:
    result = read_xlsx(
        Path("fixtures/demo_dossier/GSPR_mapping.xlsx"),
        document_id="doc_test_gspr",
    )

    assert result.parser.startswith("openpyxl:")
    assert all(s.location.kind == SpanLocationKind.TABLE_CELL for s in result.spans)
    assert len(result.spans) >= 20


def test_read_xlsx_cell_labels_carry_sheet_and_address() -> None:
    result = read_xlsx(
        Path("fixtures/demo_dossier/GSPR_mapping.xlsx"),
        document_id="doc_test_gspr",
    )

    labels = {s.location.label for s in result.spans if s.location.label is not None}
    assert "GSPR:A1" in labels
    assert "GSPR:A2" in labels
    assert "GSPR:E5" in labels


def test_read_xlsx_skips_empty_rows_and_cells(tmp_path: Path) -> None:
    path = tmp_path / "gaps.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Data"
    ws.append(["H1", "H2", "H3"])
    ws.append(["v1", None, "v3"])
    ws.append([None, None, None])
    ws.append(["x", "y", "z"])
    wb.save(path)

    result = read_xlsx(path, document_id="doc_gaps")

    texts = {s.text for s in result.spans}
    assert "H1" in texts
    assert "v1" in texts
    assert "x" in texts
    assert "" not in texts


def test_read_xlsx_attaches_header_context_as_section() -> None:
    result = read_xlsx(
        Path("fixtures/demo_dossier/GSPR_mapping.xlsx"),
        document_id="doc_test_gspr",
    )

    by_label = {s.location.label: s for s in result.spans}

    a1 = by_label.get("GSPR:A1")
    assert a1 is not None
    assert a1.section == "GSPR:header"

    b2 = by_label.get("GSPR:B2")
    assert b2 is not None
    assert b2.section is not None
    assert "Requirement" in b2.section


def test_read_xlsx_links_every_span_to_document_id() -> None:
    result = read_xlsx(
        Path("fixtures/demo_dossier/GSPR_mapping.xlsx"),
        document_id="doc_test_gspr",
    )

    assert all(s.document_id == "doc_test_gspr" for s in result.spans)
    assert all(s.text for s in result.spans)
    assert all(s.span_id.startswith("span_") for s in result.spans)


def test_read_xlsx_span_ids_are_stable_across_calls() -> None:
    path = Path("fixtures/demo_dossier/GSPR_mapping.xlsx")

    first = read_xlsx(path, document_id="doc_test_gspr")
    second = read_xlsx(path, document_id="doc_test_gspr")

    assert tuple(s.span_id for s in first.spans) == tuple(s.span_id for s in second.spans)


def test_read_xlsx_emits_unreadable_warning_for_non_xlsx_bytes(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.xlsx"
    bogus.write_bytes(b"definitely not an xlsx")

    result = read_xlsx(bogus, document_id="doc_bogus_xlsx")

    assert result.spans == ()
    codes = {w.code for w in result.warnings}
    assert ParserWarningCode.EXTRACTION_UNREADABLE_FILE in codes


def test_read_xlsx_emits_empty_document_for_blank_workbook(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    Workbook().save(path)

    result = read_xlsx(path, document_id="doc_empty_xlsx")

    codes = {w.code for w in result.warnings}
    assert ParserWarningCode.EXTRACTION_EMPTY_DOCUMENT in codes
    assert result.spans == ()


def test_read_xlsx_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_xlsx(tmp_path / "absent.xlsx", document_id="doc_missing")
