"""Local dossier discovery and content-aware ingestion."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from locuslab.ingest.docx_reader import read_docx
from locuslab.ingest.ids import file_sha256, make_document_id, relative_posix_path
from locuslab.ingest.pdf_reader import read_pdf
from locuslab.ingest.reader_base import ReaderResult
from locuslab.ingest.xlsx_reader import read_xlsx
from locuslab.models import Document, DocumentKind, ParserWarning, ParserWarningCode, Span

# The marker is the MDR Article 32 statutory title. Matching is limited to a
# title-like span so revision-history blocks may precede it without turning a
# narrative reference elsewhere in a document into an SSCP classification.
_SSCP_CONTENT_MARKER = "summary of safety and clinical performance"

SUPPORTED_CONTENT_EXTENSIONS = frozenset({".docx", ".pdf", ".xlsx"})

_Reader = Callable[..., ReaderResult]

_READERS: dict[str, _Reader] = {
    ".docx": read_docx,
    ".pdf": read_pdf,
    ".xlsx": read_xlsx,
}


class DossierLoadError(ValueError):
    """Raised when a dossier directory cannot be loaded."""


@dataclass(frozen=True)
class DossierLoadResult:
    """Documents, spans, and aggregated warnings extracted from a local dossier."""

    dossier_dir: Path
    documents: tuple[Document, ...]
    spans: tuple[Span, ...]
    warnings: tuple[ParserWarning, ...]


def load_dossier(dossier_dir: Path) -> DossierLoadResult:
    """Discover local dossier files and return document + span records."""
    root = dossier_dir.resolve()
    if not root.exists():
        raise DossierLoadError(f"Dossier directory not found: {dossier_dir}")
    if not root.is_dir():
        raise DossierLoadError(f"Dossier path is not a directory: {dossier_dir}")

    documents: list[Document] = []
    all_spans: list[Span] = []
    aggregated_warnings: list[ParserWarning] = []

    for path in _iter_dossier_files(root):
        document, spans = _ingest_file(path=path, root=root)
        # Content refinement only applies when the filename heuristic returned
        # OTHER, so filename-classified documents keep their kind.
        document = _refine_kind_from_content(document, spans)
        documents.append(document)
        all_spans.extend(spans)
        aggregated_warnings.extend(document.parse_warnings)
        for span in spans:
            aggregated_warnings.extend(span.extraction_warnings)

    return DossierLoadResult(
        dossier_dir=root,
        documents=tuple(documents),
        spans=tuple(all_spans),
        warnings=tuple(aggregated_warnings),
    )


def _refine_kind_from_content(
    document: Document, spans: Sequence[Span]
) -> Document:
    """Reclassify OTHER -> SSCP when a span is the MDR Article 32 title.

    Only fires for documents currently classified as OTHER. Filename-
    classified documents (CER, PMCF, SSCP-by-name, ...) are returned
    unchanged. A title-shaped match avoids classifying narrative references.
    """
    if document.kind != DocumentKind.OTHER:
        return document
    doc_spans = [span for span in spans if span.document_id == document.document_id]
    for span in doc_spans:
        if _is_sscp_title_span(span.text):
            return dataclasses.replace(document, kind=DocumentKind.SSCP)
    return document


def _is_sscp_title_span(text: str) -> bool:
    normalized = " ".join(text.casefold().split()).strip()
    if normalized == _SSCP_CONTENT_MARKER:
        return True
    return any(
        normalized.startswith(f"{_SSCP_CONTENT_MARKER}{separator}")
        for separator in (":", " -", " –", " —")
    )


def infer_document_kind(path: Path) -> DocumentKind:
    """Infer an MDR/IVDR document kind from a dossier-relative path."""
    suffix = path.suffix.lower()
    normalized_stem = path.stem.lower().replace("-", "_").replace(" ", "_")
    tokens = {token for token in normalized_stem.split("_") if token}
    relative_text = path.as_posix().lower()

    if "gspr" in tokens or "gspr" in normalized_stem:
        return DocumentKind.GSPR_MAPPING
    if "evidence" in tokens or "evidence_table" in normalized_stem:
        return DocumentKind.EVIDENCE_TABLE
    if "pmcf" in tokens:
        return DocumentKind.PMCF
    if "psur" in tokens:
        return DocumentKind.PSUR
    if "pms" in tokens:
        return DocumentKind.PMS
    if "sscp" in tokens:
        return DocumentKind.SSCP
    if "cer" in tokens or "clinical_evaluation" in normalized_stem:
        return DocumentKind.CER
    if suffix == ".pdf" and ("bibliography/" in relative_text or "sources/" in relative_text):
        return DocumentKind.SOURCE_PDF
    return DocumentKind.OTHER


def _ingest_file(path: Path, root: Path) -> tuple[Document, tuple[Span, ...]]:
    relative_path = relative_posix_path(path, root)
    kind = infer_document_kind(Path(relative_path))
    suffix = path.suffix.lower()
    metadata = _metadata_for(path=path, relative_path=relative_path, suffix=suffix)

    file_hash = ""
    read_warning: ParserWarning | None = None
    try:
        file_hash = file_sha256(path)
    except OSError as exc:
        read_warning = ParserWarning(
            code=ParserWarningCode.FILE_READ_FAILED,
            message=f"File could not be read during ingestion: {exc}",
            path=relative_path,
        )

    document_id = make_document_id(kind=kind, relative_path=relative_path, file_hash=file_hash)

    if read_warning is not None:
        document = Document(
            document_id=document_id,
            kind=kind,
            path=relative_path,
            sha256=file_hash,
            parser="unreadable-file",
            metadata=metadata,
            parse_warnings=(read_warning,),
        )
        return document, ()

    reader = _READERS.get(suffix)
    if reader is None:
        warnings_list: list[ParserWarning] = [
            ParserWarning(
                code=ParserWarningCode.UNSUPPORTED_FILE_TYPE,
                message="File extension is not supported; expected DOCX, PDF, or XLSX.",
                path=relative_path,
            )
        ]
        if metadata["size_bytes"] == "0":
            warnings_list.append(
                ParserWarning(
                    code=ParserWarningCode.EMPTY_FILE,
                    message="Input file is empty.",
                    path=relative_path,
                )
            )
        warnings = tuple(warnings_list)
        document = Document(
            document_id=document_id,
            kind=kind,
            path=relative_path,
            sha256=file_hash,
            parser="unsupported-file",
            metadata=metadata,
            parse_warnings=warnings,
        )
        return document, ()

    if metadata["size_bytes"] == "0":
        document = Document(
            document_id=document_id,
            kind=kind,
            path=relative_path,
            sha256=file_hash,
            parser="unreadable-file",
            metadata=metadata,
            parse_warnings=(
                ParserWarning(
                    code=ParserWarningCode.EMPTY_FILE,
                    message="Input file is empty.",
                    path=relative_path,
                ),
            ),
        )
        return document, ()

    reader_result = reader(path, document_id=document_id)
    warnings_tuple = tuple(
        ParserWarning(code=w.code, message=w.message, path=relative_path, location=w.location)
        for w in reader_result.warnings
    )
    is_unreadable = any(
        w.code == ParserWarningCode.EXTRACTION_UNREADABLE_FILE for w in warnings_tuple
    )
    parser_name = "unreadable-file" if is_unreadable else reader_result.parser
    document = Document(
        document_id=document_id,
        kind=kind,
        path=relative_path,
        sha256=file_hash,
        parser=parser_name,
        metadata=metadata,
        parse_warnings=warnings_tuple,
    )
    return document, reader_result.spans


def _iter_dossier_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in root.rglob("*") if path.is_file()))


def _metadata_for(path: Path, relative_path: str, suffix: str) -> dict[str, str]:
    try:
        size_bytes = str(path.stat().st_size)
    except OSError:
        size_bytes = "0"
    supported = suffix in SUPPORTED_CONTENT_EXTENSIONS
    return {
        "extension": suffix,
        "ingestion_mode": "content_v1" if supported else "metadata_only",
        "relative_path": relative_path,
        "size_bytes": size_bytes,
    }
