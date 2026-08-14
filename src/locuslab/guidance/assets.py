"""Locate SSCP guidance JSON and derived Markdown from package data.

docs/ in the git checkout is the source of truth. Identical files are
shipped under locuslab.resources so `locus verify` works after
`pip install` without depending on Path.cwd() or a repo-relative
parents[2] layout.
"""

from __future__ import annotations

import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

RULE_PACK_RELPATH = Path("docs/rules/guidance/sscp/rule_pack.json")
INVENTORY_RELPATH = Path("docs/guidance/source_inventory.json")

GuidancePayload = tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, tuple[str, str]],
]


def _resources_root() -> Traversable:
    return files("locuslab.resources")


def _joinpath(root: Traversable, rel: Path) -> Traversable:
    return root.joinpath(*rel.parts)


def load_guidance_payload() -> GuidancePayload | None:
    """Load rule pack, inventory, and derived MD text from package data.

    Returns None if the packaged files are missing (broken install).
    """
    root = _resources_root()
    rule_trav = _joinpath(root, RULE_PACK_RELPATH)
    inv_trav = _joinpath(root, INVENTORY_RELPATH)
    if not rule_trav.is_file() or not inv_trav.is_file():
        return None

    rule_pack: dict[str, Any] = json.loads(rule_trav.read_text(encoding="utf-8"))
    inventory: dict[str, Any] = json.loads(inv_trav.read_text(encoding="utf-8"))
    md_text_by_source_id = _load_md_for_sources(rule_pack, inventory, root)
    return rule_pack, inventory, md_text_by_source_id


def _load_md_for_sources(
    rule_pack: dict[str, Any],
    inventory: dict[str, Any],
    root: Traversable,
) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    source_ids: set[str] = set()
    for rule in rule_pack.get("rules", []) or []:
        if isinstance(rule, dict):
            sid = rule.get("source_id")
            if isinstance(sid, str) and sid:
                source_ids.add(sid)
    inventory_by_id = {
        src["source_id"]: src
        for src in inventory.get("sources", []) or []
        if isinstance(src, dict) and isinstance(src.get("source_id"), str)
    }
    for source_id in source_ids:
        entry = inventory_by_id.get(source_id)
        if entry is None:
            continue
        md_path_raw = entry.get("derived_md_path_optional")
        if not isinstance(md_path_raw, str) or not md_path_raw:
            continue
        trav = _joinpath(root, Path(md_path_raw))
        if not trav.is_file():
            continue
        result[source_id] = (md_path_raw, trav.read_text(encoding="utf-8"))
    return result


def packaged_filesystem_path(rel: str | Path) -> Path | None:
    """Return a filesystem Path for a packaged file when it exists on disk."""
    trav = _joinpath(_resources_root(), Path(rel))
    if not trav.is_file():
        return None
    candidate = Path(str(trav))
    if candidate.is_file():
        return candidate
    return None


def read_packaged_text(rel: str | Path) -> str | None:
    """Return UTF-8 text of a packaged file, or None if it is absent."""
    trav = _joinpath(_resources_root(), Path(rel))
    if not trav.is_file():
        return None
    return trav.read_text(encoding="utf-8")
