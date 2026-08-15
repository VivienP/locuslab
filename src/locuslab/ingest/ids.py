"""Stable identifier helpers for ingestion objects."""

from __future__ import annotations

import hashlib
from pathlib import Path

from locuslab.models import DocumentKind, SpanLocation

ID_DIGEST_LENGTH = 16


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    """Build a deterministic short ID from ordered string parts."""
    digest = hashlib.sha256()
    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)
    return f"{prefix}_{digest.hexdigest()[:ID_DIGEST_LENGTH]}"


def make_document_id(kind: DocumentKind, relative_path: str, file_hash: str) -> str:
    """Build the stable document ID for a dossier file."""
    return stable_id("doc", kind.value, relative_path, file_hash)


def make_span_id(document_id: str, location: SpanLocation, text: str) -> str:
    """Build the stable span ID for extracted text at a document location."""
    location_parts = [
        location.kind.value,
        "" if location.index is None else str(location.index),
        "" if location.label is None else location.label,
    ]
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return stable_id("span", document_id, *location_parts, text_hash)


def relative_posix_path(path: Path, root: Path) -> str:
    """Return a stable POSIX-style relative path for ID inputs and metadata."""
    return path.relative_to(root).as_posix()


def make_claim_id(
    document_id: str,
    span_id: str,
    normalized_text: str,
    extractor_id: str,
    occurrence_index: int,
) -> str:
    """Build stable claim ID. Does NOT use character offsets."""
    return stable_id(
        "claim", document_id, span_id, normalized_text, extractor_id, str(occurrence_index)
    )


def make_citation_id(
    document_id: str,
    span_id: str,
    normalized_marker: str,
    parser_id: str,
    occurrence_index: int,
) -> str:
    """Build stable citation mention ID."""
    return stable_id(
        "cite", document_id, span_id, normalized_marker, parser_id, str(occurrence_index)
    )


def make_source_id(
    relative_path: str,
    citation_key: str | None,
) -> str:
    """Build stable source ID from path and normalized key."""
    return stable_id("src", relative_path, citation_key or "")


def make_evidence_link_id(
    claim_id: str,
    source_id: str | None,
    status: str,
    candidate_source_ids: tuple[str, ...] = (),
) -> str:
    """Build stable evidence link ID."""
    return stable_id(
        "elink",
        claim_id,
        source_id or "",
        status,
        *sorted(candidate_source_ids),
    )
