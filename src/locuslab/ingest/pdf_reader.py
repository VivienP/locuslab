"""PDF content reader producing one span per page with extractable text."""

from __future__ import annotations

from pathlib import Path

import pypdf

from locuslab.ingest.ids import make_span_id
from locuslab.ingest.reader_base import ReaderResult
from locuslab.models import ParserWarning, ParserWarningCode, Span, SpanLocation, SpanLocationKind

PARSER_NAME = f"pypdf:{pypdf.__version__}"


def read_pdf(path: Path, *, document_id: str) -> ReaderResult:
    """Extract one text span per page with content, plus warnings for image-only pages."""
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    relative = path.name
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:
        return ReaderResult(
            spans=(),
            warnings=(
                ParserWarning(
                    code=ParserWarningCode.EXTRACTION_UNREADABLE_FILE,
                    message=f"pypdf could not open file: {exc.__class__.__name__}",
                    path=relative,
                ),
            ),
            parser=PARSER_NAME,
        )

    if reader.is_encrypted:
        return ReaderResult(
            spans=(),
            warnings=(
                ParserWarning(
                    code=ParserWarningCode.EXTRACTION_UNREADABLE_FILE,
                    message="PDF is encrypted and cannot be parsed without credentials.",
                    path=relative,
                ),
            ),
            parser=PARSER_NAME,
        )

    spans: list[Span] = []
    warnings: list[ParserWarning] = []

    for page_index, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:
            warnings.append(
                ParserWarning(
                    code=ParserWarningCode.EXTRACTION_PARTIAL_CONTENT,
                    message=(
                        f"pypdf failed to extract page {page_index}: {exc.__class__.__name__}"
                    ),
                    path=relative,
                    location=f"page={page_index}",
                )
            )
            continue

        text = raw_text.strip()
        if not text:
            warnings.append(
                ParserWarning(
                    code=ParserWarningCode.EXTRACTION_NO_TEXT_LAYER,
                    message="PDF page has no extractable text layer (likely scanned/image-only).",
                    path=relative,
                    location=f"page={page_index}",
                )
            )
            continue

        location = SpanLocation(kind=SpanLocationKind.PAGE, index=page_index, label=None)
        spans.append(
            Span(
                span_id=make_span_id(document_id=document_id, location=location, text=text),
                document_id=document_id,
                location=location,
                text=text,
                section=None,
            )
        )

    has_no_text_layer = any(
        w.code == ParserWarningCode.EXTRACTION_NO_TEXT_LAYER for w in warnings
    )
    if not spans and not has_no_text_layer:
        warnings.append(
            ParserWarning(
                code=ParserWarningCode.EXTRACTION_EMPTY_DOCUMENT,
                message="PDF opened cleanly but produced no content spans.",
                path=relative,
            )
        )

    return ReaderResult(spans=tuple(spans), warnings=tuple(warnings), parser=PARSER_NAME)
