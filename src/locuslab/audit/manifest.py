"""Build and persist the audit_manifest.json artifact.

Pure deterministic helpers. No wall-clock, no network. The manifest hashes
the other artifacts written by the pipeline; by design it does NOT hash
itself (single-pass write). See docs/architecture.md.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from locuslab.models import Document

MANIFEST_SCHEMA_VERSION = "audit.v1"

KNOWN_LIMITATIONS: tuple[str, ...] = (
    "numeric mismatch checker not yet implemented",
    "cross-document contradiction checker not yet implemented",
    "GSPR Status-aware severity refinement not yet implemented",
    "bibliography-to-sources resolver for in-document footnotes remains NEEDS-DESIGN",
    "no graph database server; graph persistence is graph.jsonl only",
    "no cryptographic proof layer (Merkle / DSSE / Sigstore / in-toto deferred)",
)


def hash_artifact(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_run_id(
    documents: Sequence[Document], artifact_counts: dict[str, int]
) -> str:
    """Stable run_<16hex> id from input document hashes + artifact counts.

    No wall-clock contribution. Two runs on the same dossier with identical
    artifacts produce identical run_id.
    """
    digest = hashlib.sha256()
    for doc in sorted(documents, key=lambda d: d.document_id):
        digest.update(b"|")
        digest.update(doc.document_id.encode("utf-8"))
        digest.update(b":")
        digest.update(doc.sha256.encode("utf-8"))
    counts_blob = json.dumps(artifact_counts, sort_keys=True).encode("utf-8")
    digest.update(b"|counts=")
    digest.update(counts_blob)
    return f"run_{digest.hexdigest()[:16]}"


def _document_summary(doc: Document) -> dict[str, object]:
    return {
        "document_id": doc.document_id,
        "path": doc.path,
        "kind": doc.kind.value,
        "sha256": doc.sha256,
        "parser": doc.parser,
        "parse_warning_codes": sorted({w.code.value for w in doc.parse_warnings}),
    }


def build_manifest(
    *,
    run_id: str,
    documents: Sequence[Document],
    artifact_counts: dict[str, int],
    artifact_hashes: dict[str, str],
    extraction_methods: Sequence[str],
    checker_ids: Sequence[str],
    linking_methods: Sequence[str],
    unresolved_affected_ids: Sequence[str],
    known_limitations: Sequence[str] = KNOWN_LIMITATIONS,
) -> dict[str, object]:
    """Build the manifest dict ready for JSON serialization.

    Top-level keys are returned in insertion order; the writer sorts them
    for deterministic byte output.
    """
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "input_documents": [
            _document_summary(doc)
            for doc in sorted(documents, key=lambda d: d.document_id)
        ],
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "artifact_counts": dict(sorted(artifact_counts.items())),
        "extraction_methods": sorted(set(extraction_methods)),
        "checker_ids": sorted(set(checker_ids)),
        "linking_methods": sorted(set(linking_methods)),
        "unresolved_affected_ids": list(unresolved_affected_ids),
        "known_limitations": list(known_limitations),
    }


def write_manifest(manifest: dict[str, object], path: Path) -> None:
    """Write the manifest as pretty-printed JSON with sorted top-level keys.

    `sort_keys=True` ensures byte-equal output across runs. Trailing newline
    keeps shell tooling happy.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
