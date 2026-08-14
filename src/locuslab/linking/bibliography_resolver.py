"""Map citations to Source records via normalized author-year keys.

Engine-domain note: author-year normalization, bibliography-directory scanning,
and Source record construction are domain-agnostic. The GSPR_MAPPING
Evidence_Document column scan is MDR/IVDR-specific and should migrate into an
MDR rule pack when pharma source-reference layouts (e.g. CSR appendix tables,
TLF cross-references) need their own resolver paths. See
docs/architecture.md "Engine Domain Discipline".
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from locuslab.extract.citation_parser import CitationMention
from locuslab.extract.patterns import normalize_author_year_key
from locuslab.ingest.ids import make_source_id
from locuslab.models import Document, DocumentKind, Source, Span, SpanLocationKind

# Pattern to extract author+year from raw PDF text (e.g. "Smith J. et al. (2023)")
_PDF_AUTHOR_YEAR = re.compile(
    r"(?P<authors>[A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+et\s+al\.?)?)"
    r"[\s.,]*"
    r"\(?(?P<year>(?:19|20)\d{2})\)?",
)

# Sections containing GSPR Evidence_Document column values.
# The xlsx_reader emits section labels like "GSPR:header:D=Evidence_Document".
_GSPR_EVIDENCE_DOC_SECTION_PATTERN = re.compile(
    r"D=Evidence_Document",
    re.IGNORECASE,
)


class BibliographyResolver:
    """Map citations to Source records via normalized author-year keys."""

    def resolve(
        self,
        documents: Sequence[Document],
        spans: Sequence[Span],
        citations: Sequence[CitationMention],
    ) -> list[Source]:
        """Build Source records from bibliography directory and GSPR references.

        Returns sources sorted by source_id.
        """
        sources: list[Source] = []
        seen_source_ids: set[str] = set()

        # Build map of document_id -> document for quick lookup
        doc_map = {d.document_id: d for d in documents}

        # --- 1. SOURCE_PDF documents: derive citation_key from page text ---
        for doc in documents:
            if doc.kind != DocumentKind.SOURCE_PDF:
                continue
            citation_key = self._derive_citation_key_from_doc(doc, spans)
            source_id = make_source_id(doc.path or "", citation_key)
            if source_id not in seen_source_ids:
                seen_source_ids.add(source_id)
                sources.append(
                    Source(
                        source_id=source_id,
                        path=doc.path,
                        citation_key=citation_key,
                        availability_status="local_fulltext",
                    )
                )

        # Build a set of known document paths (POSIX-normalized basenames) for
        # existence checks when processing GSPR filename references.
        known_paths: set[str] = set()
        for doc in documents:
            if doc.path:
                known_paths.add(doc.path)
                # Also add bare basename to handle "CER.docx" vs "bibliography/CER.docx"
                known_paths.add(doc.path.split("/")[-1])

        # --- 2. GSPR_MAPPING spans: find Evidence_Document column cells ---
        for span in spans:
            span_doc = doc_map.get(span.document_id)
            if span_doc is None or span_doc.kind != DocumentKind.GSPR_MAPPING:
                continue
            if span.location.kind != SpanLocationKind.TABLE_CELL:
                continue
            # Section label indicates this is an Evidence_Document column cell
            section = span.section or ""
            if not _GSPR_EVIDENCE_DOC_SECTION_PATTERN.search(section):
                continue
            filename = span.text.strip()
            if not filename:
                continue
            # Only emit missing_file if the referenced file is not a known dossier document
            if filename in known_paths:
                continue
            source_id = make_source_id(filename, None)
            if source_id not in seen_source_ids:
                seen_source_ids.add(source_id)
                sources.append(
                    Source(
                        source_id=source_id,
                        path=filename,
                        citation_key=None,
                        availability_status="missing_file",
                    )
                )

        sources.sort(key=lambda s: s.source_id)
        return sources

    def _derive_citation_key_from_doc(
        self, doc: Document, spans: Sequence[Span]
    ) -> str | None:
        """Scan page spans of a SOURCE_PDF document to extract an author-year key.

        Uses the first author-year pair found in the document's spans.
        Returns None if no recognizable author-year pattern is found.
        """
        # Find spans for this document
        doc_spans = [s for s in spans if s.document_id == doc.document_id]
        for span in doc_spans:
            m = _PDF_AUTHOR_YEAR.search(span.text)
            if m:
                authors = m.group("authors")
                year = m.group("year")
                key = normalize_author_year_key(authors, year)
                if key != f"unknown_{year}":
                    return key
        return None
