"""Demo runner: verify the bundled synthetic dossier and list artifacts.

Runs the same `verify_dossier` path as `locus verify`, prints the standard
CLI summary line, then lists artifact paths and a short review order.
Points at `docs/LIMITATIONS.md` for known gaps.

No GUI. No network. No fixture modification.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --out tmp/demo
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# Allow running the script directly via `python scripts/...` without an
# installed package (mirrors scripts/validate_guidance_rules.py).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.pipeline import verify_dossier  # noqa: E402

_DEFAULT_DOSSIER = Path("fixtures/demo_dossier")
_LIMITATIONS = "docs/LIMITATIONS.md"

# Artifacts written by the current verify pipeline, listed in review order
# then remaining machine artifacts.
_ARTIFACT_ORDER: tuple[str, ...] = (
    "report.docx",
    "findings.xlsx",
    "audit_manifest.json",
    "report.json",
    "findings.csv",
    "findings.jsonl",
    "graph.jsonl",
    "claims.jsonl",
    "citations.jsonl",
    "sources.jsonl",
    "evidence_links.jsonl",
)


def _default_out_dir() -> Path:
    return Path(tempfile.gettempdir()) / "locuslab_demo_run"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_demo",
        description=(
            "Run LocusLab verify on the bundled demo dossier and print "
            "artifact paths plus a short review order. Offline only."
        ),
    )
    parser.add_argument(
        "--dossier",
        type=Path,
        default=_DEFAULT_DOSSIER,
        help=f"Dossier directory to verify (default: {_DEFAULT_DOSSIER}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output run directory (default: a system temp directory under "
            "locuslab_demo_run/)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    dossier_dir: Path = args.dossier
    out_dir: Path = args.out if args.out is not None else _default_out_dir()

    if not dossier_dir.is_dir():
        sys.stderr.write(f"Dossier directory not found: {dossier_dir}\n")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    result = verify_dossier(dossier_dir=dossier_dir, output_dir=out_dir)

    # CLI-equivalent summary line (matches locus verify output verbatim).
    sys.stdout.write(
        f"Verified: {result.n_claims} claims, {result.n_citations} citations, "
        f"{result.n_sources} sources, {result.n_links} evidence links, "
        f"{result.n_findings} findings, {result.n_graph_records} graph records, "
        f"report package written. Output: {result.output_dir}\n"
    )

    sys.stdout.write("\nReview artifacts:\n")
    sys.stdout.write("  Open in this order:\n")
    sys.stdout.write("    1. report.docx\n")
    sys.stdout.write("    2. findings.xlsx\n")
    sys.stdout.write("    3. audit_manifest.json\n")
    sys.stdout.write(f"  Known gaps: {_LIMITATIONS}\n")
    sys.stdout.write("\n  Artifact paths:\n")
    for name in _ARTIFACT_ORDER:
        path = out_dir / name
        marker = "OK " if path.is_file() and path.stat().st_size > 0 else "?? "
        sys.stdout.write(f"    {marker}{path}\n")

    if result.n_sources == 0:
        sys.stdout.write(
            "\nNote: 0 sources resolved. The dossier likely has no "
            "bibliography directory, so every claim becomes a "
            "claim_without_resolved_source or evidence_link_requires_manual_review "
            "finding. Either expected (a dossier with no bibliography) or a "
            "missing bibliography in the input tree (the bundled demo dossier "
            "should resolve sources).\n"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
