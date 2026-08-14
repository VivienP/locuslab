"""Ingestion boundaries for local dossier files."""

from locuslab.ingest.docx_reader import read_docx
from locuslab.ingest.ids import (
    file_sha256,
    make_document_id,
    make_span_id,
    relative_posix_path,
    stable_id,
)
from locuslab.ingest.loader import DossierLoadError, DossierLoadResult, load_dossier
from locuslab.ingest.pdf_reader import read_pdf
from locuslab.ingest.reader_base import ReaderResult
from locuslab.ingest.xlsx_reader import read_xlsx

__all__ = [
    "DossierLoadError",
    "DossierLoadResult",
    "ReaderResult",
    "file_sha256",
    "load_dossier",
    "make_document_id",
    "make_span_id",
    "read_docx",
    "read_pdf",
    "read_xlsx",
    "relative_posix_path",
    "stable_id",
]
