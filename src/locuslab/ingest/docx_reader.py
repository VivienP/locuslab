"""DOCX content reader producing structured spans."""

from __future__ import annotations

from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from locuslab.ingest.ids import make_span_id
from locuslab.ingest.reader_base import ReaderResult
from locuslab.models import ParserWarning, ParserWarningCode, Span, SpanLocation, SpanLocationKind

PARSER_NAME = f"python-docx:{docx.__version__}"

_HEADING_STYLE_NAMES = frozenset(f"Heading {level}" for level in range(1, 7))


def read_docx(path: Path, *, document_id: str) -> ReaderResult:
    """Extract paragraph and table-cell spans from a DOCX file."""
    if not path.exists():
        raise FileNotFoundError(f"DOCX file not found: {path}")

    relative = path.name
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        return ReaderResult(
            spans=(),
            warnings=(
                ParserWarning(
                    code=ParserWarningCode.EXTRACTION_UNREADABLE_FILE,
                    message=f"python-docx could not open file: {exc.__class__.__name__}",
                    path=relative,
                ),
            ),
            parser=PARSER_NAME,
        )

    spans, warnings = _extract_body(document=document, document_id=document_id, relative=relative)

    if not spans:
        warnings.append(
            ParserWarning(
                code=ParserWarningCode.EXTRACTION_EMPTY_DOCUMENT,
                message="DOCX file opened cleanly but produced no content spans.",
                path=relative,
            )
        )

    return ReaderResult(spans=tuple(spans), warnings=tuple(warnings), parser=PARSER_NAME)


def _extract_body(
    *,
    document: DocxDocument,
    document_id: str,
    relative: str,
) -> tuple[list[Span], list[ParserWarning]]:
    spans: list[Span] = []
    warnings: list[ParserWarning] = []
    current_section: str | None = None
    paragraph_index = 0
    table_index = 0
    cell_running_index = 0

    body = document.element.body
    p_tag = qn("w:p")
    tbl_tag = qn("w:tbl")

    for child in body.iterchildren():
        if child.tag == p_tag:
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            style_name = paragraph.style.name if paragraph.style is not None else ""
            if style_name in _HEADING_STYLE_NAMES:
                if text:
                    current_section = text
                    spans.append(
                        _build_paragraph_span(
                            document_id=document_id,
                            paragraph_index=paragraph_index,
                            text=text,
                            section=text,
                        )
                    )
                paragraph_index += 1
                continue
            if not text:
                paragraph_index += 1
                continue
            spans.append(
                _build_paragraph_span(
                    document_id=document_id,
                    paragraph_index=paragraph_index,
                    text=text,
                    section=current_section,
                )
            )
            paragraph_index += 1
        elif child.tag == tbl_tag:
            table = Table(child, document)
            for row_index, row in enumerate(table.rows):
                for col_index, cell in enumerate(row.cells):
                    cell_text = _cell_text(cell)
                    if not cell_text:
                        continue
                    spans.append(
                        _build_cell_span(
                            document_id=document_id,
                            cell_index=cell_running_index,
                            table_index=table_index,
                            row_index=row_index,
                            col_index=col_index,
                            text=cell_text,
                            section=current_section,
                        )
                    )
                    cell_running_index += 1
            table_index += 1

    return spans, warnings


def _cell_text(cell: _Cell) -> str:
    pieces: list[str] = []
    for paragraph in cell.paragraphs:
        chunk = paragraph.text.strip()
        if chunk:
            pieces.append(chunk)
    return "\n".join(pieces)


def _build_paragraph_span(
    *, document_id: str, paragraph_index: int, text: str, section: str | None
) -> Span:
    location = SpanLocation(kind=SpanLocationKind.PARAGRAPH, index=paragraph_index, label=None)
    return Span(
        span_id=make_span_id(document_id=document_id, location=location, text=text),
        document_id=document_id,
        location=location,
        text=text,
        section=section,
    )


def _build_cell_span(
    *,
    document_id: str,
    cell_index: int,
    table_index: int,
    row_index: int,
    col_index: int,
    text: str,
    section: str | None,
) -> Span:
    label = f"t{table_index}:r{row_index}:c{col_index}"
    location = SpanLocation(kind=SpanLocationKind.TABLE_CELL, index=cell_index, label=label)
    return Span(
        span_id=make_span_id(document_id=document_id, location=location, text=text),
        document_id=document_id,
        location=location,
        text=text,
        section=section,
    )
