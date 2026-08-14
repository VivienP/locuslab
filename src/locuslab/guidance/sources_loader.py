"""Phase 6E-prep-A — Read-only source loader with parsed frontmatter cross-refs.

Reads packaged ``source_inventory.json``, resolves ``derived_md_path_optional``,
and parses frontmatter cross-refs when a ``.md`` sibling exists.

MUST NOT import pdfplumber. Operates on already-generated ``.md`` files only.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from locuslab.guidance.assets import (
    INVENTORY_RELPATH,
    packaged_filesystem_path,
    read_packaged_text,
)
from locuslab.guidance.frontmatter import Frontmatter, parse_frontmatter


@dataclass(frozen=True)
class SourceRecord:
    """A fully loaded source entry with optional parsed Markdown and cross-refs."""

    source_id: str
    title: str
    inventory_entry: dict[str, Any]
    md_path: Path | None
    frontmatter: Frontmatter | None
    body: str | None


def _load_inventory() -> dict[str, Any]:
    text = read_packaged_text(INVENTORY_RELPATH)
    if text is None:
        raise FileNotFoundError(
            "Packaged source_inventory.json is missing from locuslab.resources"
        )
    result: dict[str, Any] = json.loads(text)
    return result


def _find_entry(inventory: dict[str, Any], source_id: str) -> dict[str, Any]:
    for entry in inventory.get("sources", []) or []:
        if isinstance(entry, dict) and entry.get("source_id") == source_id:
            result: dict[str, Any] = entry
            return result
    raise KeyError(f"source_id {source_id!r} not found in source_inventory.json")


def load_source_with_xrefs(source_id: str) -> SourceRecord:
    """Load a source by ID with parsed frontmatter cross-refs.

    Reads packaged ``source_inventory.json``, resolves
    ``derived_md_path_optional``, parses frontmatter if a ``.md`` sibling
    exists. Raises ``KeyError`` if ``source_id`` is not in the inventory.
    """
    inventory = _load_inventory()
    entry = _find_entry(inventory, source_id)

    md_path: Path | None = None
    frontmatter: Frontmatter | None = None
    body: str | None = None

    raw_md_path = entry.get("derived_md_path_optional")
    if raw_md_path:
        md_text = read_packaged_text(str(raw_md_path))
        if md_text is not None:
            md_path = packaged_filesystem_path(str(raw_md_path)) or Path(str(raw_md_path))
            try:
                frontmatter, body = parse_frontmatter(md_text)
            except ValueError as exc:
                warnings.warn(
                    f"Malformed frontmatter in {raw_md_path}: {exc}. "
                    "Falling back to body=full text, frontmatter=None.",
                    UserWarning,
                    stacklevel=2,
                )
                frontmatter = None
                body = md_text

    return SourceRecord(
        source_id=str(entry.get("source_id", "")),
        title=str(entry.get("title", "")),
        inventory_entry=dict(entry),
        md_path=md_path,
        frontmatter=frontmatter,
        body=body,
    )


def load_source_md(source_id: str) -> str | None:
    """Return raw Markdown text for a source, or None if no derived MD exists."""
    inventory = _load_inventory()
    entry = _find_entry(inventory, source_id)

    raw_md_path = entry.get("derived_md_path_optional")
    if not raw_md_path:
        return None
    return read_packaged_text(str(raw_md_path))
