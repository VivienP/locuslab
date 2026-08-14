"""Phase 6E-prep-A — Reindex derived MD sha256 hashes in source_inventory.json.

Usage:
    python scripts/reindex_guidance_sources.py --check
        CI-safe: exit 0 if all derived_md_sha256_optional values match the
        files on disk; exit 1 if any mismatch is found. No writes.

    python scripts/reindex_guidance_sources.py --write
        Re-pin derived_md_sha256_optional for every entry that has a
        derived_md_path_optional pointing to an existing file.
        Updates source_inventory.json in-place.

    python scripts/reindex_guidance_sources.py --check --inventory <path>
    python scripts/reindex_guidance_sources.py --write --inventory <path>
        Use a custom inventory path (primarily for testing).

Exit codes:
    0  success / no drift
    1  drift detected (--check mode)
    2  usage or file-not-found error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_DEFAULT_INVENTORY = (
    Path(__file__).resolve().parent.parent / "docs" / "guidance" / "source_inventory.json"
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_md_path(raw: str, inventory_dir: Path) -> Path:
    """Resolve a possibly-relative path against the inventory directory."""
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    # Try relative to inventory file's directory, then to repo root
    by_dir = inventory_dir / candidate
    if by_dir.exists():
        return by_dir
    return candidate


def run_check(inventory_path: Path) -> int:
    """Check all derived_md_sha256_optional values; return 0=clean, 1=drift."""
    if not inventory_path.is_file():
        sys.stderr.write(f"Inventory not found: {inventory_path}\n")
        return 2

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    sources = inventory.get("sources") or []
    inv_dir = inventory_path.parent
    drift_found = False

    for entry in sources:
        if not isinstance(entry, dict):
            continue
        raw_md = entry.get("derived_md_path_optional")
        if not raw_md:
            continue
        md_path = _resolve_md_path(str(raw_md), inv_dir)
        if not md_path.is_file():
            sys.stderr.write(
                f"[drift] {entry.get('source_id')!r}: "
                f"derived_md_path_optional {str(md_path)!r} not found on disk\n"
            )
            drift_found = True
            continue

        actual = _sha256_file(md_path)
        recorded = entry.get("derived_md_sha256_optional")
        if recorded != actual:
            sys.stderr.write(
                f"[drift] {entry.get('source_id')!r}: "
                f"derived_md_sha256_optional mismatch "
                f"(recorded={recorded!r}, actual={actual!r})\n"
            )
            drift_found = True

    if drift_found:
        sys.stderr.write(
            "Drift detected. Run 'python scripts/reindex_guidance_sources.py --write' to fix.\n"
        )
        return 1

    sys.stdout.write("All derived MD sha256 hashes match. No drift.\n")
    return 0


def run_write(inventory_path: Path) -> int:
    """Re-pin derived_md_sha256_optional for all entries with existing .md files."""
    if not inventory_path.is_file():
        sys.stderr.write(f"Inventory not found: {inventory_path}\n")
        return 2

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    sources = inventory.get("sources") or []
    inv_dir = inventory_path.parent
    updated = 0

    for entry in sources:
        if not isinstance(entry, dict):
            continue
        raw_md = entry.get("derived_md_path_optional")
        if not raw_md:
            continue
        md_path = _resolve_md_path(str(raw_md), inv_dir)
        if not md_path.is_file():
            sys.stderr.write(
                f"[skip] {entry.get('source_id')!r}: "
                f"derived_md_path_optional {str(md_path)!r} not found — skipping\n"
            )
            continue
        actual = _sha256_file(md_path)
        if entry.get("derived_md_sha256_optional") != actual:
            entry["derived_md_sha256_optional"] = actual
            updated += 1

    # Write back with 2-space indent, no trailing newline issues
    text = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    inventory_path.write_text(text, encoding="utf-8")
    sys.stdout.write(f"Updated {updated} derived_md_sha256_optional entries.\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reindex_guidance_sources",
        description=(
            "Check or repin derived_md_sha256_optional in source_inventory.json. "
            "Use --check in CI; use --write to update hashes after renderer changes."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify hashes; exit 1 on drift. No writes.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Update derived_md_sha256_optional in-place.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=_DEFAULT_INVENTORY,
        help=f"Path to source_inventory.json (default: {_DEFAULT_INVENTORY})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.check:
        return run_check(args.inventory)
    if args.write:
        return run_write(args.inventory)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
