"""Phase 6E-prep-A — Extract Markdown from a guidance PDF (operator CLI).

Mirrors the shape of ``scripts/extract_guidance_pdf_text.py``.
Module is importable without ``pdfplumber``; only the ``--extract`` action
requires it.

Usage:
    python scripts/extract_guidance_md.py \\
        --source-id mdcg-sscp-public-guidance \\
        [--inventory docs/guidance/source_inventory.json] \\
        [--out docs/guidance/sources/mdcg/md_mdcg_2019_9_sscp_en.md]

Exit codes:
    0  success
    1  extraction or write error
    2  missing input file or bad arguments
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make src/ importable so locuslab imports work.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_INVENTORY = _REPO_ROOT / "docs" / "guidance" / "source_inventory.json"
# Keep in sync with locuslab.guidance.extract_md._RENDERER_VERSION.
_RENDERER_VERSION = "locuslab-renderer:0.2.0"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract_guidance_md",
        description=(
            "Extract structured Markdown from a guidance PDF using pdfplumber. "
            "Output is a review artifact tagged with derived_md_review_status: machine_generated. "
            "Requires: pip install -e '.[guidance-extract]'"
        ),
    )
    parser.add_argument(
        "--source-id",
        dest="source_id",
        required=True,
        help="source_id from source_inventory.json (e.g. mdcg-sscp-public-guidance).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=_DEFAULT_INVENTORY,
        help=f"Path to source_inventory.json (default: {_DEFAULT_INVENTORY})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output .md file path. Default: sibling of the source PDF/TXT, "
            "with .md extension replacing the original extension."
        ),
    )
    parser.add_argument(
        "--parser-version",
        dest="parser_version",
        default=None,
        help=(
            "Override the parser version string written to frontmatter. "
            f"Default: pdfplumber:<version>+{_RENDERER_VERSION}"
        ),
    )
    return parser


def _find_inventory_entry(
    inventory_path: Path, source_id: str
) -> dict[str, object]:
    import json

    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    for entry in inv.get("sources") or []:
        if isinstance(entry, dict) and entry.get("source_id") == source_id:
            return entry  # type: ignore[return-value]
    raise KeyError(f"source_id {source_id!r} not found in {inventory_path}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.inventory.is_file():
        sys.stderr.write(f"Inventory not found: {args.inventory}\n")
        return 2

    try:
        entry = _find_inventory_entry(args.inventory, args.source_id)
    except KeyError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2

    local_path_raw = entry.get("local_path_optional")
    if not local_path_raw:
        sys.stderr.write(
            f"source_id {args.source_id!r} has no 'local_path_optional' in inventory.\n"
        )
        return 2

    pdf_path = Path(str(local_path_raw))
    if not pdf_path.is_absolute():
        pdf_path = _REPO_ROOT / pdf_path

    if not pdf_path.is_file():
        sys.stderr.write(f"Source file not found: {pdf_path}\n")
        return 2

    # Determine output path
    out_path = args.out if args.out is not None else pdf_path.with_suffix(".md")

    # Determine parser version
    try:
        import pdfplumber  # type: ignore[import-untyped]

        pdfplumber_ver = getattr(pdfplumber, "__version__", "unknown")
    except ImportError:
        sys.stderr.write(
            "pdfplumber is not installed. "
            'Install with: pip install -e ".[guidance-extract]"\n'
        )
        return 1

    parser_version = args.parser_version or f"pdfplumber:{pdfplumber_ver}+{_RENDERER_VERSION}"

    # Run extraction (deferred import inside extract_md)
    from locuslab.guidance.extract_md import extract_md  # noqa: PLC0415

    try:
        result = extract_md(pdf_path, parser_version=parser_version)
    except RuntimeError as exc:
        sys.stderr.write(f"Extraction error: {exc}\n")
        return 1

    # Build frontmatter
    from locuslab.guidance.frontmatter import Frontmatter, dump_frontmatter  # noqa: PLC0415

    fm = Frontmatter(
        source_id=args.source_id,
        document_family=str(entry.get("document_family", "OTHER")),
        derived_from_source_id=args.source_id,  # Self-referential for primary PDFs
        derived_md_review_status="machine_generated",
        cross_refs=[],
    )

    # Build extra frontmatter lines for metadata not in Frontmatter dataclass.
    # Uses block-list style per restricted YAML dialect (spec §7); flow style is forbidden.
    extra_lines: list[str] = []
    if result.normalization_applied:
        extra_lines.append("_extractor_normalization:")
        extra_lines.extend(f"  - {norm}" for norm in result.normalization_applied)
    if result.limitations:
        extra_lines.append(f"_extractor_limitations_count: {len(result.limitations)}")

    # Serialize frontmatter + extra metadata + body
    fm_text = dump_frontmatter(fm, result.markdown_text)

    # Inject extra lines before the closing ---
    if extra_lines:
        close_marker = "\n---\n"
        first_close = fm_text.find(close_marker)
        if first_close != -1:
            insert_pos = first_close
            extra_block = "\n" + "\n".join(extra_lines)
            fm_text = fm_text[:insert_pos] + extra_block + fm_text[insert_pos:]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(fm_text, encoding="utf-8")

    sys.stdout.write(
        f"Extracted {len(result.page_anchors)} page(s) from {pdf_path}\n"
        f"  -> {out_path}\n"
        f"  parser: {parser_version}\n"
        f"  normalizations: {result.normalization_applied}\n"
        f"  limitations: {len(result.limitations)} noted\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
