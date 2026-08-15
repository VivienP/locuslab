"""Canonicalise generated OOXML containers for byte-stable hashing."""

from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

_CANONICAL_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)
_CANONICAL_MODIFIED_TIMESTAMP = b"2026-01-01T00:00:00Z"
_MODIFIED_TIMESTAMP_PATTERN = re.compile(
    rb"(<dcterms:modified\b[^>]*>)[^<]*(</dcterms:modified>)"
)


def _canonicalise_entry_content(filename: str, content: bytes) -> bytes:
    if filename != "docProps/core.xml":
        return content
    return _MODIFIED_TIMESTAMP_PATTERN.sub(
        rb"\g<1>" + _CANONICAL_MODIFIED_TIMESTAMP + rb"\g<2>",
        content,
    )


def canonicalise_ooxml(path: Path) -> None:
    """Rewrite a DOCX/XLSX ZIP with stable entry order and metadata."""
    temporary_path = path.with_name(f"{path.name}.canonical.tmp")
    try:
        with ZipFile(path, "r") as source:
            entries = tuple(
                (entry.filename, entry.compress_type, source.read(entry.filename))
                for entry in source.infolist()
            )

        with ZipFile(
            temporary_path,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as target:
            for filename, compress_type, content in sorted(entries):
                entry = ZipInfo(filename=filename, date_time=_CANONICAL_ZIP_DATETIME)
                entry.compress_type = compress_type
                entry.create_system = 0
                entry.external_attr = 0
                target.writestr(entry, _canonicalise_entry_content(filename, content))

        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
