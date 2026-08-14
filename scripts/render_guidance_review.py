"""SSCP guidance review checklist renderer (offline).

Reads an existing locus verify run directory (read-only) plus an SSCP
rule pack, and writes:

- <out>/guidance_review.json
- <out>/guidance_review.md

The output is a human-review checklist; it is NOT an ECO finding and does
not modify the verify run directory. See `docs/architecture.md`.

Usage:
    python scripts/render_guidance_review.py \\
        --run-dir <path-to-locus-verify-output> \\
        --document-family SSCP \\
        --rule-pack docs/rules/guidance/sscp/rule_pack.json \\
        --inventory docs/guidance/source_inventory.json \\
        --out <out-dir>

Exit codes:
    0  success
    2  invalid arguments or missing input files
    3  rule pack failed validation
    4  unsupported --document-family (Phase 6B is SSCP-only)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make src/ importable when run as `python scripts/...`.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.guidance import GuidanceValidationError, write_checklist_outputs  # noqa: E402

_SUPPORTED_FAMILIES = ("SSCP",)
_DEFAULT_RULE_PACK = Path("docs/rules/guidance/sscp/rule_pack.json")
_DEFAULT_INVENTORY = Path("docs/guidance/source_inventory.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_guidance_review",
        description=(
            "Render a human-review checklist from a guidance rule pack "
            "and an optional locus verify run directory. The checklist is "
            "a review aid, not an ECO finding."
        ),
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "Optional path to a locus verify output directory. If present "
            "and contains report.json, the run_id and counts will be "
            "echoed into the checklist. The directory is read-only."
        ),
    )
    parser.add_argument(
        "--document-family",
        type=str,
        required=True,
        help=(
            "Document family to render the checklist for. Phase 6B "
            f"supports: {', '.join(_SUPPORTED_FAMILIES)}."
        ),
    )
    parser.add_argument(
        "--rule-pack",
        type=Path,
        default=_DEFAULT_RULE_PACK,
        help=f"Path to the rule pack JSON (default: {_DEFAULT_RULE_PACK}).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=_DEFAULT_INVENTORY,
        help=f"Path to the source inventory JSON (default: {_DEFAULT_INVENTORY}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory (will be created if missing).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.document_family not in _SUPPORTED_FAMILIES:
        sys.stderr.write(
            f"Unsupported --document-family {args.document_family!r}. "
            f"Phase 6B supports: {', '.join(_SUPPORTED_FAMILIES)}. "
            f"Future packets will add more document families.\n"
        )
        return 4

    if not args.rule_pack.is_file():
        sys.stderr.write(f"Rule pack not found: {args.rule_pack}\n")
        return 2
    if not args.inventory.is_file():
        sys.stderr.write(f"Inventory not found: {args.inventory}\n")
        return 2
    if args.run_dir is not None and not args.run_dir.is_dir():
        sys.stderr.write(f"Run directory not found: {args.run_dir}\n")
        return 2

    rule_pack = json.loads(args.rule_pack.read_text(encoding="utf-8"))
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))

    try:
        outputs = write_checklist_outputs(
            rule_pack=rule_pack,
            inventory=inventory,
            run_dir=args.run_dir,
            document_family=args.document_family,
            out_dir=args.out,
        )
    except GuidanceValidationError as exc:
        sys.stderr.write(
            f"Rule pack failed validation ({len(exc.issues)} issue(s)):\n"
        )
        for issue in exc.issues:
            sys.stderr.write(f"  - {issue}\n")
        return 3

    n_rules = len(rule_pack.get("rules") or [])
    sys.stdout.write(
        f"Checklist written: {n_rules} review item(s), "
        f"document_family={args.document_family}, "
        f"pack={rule_pack.get('pack_id')} v{rule_pack.get('pack_version')}.\n"
    )
    sys.stdout.write(f"  json: {outputs['json']}\n")
    sys.stdout.write(f"  md:   {outputs['md']}\n")
    sys.stdout.write(
        "Output boundary: review aid, not an ECO finding. "
        "Items start at 'needs_human_confirmation'.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
